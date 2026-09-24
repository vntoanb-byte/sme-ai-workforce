"""
Kiểm thử bộ biên dịch mô tả công việc thành quy trình

Dùng FakeLLMProvider tự viết trong file này — hiện thực đúng Protocol LLMProvider
ở app/ports/llm.py và trả về các LLMResult giả lập đã chuẩn bị sẵn theo từng ca
test. TUYỆT ĐỐI không gọi mạng/API mô hình thật.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.compiler import (
    PROMPT_VERSION,
    classify_intent,
    extract_params,
)
from app.domain.compiler import (
    compile as compile_spec,
)
from app.ports.llm import LLMResult, LLMTimeout
from app.schemas.workflow_spec import WorkflowSpec


class FakeLLMProvider:
    """LLMProvider giả lập — trả kết quả đã chuẩn bị sẵn theo thứ tự, ghi lại lời gọi."""

    def __init__(self, results: list[LLMResult]) -> None:
        self._results = list(results)
        self.call_count = 0
        self.schemas: list[dict[str, Any] | None] = []
        self.messages_list: list[list[dict[str, Any]]] = []

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        images: Sequence[bytes] | None = None,
        timeout: float | None = None,
    ) -> LLMResult:
        self.call_count += 1
        self.schemas.append(schema)
        self.messages_list.append(list(messages))
        return self._results.pop(0)


class RaisingLLMProvider:
    """LLMProvider giả lập — lần đầu trả kết quả, các lần sau luôn raise lỗi tầng LLM."""

    def __init__(self, classify_result: LLMResult, exc: Exception) -> None:
        self._classify_result = classify_result
        self._exc = exc
        self.call_count = 0

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        images: Sequence[bytes] | None = None,
        timeout: float | None = None,
    ) -> LLMResult:
        self.call_count += 1
        if self.call_count == 1:
            return self._classify_result
        raise self._exc


def _llm_result(parsed: dict[str, Any] | None, content: str = "") -> LLMResult:
    return LLMResult(
        content=content,
        parsed=parsed,
        model="fake-model",
        token_in=0,
        token_out=0,
        latency_ms=0,
    )


def _tool(
    is_enabled: bool = True,
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    required_params: list[str] | None = None,
) -> dict:
    return {
        "is_enabled": is_enabled,
        "input_schema": input_schema,
        "output_schema": output_schema,
        "required_params": required_params or [],
    }


# Fake tools giống hệt convention test_validators.py: duck-typed dict với
# is_enabled/input_schema/output_schema/required_params.
TOOLS = {
    "doc.read": _tool(
        output_schema={"properties": {"raw_text": {}}},
        required_params=["duong_dan_thu_muc"],
    ),
    "doc.classify": _tool(
        input_schema={"required": ["raw_text"], "properties": {"raw_text": {}}}
    ),
}

# Spec hợp lệ với TOOLS bên trên (qua được cả 5 phép V-1..V-5).
VALID_SPEC_DICT = {
    "template_code": "doc_classify",
    "name": "Đọc và phân loại hoá đơn",
    "description": None,
    "trigger": {"type": "manual"},
    "steps": [
        {
            "step_key": "doc_in",
            "tool_code": "doc.read",
            "config": {"duong_dan_thu_muc": "/data"},
        },
        {"step_key": "doc_out", "tool_code": "doc.classify", "config": {}},
    ],
    "edges": [{"from_key": "doc_in", "to_key": "doc_out"}],
}

# Spec dùng tool không tồn tại — validate_spec báo V-1 ở mọi lần thử.
INVALID_SPEC_DICT = {
    "template_code": "doc_classify",
    "name": "Quy trình lỗi",
    "trigger": {"type": "manual"},
    "steps": [{"step_key": "step_a", "tool_code": "tool.khong_ton_tai", "config": {}}],
    "edges": [],
}
# --- classify_intent ---------------------------------------------------------


def test_classify_intent_returns_template_code():
    llm = FakeLLMProvider([_llm_result({"template_code": "doc_classify"})])
    code = classify_intent("Đọc hoá đơn mua vào rồi phân loại theo loại", llm)
    assert code == "doc_classify"
    assert llm.call_count == 1
    # Schema yêu cầu phải ràng buộc đúng 5 mã mẫu.
    schema = llm.schemas[0]
    assert schema is not None
    assert schema["properties"]["template_code"]["enum"] == [
        "doc_classify",
        "excel_clean",
        "excel_reconcile",
        "invoice_report",
        "invoice_to_excel",
    ]


def test_classify_intent_returns_none_for_code_outside_five():
    llm = FakeLLMProvider([_llm_result({"template_code": "make_coffee"})])
    assert classify_intent("Pha cà phê buổi sáng", llm) is None


def test_classify_intent_returns_none_when_no_parsed():
    llm = FakeLLMProvider([_llm_result(None, content="mô hình không trả JSON")])
    assert classify_intent("Đọc hoá đơn", llm) is None


# --- extract_params ----------------------------------------------------------


def test_extract_params_uses_workflow_spec_schema():
    llm = FakeLLMProvider([_llm_result(VALID_SPEC_DICT)])
    extract_params("Đọc hoá đơn", "doc_classify", llm)
    assert llm.schemas[0] == WorkflowSpec.json_schema()


def test_extract_params_attaches_previous_errors_to_messages():
    llm = FakeLLMProvider([_llm_result(VALID_SPEC_DICT)])
    spec = extract_params(
        "Đọc hoá đơn", "doc_classify", llm, previous_errors=["Lỗi 1", "Lỗi 2"]
    )
    assert spec.template_code == "doc_classify"
    messages = llm.messages_list[0]
    assert messages[-1]["role"] == "user"
    assert "Lỗi 1" in messages[-1]["content"]
    assert "Lỗi 2" in messages[-1]["content"]


def test_extract_params_skips_errors_message_when_none():
    llm = FakeLLMProvider([_llm_result(VALID_SPEC_DICT)])
    extract_params("Đọc hoá đơn", "doc_classify", llm)
    messages = llm.messages_list[0]
    assert messages[-1] == {"role": "user", "content": "Đọc hoá đơn"}


def test_extract_params_raises_on_bad_structure():
    bad = {"template_code": "doc_classify", "name": "", "trigger": {}, "steps": []}
    llm = FakeLLMProvider([_llm_result(bad)])
    with pytest.raises(ValidationError):
        extract_params("Đọc hoá đơn", "doc_classify", llm)


# --- compile -----------------------------------------------------------------


def test_compile_returns_valid_spec_on_first_try():
    llm = FakeLLMProvider(
        [_llm_result({"template_code": "doc_classify"}), _llm_result(VALID_SPEC_DICT)]
    )
    spec, errors = compile_spec(
        "Đọc hoá đơn mua vào, kiểm tra rồi ghi vào Excel", llm, TOOLS
    )
    assert errors == []
    assert spec is not None
    assert spec.template_code == "doc_classify"
    assert [s.step_key for s in spec.steps] == ["doc_in", "doc_out"]
    assert llm.call_count == 2  # 1 phân loại + 1 điền tham số
    assert llm.schemas[1] == WorkflowSpec.json_schema()


def test_compile_retries_three_times_then_returns_last_draft_with_errors():
    llm = FakeLLMProvider(
        [
            _llm_result({"template_code": "doc_classify"}),
            _llm_result(INVALID_SPEC_DICT),
            _llm_result(INVALID_SPEC_DICT),
            _llm_result(INVALID_SPEC_DICT),
        ]
    )
    spec, errors = compile_spec("Đọc hoá đơn", llm, TOOLS)
    # 1 phân loại + đúng 3 lần điền tham số — không có vòng lặp vô hạn.
    assert llm.call_count == 4
    assert spec is not None
    assert [s.tool_code for s in spec.steps] == ["tool.khong_ton_tai"]
    assert len(errors) == 1
    assert errors[0].rule == "V-1"
    assert errors[0].step_key == "step_a"
    # Từ lần gọi thứ 3 (index 2) trở đi, lỗi lần trước được đính kèm vào prompt.
    retry_messages = llm.messages_list[2]
    assert retry_messages[-1]["role"] == "user"
    assert "tool.khong_ton_tai" in retry_messages[-1]["content"]


def test_compile_returns_compile_0_when_intent_unknown():
    llm = FakeLLMProvider([_llm_result({"template_code": "make_coffee"})])
    spec, errors = compile_spec("Pha cà phê mỗi sáng", llm, TOOLS)
    assert spec is None
    assert len(errors) == 1
    assert errors[0].rule == "COMPILE-0"
    assert errors[0].step_key is None
    assert llm.call_count == 1  # không đi tiếp tới extract_params


def test_compile_returns_compile_1_when_llm_layer_always_fails():
    llm = RaisingLLMProvider(
        _llm_result({"template_code": "doc_classify"}),
        LLMTimeout("Máy chủ mô hình không phản hồi"),
    )
    spec, errors = compile_spec("Đọc hoá đơn", llm, TOOLS)
    assert llm.call_count == 4  # 1 phân loại + 3 lần thử đều lỗi tầng mô hình
    assert spec is None
    assert len(errors) == 1
    assert errors[0].rule == "COMPILE-1"
    assert errors[0].step_key is None


def test_compile_recovers_after_pydantic_validation_error():
    llm = FakeLLMProvider(
        [
            _llm_result({"template_code": "doc_classify"}),
            _llm_result(None),  # parsed=None -> model_validate(None) -> ValidationError
            _llm_result(VALID_SPEC_DICT),
        ]
    )
    spec, errors = compile_spec("Đọc hoá đơn", llm, TOOLS)
    assert errors == []
    assert spec is not None
    assert spec.template_code == "doc_classify"
    assert llm.call_count == 3


def test_compile_returns_compile_2_when_structure_always_invalid():
    # Cả 3 lần điền tham số đều lỗi cấu trúc Pydantic (parsed=None), không lần
    # nào parse thành công -> spec phải là None, KHÔNG được trả (None, []) vì
    # errors=[] dễ bị hiểu nhầm là "hợp lệ, không có lỗi".
    llm = FakeLLMProvider(
        [
            _llm_result({"template_code": "doc_classify"}),
            _llm_result(None),
            _llm_result(None),
            _llm_result(None),
        ]
    )
    spec, errors = compile_spec("Đọc hoá đơn", llm, TOOLS)
    assert llm.call_count == 4  # 1 phân loại + 3 lần thử đều lỗi cấu trúc
    assert spec is None
    assert len(errors) == 1
    assert errors[0].rule == "COMPILE-2"
    assert errors[0].step_key is None


def test_prompt_version_is_set():
    assert isinstance(PROMPT_VERSION, str) and bool(PROMPT_VERSION)

def test_classify_prompt_lists_all_templates_with_examples():
    llm = FakeLLMProvider([_llm_result({"template_code": "excel_clean"})])
    classify_intent("Gộp các file Excel", llm)
    system = llm.messages_list[0][0]["content"]
    for code in ("invoice_to_excel", "invoice_report", "excel_clean", "excel_reconcile",
                 "doc_classify"):
        assert code in system
    assert "ví dụ" in system


def test_extract_prompt_contains_template_skeleton_and_hints():
    llm = FakeLLMProvider([_llm_result(VALID_SPEC_DICT)])
    extract_params(
        "Đọc hoá đơn", "invoice_to_excel", llm, hints={"thư mục quét": "/mnt/scan"}
    )
    system = llm.messages_list[0][0]["content"]
    assert "fs.list_new_files" in system and "xlsx.append_rows" in system
    assert "/mnt/scan" in system
