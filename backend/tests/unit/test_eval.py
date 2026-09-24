"""Kiểm thử bộ đánh giá: eval/score.py (chuẩn hoá + chấm) và scripts/eval_run.py."""

from __future__ import annotations

import copy
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

from app.domain.qc_rules import run_qc
from app.ports.llm import LLMResult

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

import eval_run  # noqa: E402
import gen_synthetic_invoices as gen  # noqa: E402
import score  # noqa: E402


def _truth() -> dict[str, Any]:
    return gen.make_invoice(random.Random(1), 1)


def test_synthetic_invoice_passes_all_qc_rules() -> None:
    rng = random.Random(3)
    for i in range(20):
        results, needs_review = run_qc(gen.make_invoice(rng, i))
        assert needs_review is False, [r for r in results if not r.passed]


def test_exact_match_scores_full_marks() -> None:
    truth = _truth()
    s = score.score_document("a.png", copy.deepcopy(truth), truth)
    assert s.field_accuracy == 1.0 and s.line_precision == 1.0 and s.line_recall == 1.0


def test_normalization_before_compare() -> None:
    truth = _truth()
    pred = copy.deepcopy(truth)
    y, m, d = truth["issue_date"].split("-")
    pred["issue_date"] = f"{d}/{m}/{y}"
    pred["seller"]["name"] = "  " + truth["seller"]["name"].upper() + "  "
    pred["totals"]["total"] = f"{int(truth['totals']['total']):,}".replace(",", ".")
    pred["line_items"] = list(reversed(pred["line_items"]))  # thứ tự dòng không quan trọng
    s = score.score_document("a.png", pred, truth)
    assert s.wrong == [] and s.line_recall == 1.0


def test_wrong_fields_and_missing_prediction() -> None:
    truth = _truth()
    pred = copy.deepcopy(truth)
    pred["totals"]["total"] = str(int(truth["totals"]["total"]) + 1)  # tiền lệch 1đ = sai
    pred["seller"]["tax_code"] = "0000000000"
    s = score.score_document("a.png", pred, truth)
    assert sorted(s.wrong) == ["seller.tax_code", "totals.total"]
    assert s.field_accuracy == 1 - 2 / len(score.HEADER_FIELDS)
    assert score.score_document("b.png", None, truth).field_accuracy == 0.0


def test_summary_groups_by_quality() -> None:
    truth = _truth()
    clean = score.score_document("a", truth, {**truth, "quality": "clean"})
    noisy = score.score_document("b", None, {**truth, "quality": "noisy"})
    rows = {g.group: g.row() for g in score.summarize([clean, noisy])}
    assert rows["clean"]["field_accuracy"] == 1.0
    assert rows["noisy"]["field_accuracy"] == 0.0
    assert rows["all"]["documents"] == 2 and rows["all"]["field_accuracy"] == 0.5


class TruthLLM:
    """Mô hình giả trả đúng nhãn chuẩn, riêng một tệp đọc sai số hoá đơn."""

    def __init__(self, truths: list[dict[str, Any]]) -> None:
        self.truths = truths

    def complete(self, messages, *, schema=None, images=None, timeout=None):  # noqa: ANN001, ANN201
        data = {k: v for k, v in self.truths.pop(0).items() if k != "quality"}
        if not self.truths:
            data["invoice_no"] = "0000000"
        return LLMResult(
            content=json.dumps(data),
            parsed=data,
            model="m",
            token_in=1,
            token_out=1,
            latency_ms=900,
        )


def test_eval_run_end_to_end(tmp_path: Path) -> None:
    gen.main(["--count", "3", "--out", str(tmp_path)])
    truths = [
        json.loads((tmp_path / "ground_truth" / f"syn_000{i}.json").read_text(encoding="utf-8"))
        for i in (1, 2, 3)
    ]
    out = tmp_path / "results.csv"
    summary = eval_run.run(TruthLLM(truths), tmp_path / "dataset", tmp_path / "ground_truth", out)
    overall = next(g for g in summary if g["group"] == "all")
    assert overall["documents"] == 3
    assert overall["field_accuracy"] == round(1 - 1 / (3 * len(score.HEADER_FIELDS)), 4)
    with out.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["wrong_fields"] for r in rows] == ["", "", "invoice_no"]
    assert out.with_name("results_summary.csv").is_file()
