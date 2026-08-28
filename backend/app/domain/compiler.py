"""
Bộ biên dịch mô tả công việc thành quy trình

ĐÓNG GÓP CHÍNH CỦA ĐỀ TÀI. Chuyển câu tiếng Việt người dùng gõ thành
WorkflowSpec. Nguyên tắc: KHÔNG dùng vòng lặp tác tử tự chủ (ADR-002). Quy giản
bài toán lập kế hoạch thành hai bài toán dễ hơn nhiều:

  1. classify_intent — phân loại mô tả vào 1 trong 5 mã mẫu TemplateCode;
  2. extract_params — điền tham số thành WorkflowSpec bằng MỘT lời gọi duy nhất
     có ràng buộc theo WorkflowSpec.json_schema().

compile() là hàm public duy nhất, điều phối hai bước trên kèm thử lại tối đa 3
lần: mỗi lần thất bại (lỗi kiểm chứng hoặc lỗi cấu trúc Pydantic) đều đính kèm
thông báo lỗi cụ thể của lần trước vào prompt cho lần gọi tiếp theo.

Ghi chú phiên bản prompt: mỗi khi đổi nội dung message gửi mô hình thì tăng
PROMPT_VERSION và ghi log kèm version để về sau so sánh được giữa các phiên bản
prompt (không thêm field prompt_version vào WorkflowSpec — model đó có
model_config extra="forbid").
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast, get_args

import structlog
from pydantic import ValidationError

from app.domain.validators import SpecError, validate_spec
from app.ports.llm import LLMInvalidOutput, LLMProvider, LLMTimeout, LLMUnavailable
from app.schemas.workflow_spec import TemplateCode, WorkflowSpec

# Phiên bản prompt gửi mô hình. Tăng lên mỗi khi đổi nội dung message ở các hàm
# classify_intent/extract_params bên dưới.
PROMPT_VERSION = "v1"

# Số lần thử tối đa của khâu điền tham số trong compile().
MAX_COMPILE_ATTEMPTS = 3

logger = structlog.get_logger(__name__)

# Tập 5 mã mẫu hợp lệ — suy trực tiếp từ Literal TemplateCode, không duyệt danh
# sách thứ hai để tránh lệch khi schema đổi.
_VALID_TEMPLATE_CODES = set(get_args(TemplateCode))

# Schema ràng buộc kết quả phân loại là MỘT trong 5 mã mẫu. Bọc trong object vì
# adapter thật (adapters/llm_openai_compatible.py) yêu cầu guided_json trả về
# JSON object chứ không phải giá trị trần.
_CLASSIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "template_code": {
            "type": "string",
            "enum": list(get_args(TemplateCode)),
        },
    },
    "required": ["template_code"],
    "additionalProperties": False,
}

_COMPILE_0_MESSAGE = (
    "Không xác định được loại quy trình phù hợp với mô tả này. Hãy mô tả cụ thể hơn, "
    "ví dụ nêu rõ công việc là đọc hoá đơn, xử lý bảng tính, hay đối chiếu dữ liệu."
)

_COMPILE_1_MESSAGE = (
    "Không gọi được mô hình ngôn ngữ sau 3 lần thử. Hãy kiểm tra kết nối mạng, địa "
    "chỉ máy chủ mô hình và cấu hình LLM, rồi thử lại sau."
)

_COMPILE_2_MESSAGE = (
    "Mô hình liên tục trả về kết quả không đúng cấu trúc quy trình sau 3 lần thử. "
    "Hãy thử mô tả công việc theo cách khác, cụ thể hơn."
)


def classify_intent(text: str, llm: LLMProvider) -> TemplateCode | None:
    """Phân loại mô tả công việc vào 1 trong 5 mã mẫu TemplateCode.

    Gọi llm.complete với schema ràng buộc kết quả là một trong 5 mã mẫu. Trả về
    None khi mô hình không khớp mẫu nào hoặc trả giá trị ngoài 5 mã — không
    raise lỗi kỹ thuật ra ngoài (lỗi tầng LLM do chính llm.complete ném, tầng
    trên chịu trách nhiệm bắt).
    """
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "Bạn là bộ phận phân loại quy trình của hệ thống nhân viên AI cho "
                "doanh nghiệp nhỏ. Đọc mô tả công việc bằng tiếng Việt của người "
                "dùng và chọn đúng MỘT mẫu quy trình phù hợp nhất trong danh sách 5 "
                "mẫu. Trả về JSON theo schema yêu cầu, không thêm giải thích."
            ),
        },
        {"role": "user", "content": text},
    ]
    result = llm.complete(messages, schema=_CLASSIFY_SCHEMA)
    if result.parsed is None:
        return None
    code = result.parsed.get("template_code")
    if code not in _VALID_TEMPLATE_CODES:
        return None
    return cast(TemplateCode, code)


def extract_params(
    text: str,
    template_code: TemplateCode,
    llm: LLMProvider,
    *,
    previous_errors: list[str] | None = None,
) -> WorkflowSpec:
    """Điền tham số của mẫu `template_code` thành WorkflowSpec.

    MỘT lời gọi mô hình duy nhất, đầu ra bị ràng buộc bằng
    WorkflowSpec.json_schema() — không có vòng lặp bên trong hàm này (vòng lặp
    thử lại nằm ở compile()). Nếu `previous_errors` có giá trị (lỗi của lần thử
    trước), chúng được đính kèm rõ ràng vào message để mô hình sửa ở lần gọi
    tiếp theo.

    Raises:
        ValidationError: kết quả không khớp cấu trúc WorkflowSpec — lỗi này để
            nổi lên cho compile() xử lý retry, không tự nuốt ở đây.
    """
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                f"Bạn là bộ điền tham số quy trình. Mô tả công việc đã được phân loại "
                f"vào mẫu quy trình '{template_code}'. Hãy điền đầy đủ thông tin thành "
                "WorkflowSpec theo đúng JSON schema yêu cầu: đặt tên ngắn gọn, chọn "
                "trigger phù hợp (ưu tiên manual nếu mô tả không nói rõ lịch chạy), "
                "dựng các bước và cạnh nối đúng tinh thần của mẫu. Trả về JSON khớp "
                "schema, không thêm giải thích."
            ),
        },
        {"role": "user", "content": text},
    ]
    if previous_errors:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Lần thử trước gặp các lỗi sau, hãy sửa lại WorkflowSpec cho khớp: "
                    + "\n".join(previous_errors)
                ),
            }
        )
    result = llm.complete(messages, schema=WorkflowSpec.json_schema())
    return WorkflowSpec.model_validate(result.parsed)


def compile(
    text: str,
    llm: LLMProvider,
    tools: Mapping[str, Any],
) -> tuple[WorkflowSpec | None, list[SpecError]]:
    """Biên dịch mô tả tiếng Việt thành WorkflowSpec — hàm public duy nhất.

    Luồng: classify_intent → extract_params → validate_spec, thử lại tối đa 3
    lần. Trả về (spec, errors):

    - spec hợp lệ, errors=[]: xong ngay lần đầu hoặc sau khi sửa lỗi.
    - spec=None, [COMPILE-0]: không phân loại được ý định.
    - spec=None, [COMPILE-1]: cả 3 lần thử đều lỗi tầng mô hình.
    - spec là bản nháp cuối, errors là lỗi kiểm chứng của lần đó: hết 3 lần vẫn
      còn lỗi kiểm chứng — caller còn thấy được bản nháp gần đúng nhất.
    """
    template_code = classify_intent(text, llm)
    logger.info(
        "compiler.classify_intent",
        prompt_version=PROMPT_VERSION,
        template_code=template_code,
        attempt=1,
    )
    if template_code is None:
        return None, [
            SpecError(rule="COMPILE-0", step_key=None, message=_COMPILE_0_MESSAGE)
        ]

    previous_errors: list[str] | None = None
    last_spec: WorkflowSpec | None = None
    last_errors: list[SpecError] = []
    llm_failures = 0

    # NOTE (suy luận, cần Owner xác nhận): log structlog được đặt ở điểm gọi trong
    # compile() (nơi duy nhất biết "lần thử thứ mấy") thay vì bên trong từng hàm,
    # để giữ nguyên chữ ký classify_intent/extract_params theo TASK-002. Nếu muốn
    # mỗi hàm tự log với attempt thật, cần thêm tham số attempt cho extract_params.
    for attempt in range(1, MAX_COMPILE_ATTEMPTS + 1):
        logger.info(
            "compiler.extract_params",
            prompt_version=PROMPT_VERSION,
            template_code=template_code,
            attempt=attempt,
        )
        try:
            spec = extract_params(
                text, template_code, llm, previous_errors=previous_errors
            )
        except (LLMTimeout, LLMInvalidOutput, LLMUnavailable) as exc:
            # Lỗi tầng mô hình — ghi chi tiết để vận hành, còn message trả về
            # người dùng là COMPILE-1 (không phải traceback). Giữ nguyên
            # previous_errors của lần trước (nếu có): đó vẫn là tín hiệu hữu ích
            # nhất cho lần gọi tiếp theo.
            logger.warning(
                "compiler.extract_params_llm_error",
                prompt_version=PROMPT_VERSION,
                template_code=template_code,
                attempt=attempt,
                error=str(exc),
            )
            llm_failures += 1
            continue
        except ValidationError as exc:
            # Lỗi cấu trúc Pydantic — gom message để gửi lại cho mô hình sửa.
            # Đồng thời cập nhật last_errors: nếu đây là lần thử CUỐI cùng và
            # chưa lần nào parse thành công (last_spec vẫn None), fallback ở
            # cuối hàm phải trả về lỗi rõ ràng thay vì (None, []) — trường hợp
            # (None, []) dễ bị caller hiểu nhầm là "hợp lệ, không có lỗi".
            previous_errors = [str(exc)]
            last_errors = [
                SpecError(rule="COMPILE-2", step_key=None, message=_COMPILE_2_MESSAGE)
            ]
            continue

        last_spec = spec
        last_errors = validate_spec(spec, tools)
        if not last_errors:
            return spec, []
        previous_errors = [err.message for err in last_errors]

    if llm_failures == MAX_COMPILE_ATTEMPTS:
        return None, [
            SpecError(rule="COMPILE-1", step_key=None, message=_COMPILE_1_MESSAGE)
        ]
    # last_spec là bản nháp của lần thử cuối cùng tạo được spec (không phải None
    # khi có ít nhất một lần extract_params parse thành công) — kèm đúng lỗi
    # kiểm chứng của chính lần đó.
    return last_spec, last_errors

