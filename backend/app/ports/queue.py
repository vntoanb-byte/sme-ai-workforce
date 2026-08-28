"""
Cổng hàng đợi công việc

Giao diện trừu tượng cho hàng đợi. Bản hiện thực trên SQLite nằm ở adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Job:
    """Một công việc (job) trong hàng đợi đã được worker giành (claimed)."""

    id: int
    run_id: int
    priority: int
    attempts: int
    max_attempts: int
    claimed_by: str | None
    lease_until: datetime | None
    created_at: datetime


class JobQueue(Protocol):
    """Giao diện giành việc (job queue) theo ADR-001.

    Bảng job_queue được ghi CHUNG transaction với bản ghi runs — nên enqueue()
    nhận Session của caller, còn claim/complete/fail/reap_expired là các tiến
    trình worker độc lập nên tự quản lý transaction riêng.
    """

    def enqueue(
        self,
        session: Session,
        run_id: int,
        *,
        priority: int = 0,
        available_at: datetime | None = None,
        max_attempts: int = 5,
    ) -> int:
        """Đưa một job vào hàng đợi, trả về job_id.

        Args:
            session: Session SQLAlchemy của CALLER — bắt buộc dùng chung
                transaction với việc tạo bản ghi runs (ADR-001), phương thức này
                KHÔNG tự commit.
            run_id: id của bản ghi runs mà job này thuộc về.
            priority: số càng cao càng được ưu tiên giành trước.
            available_at: thời điểm job được phép giành (mặc định: ngay bây giờ).
            max_attempts: số lần thử tối đa trước khi chuyển sang 'failed'.
        """
        ...

    def claim(self, worker_id: str, *, lease_seconds: int = 300) -> Job | None:
        """Giành một job đang chờ cho worker, trả về Job hoặc None nếu không có.

        Tự quản lý transaction riêng (tiến trình worker độc lập) — dùng giao
        thức BEGIN IMMEDIATE + kiểm rowcount theo ADR-001.
        """
        ...

    def complete(self, job_id: int) -> None:
        """Đánh dấu job đã xử lý xong. Tự quản lý transaction riêng."""
        ...

    def fail(self, job_id: int, error: str) -> None:
        """Đánh dấu job lỗi; thử lại sau backoff hoặc chuyển 'failed' nếu hết lượt.

        Tự quản lý transaction riêng.
        """
        ...

    def reap_expired(self) -> int:
        """Thu hồi job có lease_until đã quá hạn, trả về số lượng đã thu hồi.

        Tự quản lý transaction riêng.
        """
        ...
