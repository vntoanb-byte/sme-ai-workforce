"""
Máy trạng thái của lần chạy

Định nghĩa các trạng thái hợp lệ và phép chuyển tiếp được phép. Mọi thay đổi
trạng thái phải đi qua đây, không được gán trực tiếp vào cột status.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol


class RunStatus(str, Enum):
    """Các trạng thái hợp lệ của một lần chạy (run)."""

    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    RETRYING = "retrying"
    NEEDS_REVIEW = "needs_review"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Trạng thái kết thúc: không còn phép chuyển tiếp nào đi ra khỏi các trạng
# thái này. Một khi run đã ở một trong ba trạng thái này, nó là bất biến.
TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
)


# Bảng chuyển tiếp hợp lệ: from_status -> {to_status hợp lệ}.
#
# Lý do thiết kế:
#   - PENDING: run mới tạo, chờ worker nhận (claim) hoặc bị huỷ trước khi
#     chạy.
#   - CLAIMED: worker đã nhận run nhưng chưa bắt đầu chạy; có thể fail ngay
#     ở bước khởi tạo (ví dụ worker crash) hoặc bị huỷ.
#   - RUNNING: đang thực thi. Có thể kết thúc thành công, thất bại hẳn
#     (FAILED — hết lượt retry), thất bại tạm thời cần thử lại (RETRYING),
#     cần con người xem xét (NEEDS_REVIEW, ví dụ QC rules không qua), hoặc bị
#     huỷ giữa chừng.
#   - RETRYING: thất bại tạm thời, chờ thử lại. Có thể quay lại hàng đợi
#     (PENDING) hoặc được worker nhận lại ngay (CLAIMED); nếu hết ngân sách
#     retry thì chuyển FAILED; vẫn có thể bị huỷ trong lúc chờ.
#   - NEEDS_REVIEW: cần con người can thiệp. Sau khi review có thể duyệt
#     (SUCCEEDED), từ chối (FAILED), yêu cầu chạy lại (RETRYING), hoặc huỷ.
#   - SUCCEEDED / FAILED / CANCELLED: trạng thái kết thúc, không có phép
#     chuyển tiếp nào đi tiếp (xem TERMINAL_STATUSES).
TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.PENDING: {RunStatus.CLAIMED, RunStatus.CANCELLED},
    RunStatus.CLAIMED: {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.RUNNING: {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.RETRYING,
        RunStatus.NEEDS_REVIEW,
        RunStatus.CANCELLED,
    },
    RunStatus.RETRYING: {
        RunStatus.PENDING,
        RunStatus.CLAIMED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    },
    RunStatus.NEEDS_REVIEW: {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.RETRYING,
        RunStatus.CANCELLED,
    },
    RunStatus.SUCCEEDED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}


class InvalidTransitionError(Exception):
    """Ném ra khi cố chuyển trạng thái không có trong bảng TRANSITIONS."""

    def __init__(self, from_status: RunStatus, to_status: RunStatus, run_id: Any = None) -> None:
        self.from_status = from_status
        self.to_status = to_status
        self.run_id = run_id
        subject = f" (run_id={run_id})" if run_id is not None else ""
        super().__init__(
            f"Không thể chuyển trạng thái run từ '{from_status.value}' "
            f"sang '{to_status.value}'{subject}."
        )


class RunLike(Protocol):
    """Giao diện tối thiểu mà `transition()` cần ở đối tượng run.

    `models/run.py` hiện vẫn là stub (chưa có class SQLAlchemy thật). Khi
    model đó được hiện thực, nó chỉ cần có thuộc tính `status` (đọc/ghi được,
    kiểu RunStatus hoặc str trùng giá trị RunStatus) — có `id` thì càng tốt
    (dùng để log/báo lỗi) — là dùng được ngay với các hàm trong module này,
    không cần sửa gì ở đây.
    """

    status: Any
    id: Any


# Callback ghi log tuỳ chọn, được tiêm (dependency injection) vào transition().
# Nhận: (run, from_status, to_status, reason, at) -> None.
LogFn = Callable[[Any, RunStatus, RunStatus, str, datetime], None]


def can_transition(a: RunStatus, b: RunStatus) -> bool:
    """Trả về True nếu được phép chuyển trạng thái từ `a` sang `b`."""
    return b in TRANSITIONS.get(a, set())


def is_terminal(status: RunStatus) -> bool:
    """Trả về True nếu `status` là trạng thái kết thúc, không thể chuyển tiếp."""
    return status in TERMINAL_STATUSES


def transition(
    run: RunLike,
    to: RunStatus,
    reason: str,
    log_fn: LogFn | None = None,
) -> RunLike:
    """Chuyển trạng thái của `run` sang `to`, kèm lý do.

    Đây là điểm duy nhất trong hệ thống được phép gán vào `run.status`. Mọi
    service/worker muốn đổi trạng thái một lần chạy phải gọi qua hàm này,
    không được gán trực tiếp `run.status = ...` ở nơi khác.

    Args:
        run: Đối tượng lần chạy, thoả giao diện `RunLike` (có thuộc tính
            `status`, tuỳ chọn `id`).
        to: Trạng thái đích muốn chuyển tới.
        reason: Lý do chuyển trạng thái (bắt buộc, không được rỗng) — dùng để
            ghi vào run_logs, phục vụ audit và debug.
        log_fn: Callback tuỳ chọn để ghi một dòng log ứng với lần chuyển
            trạng thái này, nhận (run, from_status, to_status, reason, at).
            Nếu không truyền, hàm chỉ đổi `run.status` mà không ghi log ở
            đâu cả — bên gọi (thường là services/) tự quyết định cách ghi.
            # TODO: nối vào models/run.py khi file đó được hiện thực, ví dụ
            # log_fn=lambda run, frm, to, reason, at: session.add(
            #     RunLog(run_id=run.id, from_status=frm, to_status=to,
            #            reason=reason, created_at=at)
            # )

    Returns:
        Chính đối tượng `run` đã được cập nhật `status`, để tiện dùng theo
        kiểu fluent, ví dụ:
        `run = transition(run, RunStatus.RUNNING, "worker bắt đầu chạy")`.

    Raises:
        ValueError: nếu `reason` rỗng hoặc chỉ toàn khoảng trắng.
        InvalidTransitionError: nếu không có phép chuyển từ trạng thái hiện
            tại của `run` sang `to` theo bảng TRANSITIONS.
    """
    if not reason or not reason.strip():
        raise ValueError("reason không được để trống khi chuyển trạng thái run.")

    from_status = RunStatus(run.status)
    to_status = RunStatus(to)

    if not can_transition(from_status, to_status):
        raise InvalidTransitionError(from_status, to_status, getattr(run, "id", None))

    at = datetime.now(UTC)
    run.status = to_status

    if log_fn is not None:
        log_fn(run, from_status, to_status, reason, at)

    return run
