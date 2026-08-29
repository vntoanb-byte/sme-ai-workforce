"""
Kiểm thử điểm cuối chứng từ (TASK-006, bản tối giản — xem IMPLEMENTATION_PLAN.md)

Dùng FastAPI TestClient qua fixture `client` (tests/conftest.py) — get_db/get_llm/
get_storage đều bị ghi đè, KHÔNG chạm DB/kho tệp thật của tiến trình dev,
KHÔNG gọi mạng thật (LLM giả `fake_llm`).

CHƯA hiện thực (ngoài phạm vi TASK-006, xem NOTE trong conftest.py):
  - Phân quyền theo vai trò (USER/MANAGER) — chưa có auth cho endpoint này.
  - PATCH /documents/{id}/extraction (sửa tay của con người).
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.ports.llm import LLMUnavailable
from tests.conftest import VALID_INVOICE_PAYLOAD, FakeLLM


def _fake_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 10), color=(0, 128, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_valid_invoice_returns_ok_with_full_detail(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/documents",
        files={"file": ("hd-001.png", _fake_png(), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["filename"] == "hd-001.png"
    assert body["invoice_no"] == "0000123"
    assert body["seller_name"] == "Công ty TNHH ABC"
    # TASK-007: PHẢI trỏ đúng route GET /documents/{id}/file thật (đã hiện
    # thực ở TASK-006) — KHÔNG dùng storage.url_for() ("/artifacts/...") vì
    # route đó chưa từng được mount, phát hiện thật khi <img> vỡ trên frontend.
    assert body["file_url"] == f"/api/v1/documents/{body['id']}/file"
    assert body["qc_failed"] == 0
    assert len(body["qc"]) == 8
    assert body["data"]["invoice_no"] == "0000123"
    assert body["model_name"] == "fake-model-v1"
    # frontend/src/api/types.ts khai báo total/totals.*/line_items[].* là
    # `number` — Decimal PHẢI ép về float ở biên API (TASK-007), không được
    # trả chuỗi (Pydantic/FastAPI mặc định serialize Decimal thành str).
    assert isinstance(body["total"], float)
    assert isinstance(body["data"]["totals"]["subtotal"], float)
    assert isinstance(body["data"]["line_items"][0]["unit_price"], float)


def test_upload_non_image_pdf_returns_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/documents",
        files={"file": ("bao-cao.zip", b"PK\x03\x04not-an-image", "application/zip")},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_list_documents_reflects_uploaded_document(client: TestClient) -> None:
    client.post(
        "/api/v1/documents",
        files={"file": ("hd-002.png", _fake_png(), "image/png")},
    )

    resp = client.get("/api/v1/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["filename"] == "hd-002.png"
    assert body["items"][0]["invoice_no"] == "0000123"


def test_list_documents_filter_by_status(client: TestClient) -> None:
    client.post(
        "/api/v1/documents",
        files={"file": ("hd-ok.png", _fake_png(), "image/png")},
    )
    client.post(
        "/api/v1/documents",
        files={"file": ("bad.zip", b"not-image", "application/zip")},
    )

    resp_ok = client.get("/api/v1/documents", params={"status": "ok"})
    resp_rejected = client.get("/api/v1/documents", params={"status": "rejected"})

    assert resp_ok.json()["total"] == 1
    assert resp_ok.json()["items"][0]["filename"] == "hd-ok.png"
    assert resp_rejected.json()["total"] == 1
    assert resp_rejected.json()["items"][0]["filename"] == "bad.zip"


def test_get_document_detail_by_id(client: TestClient) -> None:
    upload = client.post(
        "/api/v1/documents",
        files={"file": ("hd-003.png", _fake_png(), "image/png")},
    ).json()

    resp = client.get(f"/api/v1/documents/{upload['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == upload["id"]
    assert resp.json()["invoice_no"] == "0000123"


def test_get_document_detail_404_when_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/documents/999999")
    assert resp.status_code == 404


def test_get_document_file_streams_original_bytes(client: TestClient) -> None:
    original = _fake_png()
    upload = client.post(
        "/api/v1/documents",
        files={"file": ("hd-004.png", original, "image/png")},
    ).json()

    resp = client.get(f"/api/v1/documents/{upload['id']}/file")
    assert resp.status_code == 200
    assert resp.content == original
    assert resp.headers["content-type"] == "image/png"


def test_presign_reports_existing_after_upload(client: TestClient) -> None:
    png_bytes = _fake_png()
    import hashlib

    sha256 = hashlib.sha256(png_bytes).hexdigest()

    before = client.post("/api/v1/documents/presign", json={"sha256": sha256})
    assert before.json() == {"exists": False}

    client.post("/api/v1/documents", files={"file": ("hd-005.png", png_bytes, "image/png")})

    after = client.post("/api/v1/documents/presign", json={"sha256": sha256})
    assert after.json() == {"exists": True}


def test_upload_llm_unavailable_returns_200_with_failed_status(
    client: TestClient, fake_llm: FakeLLM
) -> None:
    """LLM lỗi (circuit breaker/timeout) KHÔNG được làm request trả 500 —
    người dùng vẫn thấy chứng từ trong danh sách với status=failed."""
    fake_llm._raise_exc = LLMUnavailable("bộ ngắt mạch đang mở")  # ghi đè sau khi fixture tạo

    resp = client.post(
        "/api/v1/documents",
        files={"file": ("hd-006.png", _fake_png(), "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


def test_upload_duplicate_bytes_reuses_artifact_but_creates_two_documents(
    client: TestClient,
) -> None:
    png_bytes = _fake_png()
    first = client.post(
        "/api/v1/documents", files={"file": ("a.png", png_bytes, "image/png")}
    ).json()
    second = client.post(
        "/api/v1/documents", files={"file": ("b.png", png_bytes, "image/png")}
    ).json()

    assert first["id"] != second["id"]

    listing = client.get("/api/v1/documents").json()
    assert listing["total"] == 2


# Đối chiếu payload mẫu dùng chung với unit test, tránh 2 nguồn "hoá đơn hợp
# lệ" lệch nhau theo thời gian.
def test_shared_valid_invoice_payload_still_matches_conftest() -> None:
    assert VALID_INVOICE_PAYLOAD["invoice_no"] == "0000123"
