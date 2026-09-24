"""
Điểm cuối xác nhận thủ công

  GET  /reviews              — hàng chờ, sắp theo mức độ nghiêm trọng rồi thời gian
  POST /reviews/{id}/resolve — {action: approve|correct|reject, data?, note?}
  GET  /reviews/stats        — số lượng đang chờ (chấm đỏ thanh điều hướng)
`id` là document id (hàng chờ = chứng từ status=needs_review, ADR-003).
Mọi người dùng đã đăng nhập đều được xác nhận (nghiệp vụ của kế toán viên).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, Queue
from app.schemas.common import Page
from app.schemas.document import ReviewItemOut, ReviewResolve, ReviewStats
from app.services import review_service

router = APIRouter()


@router.get("", response_model=Page[ReviewItemOut])
def list_reviews(
    db: DbSession,
    _user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    items, total = review_service.queue_page(db, page=page, page_size=page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/stats", response_model=ReviewStats)
def review_stats(db: DbSession, _user: CurrentUser) -> dict[str, int]:
    return review_service.stats(db)


@router.post("/{document_id}/resolve")
def resolve_review(
    document_id: int, body: ReviewResolve, db: DbSession, queue: Queue, user: CurrentUser
) -> dict[str, Any]:
    document = review_service.get_document(db, document_id)
    review_service.resolve(
        db, queue, document, body.action, user, data=body.data, note=body.note
    )
    db.commit()
    return {"id": document.id, "status": document.status}
