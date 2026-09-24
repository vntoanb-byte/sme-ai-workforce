"""
Dịch vụ chỉ số vận hành (bảng điều khiển + /admin/metrics)

Định nghĩa chỉ số (tháng hiện tại theo TIMEZONE, so với tháng trước):
  - docs_processed: chứng từ nạp trong tháng đã có kết quả (ok | needs_review |
    rejected | failed).
  - automation_rate: % chứng từ có dữ liệu trích xuất mà ĐẠT tự động — status
    ok và KHÔNG có quyết định xác nhận thủ công nào.
  - hours_saved = số chứng từ đạt tự động × manual_minutes_per_doc / 60.
  - needs_review_total: chứng từ trong tháng từng cần người xác nhận;
    needs_review_open: số đang chờ (mọi thời điểm) — chấm đỏ thanh điều hướng.
  - llm_status: theo llm_calls 15 phút gần nhất — không lỗi 'ok', lỗi một phần
    'degraded', toàn lỗi 'down' (không có lời gọi nào → 'ok').
Kèm số lần chạy/độ trễ trung bình/token đã dùng trong tháng cho quản trị viên.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.artifact import Document
from app.models.audit import LlmCall
from app.models.extraction import Extraction, HumanReview
from app.models.run import Run
from app.services import settings_service

_PROCESSED = ("ok", "needs_review", "rejected", "failed")


def _month_bounds(now_local: datetime) -> tuple[datetime, datetime, datetime]:
    start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_start = (start - timedelta(days=1)).replace(day=1)
    return prev_start.astimezone(UTC), start.astimezone(UTC), now_local.astimezone(UTC)


def _period_counts(db: Session, start: datetime, end: datetime) -> dict[str, int]:
    in_period = and_(Document.created_at >= start, Document.created_at < end)
    reviewed = exists().where(HumanReview.document_id == Document.id)
    extracted = exists().where(Extraction.document_id == Document.id)
    processed = db.scalar(
        select(func.count(Document.id)).where(in_period, Document.status.in_(_PROCESSED))
    ) or 0
    with_extraction = db.scalar(
        select(func.count(Document.id)).where(in_period, extracted)
    ) or 0
    auto_ok = db.scalar(
        select(func.count(Document.id)).where(in_period, Document.status == "ok", ~reviewed)
    ) or 0
    review_total = db.scalar(
        select(func.count(Document.id)).where(
            in_period, (Document.status == "needs_review") | reviewed
        )
    ) or 0
    return {
        "processed": processed,
        "with_extraction": with_extraction,
        "auto_ok": auto_ok,
        "review_total": review_total,
    }


def _rate(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def llm_status(db: Session, now: datetime) -> str:
    since = now - timedelta(minutes=15)
    total, errors = db.execute(
        select(
            func.count(LlmCall.id),
            func.coalesce(func.sum(case((LlmCall.status == "error", 1), else_=0)), 0),
        ).where(LlmCall.created_at >= since)
    ).one()
    if not total:
        return "ok"
    if errors == total:
        return "down"
    return "degraded" if errors else "ok"


def metrics(db: Session, now: datetime | None = None) -> dict[str, Any]:
    tz = ZoneInfo(settings.TIMEZONE)
    now_local = (now or datetime.now(UTC)).astimezone(tz)
    prev_start, month_start, now_utc = _month_bounds(now_local)
    cur = _period_counts(db, month_start, now_utc + timedelta(seconds=1))
    prev = _period_counts(db, prev_start, month_start)

    minutes = float(settings_service.get(db, "manual_minutes_per_doc", 4) or 0)
    cur_rate = _rate(cur["auto_ok"], cur["with_extraction"])
    prev_rate = _rate(prev["auto_ok"], prev["with_extraction"])
    delta_docs = (
        round(100.0 * (cur["processed"] - prev["processed"]) / prev["processed"])
        if prev["processed"]
        else 0
    )
    open_reviews = db.scalar(
        select(func.count(Document.id)).where(Document.status == "needs_review")
    ) or 0
    runs, avg_latency, tokens = db.execute(
        select(
            select(func.count(Run.id)).where(Run.created_at >= month_start).scalar_subquery(),
            select(func.avg(LlmCall.latency_ms))
            .where(LlmCall.created_at >= month_start, LlmCall.status == "success")
            .scalar_subquery(),
            select(
                func.coalesce(
                    func.sum(
                        func.coalesce(LlmCall.prompt_tokens, 0)
                        + func.coalesce(LlmCall.completion_tokens, 0)
                    ),
                    0,
                )
            )
            .where(LlmCall.created_at >= month_start)
            .scalar_subquery(),
        )
    ).one()
    return {
        "period_label": f"Tháng {now_local.month}/{now_local.year}",
        "docs_processed": cur["processed"],
        "docs_processed_delta": delta_docs,
        "hours_saved": round(cur["auto_ok"] * minutes / 60, 1),
        "minutes_per_doc": minutes,
        "automation_rate": cur_rate,
        "automation_rate_delta": round(cur_rate - prev_rate, 1),
        "needs_review_total": cur["review_total"],
        "needs_review_open": open_reviews,
        "llm_status": llm_status(db, now_utc),
        "runs_this_month": runs or 0,
        "avg_llm_latency_ms": int(avg_latency) if avg_latency is not None else None,
        "tokens_this_month": int(tokens or 0),
    }
