"""
Lược đồ đặc tả quy trình

Định nghĩa Pydantic cho WorkflowSpec. Đây vừa là hợp đồng dữ liệu giữa mô hình
và hệ thống, vừa là ràng buộc truyền cho cơ chế sinh có ràng buộc của máy chủ
suy luận.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# NOTE (suy luận, chưa được Owner xác nhận): 5 mã mẫu dưới đây được suy ra từ
# tên 5 tệp trong backend/app/domain/templates/ (doc_classify.py,
# excel_clean.py, excel_reconcile.py, invoice_report.py,
# invoice_to_excel.py). Các tệp mẫu và registry.py hiện vẫn là docstring
# stub, chưa khai báo TEMPLATE.code thật, nên đây KHÔNG phải fact đã kiểm
# chứng — chỉ là suy luận hợp lý từ quy ước đặt tên. Khi registry.py và các
# tệp mẫu được hiện thực, cần đối chiếu lại giá trị Literal này với
# WorkflowTemplate.code thật và cập nhật nếu lệch.
TemplateCode = Literal[
    "doc_classify",
    "excel_clean",
    "excel_reconcile",
    "invoice_report",
    "invoice_to_excel",
]

# Khoá bước dùng chung cho StepSpec.step_key và EdgeSpec.from_key/to_key.
_STEP_KEY_PATTERN = r"^[a-z][a-z0-9_]{1,30}$"
StepKey = Annotated[str, Field(pattern=_STEP_KEY_PATTERN)]


class TriggerSpec(BaseModel):
    """Điều kiện kích hoạt quy trình.

    type=manual: chạy thủ công, không cần cron_expr/watch_path.
    type=cron: cần cron_expr (và nên có timezone).
    type=file_watch: cần watch_path (thư mục theo dõi tệp mới).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["manual", "cron", "file_watch"]
    cron_expr: str | None = Field(
        default=None,
        description="Biểu thức cron, bắt buộc khi type='cron'. Cú pháp được "
        "kiểm chứng đầy đủ ở domain/validators.py (V-5), không phải ở đây.",
    )
    watch_path: str | None = Field(
        default=None,
        description="Thư mục cần theo dõi, bắt buộc khi type='file_watch'. "
        "Sự tồn tại của thư mục được kiểm chứng ở domain/validators.py (V-5).",
    )
    timezone: str | None = Field(
        default=None,
        description="Múi giờ áp dụng cho cron_expr, ví dụ 'Asia/Ho_Chi_Minh'.",
    )

    @model_validator(mode="after")
    def _check_required_fields_by_type(self) -> "TriggerSpec":
        """Bảo đảm tính nhất quán cấu trúc tối thiểu theo từng loại trigger.

        Đây là ràng buộc cấu trúc (structural), không phải kiểm chứng ngữ
        nghĩa/nghiệp vụ — phần đó thuộc domain/validators.py (V-5).
        """
        if self.type == "cron" and not self.cron_expr:
            raise ValueError("trigger.cron_expr là bắt buộc khi type='cron'")
        if self.type == "file_watch" and not self.watch_path:
            raise ValueError(
                "trigger.watch_path là bắt buộc khi type='file_watch'"
            )
        return self


class StepSpec(BaseModel):
    """Một bước xử lý trong quy trình.

    tool_code không giới hạn bằng Literal vì danh mục công cụ được nạp động
    từ bảng `tools` (xem app/tools/base.py) — schemas/ không được phép phụ
    thuộc vào lớp adapters/DB. Việc tool_code có tồn tại và is_enabled=True
    hay không được kiểm chứng ở domain/validators.py (V-1).
    """

    model_config = ConfigDict(extra="forbid")

    step_key: StepKey = Field(
        description="Định danh bước, duy nhất trong quy trình, dạng snake_case."
    )
    tool_code: str = Field(
        min_length=1,
        description="Mã công cụ áp dụng cho bước này (đối chiếu bảng tools).",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Tham số cấu hình truyền cho công cụ ở bước này.",
    )
    # NOTE (suy luận): docstring gốc không liệt kê tập giá trị hợp lệ của
    # on_error. Ba giá trị dưới đây (stop/skip/retry) là suy luận hợp lý dựa
    # trên retry_max đi kèm — cần Owner xác nhận lại.
    on_error: Literal["stop", "skip", "retry"] = Field(
        default="stop",
        description="Hành vi khi bước này lỗi: dừng quy trình, bỏ qua bước, "
        "hoặc thử lại.",
    )
    retry_max: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Số lần thử lại tối đa khi bước lỗi (chỉ có ý nghĩa khi "
        "on_error='retry').",
    )


class EdgeSpec(BaseModel):
    """Một cạnh nối hai bước trong đồ thị quy trình."""

    model_config = ConfigDict(extra="forbid")

    from_key: StepKey
    to_key: StepKey
    # NOTE (suy luận): condition để dạng chuỗi tự do (vd. "success",
    # "needs_review") thay vì Literal cố định, vì tập điều kiện phụ thuộc
    # từng mẫu quy trình và chưa có danh mục chốt trong docstring gốc.
    # None nghĩa là cạnh vô điều kiện.
    condition: str | None = Field(
        default=None,
        description="Điều kiện đi theo cạnh này; None nghĩa là luôn đi qua.",
    )


class WorkflowSpec(BaseModel):
    """Đặc tả đầy đủ một quy trình do bộ biên dịch (domain/compiler.py) sinh ra.

    Đây là ràng buộc truyền cho tham số guided_json của máy chủ suy luận —
    model_config extra='forbid' áp dụng cho toàn bộ cây lược đồ (kể cả các
    lớp lồng bên trên) để chặn mô hình bịa thêm trường.
    """

    model_config = ConfigDict(extra="forbid")

    template_code: TemplateCode
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    trigger: TriggerSpec
    steps: list[StepSpec] = Field(min_length=1)
    edges: list[EdgeSpec] = Field(default_factory=list)

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """Trả về JSON Schema của WorkflowSpec.

        Dùng làm giá trị cho tham số guided_json khi gọi máy chủ suy luận,
        để ràng buộc đầu ra của mô hình khớp đúng cấu trúc WorkflowSpec.
        """
        return cls.model_json_schema()
