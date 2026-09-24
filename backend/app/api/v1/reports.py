"""
Điểm cuối báo cáo

  POST /reports/preview                — {from, to, group_by} → dữ liệu tổng hợp JSON
  POST /reports/export                 — sinh tệp (xlsx|pdf), trả về artifact_id
  GET  /reports/{artifact_id}/download — tải tệp (báo cáo, tệp kết quả lần chạy);
                                         ?filename= đặt tên tệp khi lưu
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, Storage
from app.core.errors import NotFound
from app.models.artifact import Artifact
from app.schemas.document import ExportRequest, ExportResult, ReportPreview, ReportRequest
from app.services import report_service
from app.tools.base import artifact_ref

router = APIRouter()

_SAFE_NAME = re.compile(r"[^\w.\- ]+", re.UNICODE)


@router.post("/preview", response_model=ReportPreview)
def preview(body: ReportRequest, db: DbSession, _user: CurrentUser) -> dict[str, Any]:
    data = report_service.aggregate(db, body.date_from, body.date_to, body.group_by)
    out = data.to_dict()
    out["date_from"], out["date_to"] = out.pop("from"), out.pop("to")
    return out


@router.post("/export", response_model=ExportResult)
def export(
    body: ExportRequest, db: DbSession, storage: Storage, _user: CurrentUser
) -> dict[str, Any]:
    data = report_service.aggregate(db, body.date_from, body.date_to, body.group_by)
    artifact, filename = report_service.export(db, storage, data, body.format)
    db.commit()
    return {
        "artifact_id": artifact.id,
        "filename": filename,
        "download_url": f"/api/v1/reports/{artifact.id}/download?filename={quote(filename)}",
    }


@router.get("/{artifact_id}/download")
def download(
    artifact_id: int,
    db: DbSession,
    storage: Storage,
    _user: CurrentUser,
    filename: str | None = None,
) -> StreamingResponse:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise NotFound("Không tìm thấy tệp.")
    ext = artifact.path.rsplit(".", 1)[-1] if "." in artifact.path else "bin"
    name = _SAFE_NAME.sub("_", filename or "").strip() or f"tep-{artifact.id}.{ext}"
    fh = storage.open(artifact_ref(artifact))

    def chunks():  # noqa: ANN202
        try:
            while chunk := fh.read(64 * 1024):
                yield chunk
        finally:
            fh.close()

    return StreamingResponse(
        chunks(),
        media_type=artifact.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )
