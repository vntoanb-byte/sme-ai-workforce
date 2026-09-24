"""Kiểm thử xác nhận thủ công: hàng chờ, approve/correct/reject, PATCH chứng từ,
nhật ký kiểm toán trước/sau (ADR-003: hàng chờ = chứng từ status=needs_review)."""

from __future__ import annotations

import io
import json
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.extraction import Extraction, HumanReview
from tests.conftest import FakeLLM, invoice_payload


def _png(seed: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 10), color=(seed, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client: TestClient, fake_llm: FakeLLM, payload: dict[str, Any], seed: int) -> dict:
    fake_llm._parsed = payload
    resp = client.post(
        "/api/v1/documents", files={"file": (f"hd{seed}.png", _png(seed), "image/png")}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _two_errors(no: str) -> dict[str, Any]:
    bad = invoice_payload(no, bad_total=True)
    bad["seller"] = {**bad["seller"], "tax_code": "0101234566"}  # thêm lỗi QC-04
    return bad


def test_review_queue_sorted_by_severity(client: TestClient, fake_llm: FakeLLM) -> None:
    ok = _upload(client, fake_llm, invoice_payload("0000001"), 1)
    one = _upload(client, fake_llm, invoice_payload("0000002", bad_total=True), 2)
    two = _upload(client, fake_llm, _two_errors("0000003"), 3)
    assert ok["status"] == "ok" and one["status"] == "needs_review"

    queue = client.get("/api/v1/reviews").json()
    assert [i["document_id"] for i in queue["items"]] == [two["id"], one["id"]]
    assert queue["items"][0]["critical_failed"] == 2
    assert client.get("/api/v1/reviews/stats").json() == {"pending": 2}
    assert client.get("/api/v1/admin/metrics").json()["needs_review_open"] == 2
    # Cùng dữ liệu với bộ lọc danh sách chứng từ (không có màn hình riêng).
    assert client.get("/api/v1/documents?status=needs_review").json()["total"] == 2


def test_resolve_actions_and_audit(
    client: TestClient, user_client: TestClient, fake_llm: FakeLLM, db: Session
) -> None:
    a = _upload(client, fake_llm, invoice_payload("0000011", bad_total=True), 1)
    b = _upload(client, fake_llm, invoice_payload("0000012", bad_total=True), 2)
    c = _upload(client, fake_llm, invoice_payload("0000013", bad_total=True), 3)

    approved = user_client.post(f"/api/v1/reviews/{a['id']}/resolve", json={"action": "approve"})
    assert approved.json() == {"id": a["id"], "status": "ok"}

    rejected = user_client.post(
        f"/api/v1/reviews/{b['id']}/resolve", json={"action": "reject", "note": "HĐ giả"}
    )
    assert rejected.json()["status"] == "rejected"

    fixed = dict(c["data"])
    fixed["totals"] = {**fixed["totals"], "total": 110000}
    corrected = user_client.post(
        f"/api/v1/reviews/{c['id']}/resolve", json={"action": "correct", "data": fixed}
    )
    assert corrected.json()["status"] == "ok"
    detail = client.get(f"/api/v1/documents/{c['id']}").json()
    assert detail["model_name"] == "human"
    assert detail["total"] == 110000.0
    assert detail["qc_failed"] == 0  # QC chạy lại trên bản đã sửa

    # Đã xử lý thì không xử lý lại qua hàng chờ.
    again = user_client.post(f"/api/v1/reviews/{a['id']}/resolve", json={"action": "reject"})
    assert again.status_code == 409

    reviews = db.scalars(select(HumanReview).order_by(HumanReview.id)).all()
    assert [r.action for r in reviews] == ["approve", "reject", "correct"]
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "document.review.correct"))
    detail_json = json.loads(audit.detail_json)  # type: ignore[union-attr, arg-type]
    assert detail_json["before"]["totals"]["total"] == "120000"
    assert detail_json["after"]["totals"]["total"] == "110000"
    assert detail_json["status_before"] == "needs_review"


def test_resolve_validation(client: TestClient, fake_llm: FakeLLM) -> None:
    doc = _upload(client, fake_llm, invoice_payload("0000021", bad_total=True), 1)
    no_data = client.post(f"/api/v1/reviews/{doc['id']}/resolve", json={"action": "correct"})
    assert no_data.status_code == 422
    bad_data = client.post(
        f"/api/v1/reviews/{doc['id']}/resolve",
        json={"action": "correct", "data": {"invoice_no": "1"}},
    )
    assert bad_data.status_code == 422 and bad_data.json()["error"]["details"]
    wrong = client.post(f"/api/v1/reviews/{doc['id']}/resolve", json={"action": "xoa"})
    assert wrong.status_code == 422
    assert client.post("/api/v1/reviews/9999/resolve", json={"action": "approve"}).status_code == 404


def test_patch_document_confirm_or_correct(
    client: TestClient, fake_llm: FakeLLM, db: Session
) -> None:
    doc = _upload(client, fake_llm, invoice_payload("0000031", bad_total=True), 1)
    # Giao diện gửi lại nguyên dữ liệu = xác nhận nguyên trạng (approve).
    same = client.patch(f"/api/v1/documents/{doc['id']}", json={"data": doc["data"]})
    assert same.status_code == 200 and same.json()["status"] == "ok"
    assert db.scalar(select(HumanReview.action)) == "approve"
    assert len(db.scalars(select(Extraction)).all()) == 1

    # Chứng từ đã ok vẫn sửa được (tạo phiên bản extraction mới).
    edited = dict(doc["data"], invoice_no="0000032")
    resp = client.patch(f"/api/v1/documents/{doc['id']}", json={"data": edited})
    assert resp.json()["invoice_no"] == "0000032"
    assert len(db.scalars(select(Extraction)).all()) == 2


def test_document_search_and_auth(
    client: TestClient, anon_client: TestClient, fake_llm: FakeLLM
) -> None:
    _upload(client, fake_llm, invoice_payload("0000041"), 1)
    doc = _upload(client, fake_llm, {**invoice_payload("0000042"),
                                     "seller": {"name": "Công ty Minh Long",
                                                "tax_code": "0101234565", "address": None}}, 2)
    found = client.get("/api/v1/documents", params={"q": "minh long"}).json()
    assert [d["id"] for d in found["items"]] == [doc["id"]]
    assert client.get("/api/v1/documents", params={"q": "0000041"}).json()["total"] == 1
    assert anon_client.get("/api/v1/documents").status_code == 401
    assert anon_client.get(f"/api/v1/documents/{doc['id']}/file").status_code == 401
