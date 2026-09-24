"""
Chạy bộ đánh giá

Chạy toàn bộ bộ dữ liệu đánh giá qua ĐÚNG đường trích xuất của hệ thống
(utils.images.preprocess → mô hình với lược đồ InvoiceExtraction) và tính các
chỉ số của Chương 8 bằng eval/score.py.

  1. Duyệt eval/dataset/ (png/jpg/jpeg/pdf), nhãn chuẩn ở eval/ground_truth/<tên>.json
  2. Độ chính xác theo trường = 1 − (số trường sai / tổng số trường)
  3. Chuẩn hoá trước khi so (xem eval/score.py)
  4. Xuất CSV từng chứng từ + bảng tổng hợp theo nhóm chất lượng ảnh
  5. --model / --base-url để chạy lại với mô hình khác mà không sửa code

Dùng:
    python scripts/eval_run.py --out ../eval/results.csv [--model Qwen3-VL-8B] [--limit 10]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "eval"))

from pydantic import ValidationError  # noqa: E402
from score import score_document, summarize  # noqa: E402

from app.ports.llm import LLMInvalidOutput, LLMProvider, LLMTimeout, LLMUnavailable  # noqa: E402
from app.schemas.invoice import InvoiceExtraction, invoice_json_schema  # noqa: E402
from app.services.document_service import EXTRACTION_PROMPT, prepare_image_bytes  # noqa: E402

_KINDS = {".png": "image", ".jpg": "image", ".jpeg": "image", ".pdf": "pdf"}


def extract(llm: LLMProvider, path: Path) -> tuple[dict[str, Any] | None, int, str | None]:
    """Trích xuất 1 tệp → (dữ liệu | None, độ trễ ms, lỗi)."""
    started = time.monotonic()
    try:
        image = prepare_image_bytes(path.read_bytes(), _KINDS[path.suffix.lower()])
        result = llm.complete(
            [{"role": "user", "content": EXTRACTION_PROMPT}],
            schema=invoice_json_schema(),
            images=[image],
        )
        data = InvoiceExtraction.model_validate(result.parsed).model_dump(mode="json")
        return data, result.latency_ms, None
    except (LLMTimeout, LLMUnavailable, LLMInvalidOutput, ValidationError, OSError) as exc:
        return None, int((time.monotonic() - started) * 1000), f"{type(exc).__name__}: {exc}"


def run(
    llm: LLMProvider, dataset: Path, truth_dir: Path, out: Path, limit: int | None = None
) -> list[dict[str, Any]]:
    files = sorted(p for p in dataset.iterdir() if p.suffix.lower() in _KINDS)[:limit]
    scores, rows = [], []
    for path in files:
        truth_file = truth_dir / f"{path.stem}.json"
        if not truth_file.is_file():
            print(f"  bỏ qua {path.name}: không có nhãn chuẩn")
            continue
        truth = json.loads(truth_file.read_text(encoding="utf-8"))
        predicted, latency, error = extract(llm, path)
        s = score_document(path.name, predicted, truth)
        scores.append(s)
        rows.append(
            {
                "file": path.name,
                "quality": s.quality,
                "field_accuracy": round(s.field_accuracy, 4),
                "line_precision": round(s.line_precision, 4),
                "line_recall": round(s.line_recall, 4),
                "latency_ms": latency,
                "wrong_fields": ";".join(s.wrong),
                "error": error or "",
            }
        )
        print(
            f"  {path.name}: {s.field_accuracy:.1%} ({latency} ms){' — ' + error if error else ''}"
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:  # BOM để Excel đọc đúng tiếng Việt
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["file"])
        writer.writeheader()
        writer.writerows(rows)
    summary = [g.row() for g in summarize(scores)]
    summary_path = out.with_name(out.stem + "_summary.csv")
    with summary_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    if rows:
        avg_latency = sum(r["latency_ms"] for r in rows) / len(rows)
        print(f"\nThời gian trung bình: {avg_latency / 1000:.1f} giây/hoá đơn (mục tiêu ≤ 25 giây)")
    for g in summary:
        print(
            f"[{g['group']}] {g['documents']} chứng từ · chính xác theo trường "
            f"{g['field_accuracy']:.1%} (mục tiêu ≥ 90%) · dòng hàng P={g['line_precision']:.2f}"
            f" R={g['line_recall']:.2f} · sai nhiều: {g['worst_fields'] or '—'}"
        )
    print(f"Đã ghi {out} và {summary_path}")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Chạy bộ đánh giá trích xuất hoá đơn")
    parser.add_argument("--dataset", type=Path, default=ROOT / "eval" / "dataset")
    parser.add_argument("--truth", type=Path, default=ROOT / "eval" / "ground_truth")
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results.csv")
    parser.add_argument("--model", help="Ghi đè LLM_MODEL")
    parser.add_argument("--base-url", help="Ghi đè LLM_BASE_URL")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    if not args.dataset.is_dir():
        parser.error(
            f"Không thấy {args.dataset} — sinh dữ liệu bằng scripts/gen_synthetic_invoices.py"
        )

    from app.adapters.llm_openai_compatible import OpenAICompatibleLLM

    llm = OpenAICompatibleLLM(base_url=args.base_url, model=args.model)
    run(llm, args.dataset, args.truth, args.out, args.limit)


if __name__ == "__main__":
    main()
