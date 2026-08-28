"""
Kiểm thử bộ kiểm chứng quy trình

Mỗi phép V-1..V-5 cần ca phát hiện được lỗi tương ứng, và ca hợp lệ tương ứng
để chắc chắn không báo lỗi giả (false positive).

  V-3: dựng đồ thị có chu trình và xác nhận bị từ chối (yêu cầu gốc của file
  này trước khi validators.py được hiện thực).
"""

from __future__ import annotations

from app.domain.validators import validate_spec
from app.schemas.workflow_spec import EdgeSpec, StepSpec, TriggerSpec, WorkflowSpec

MANUAL_TRIGGER = TriggerSpec(type="manual")


def _spec(
    steps: list[StepSpec],
    edges: list[EdgeSpec] | None = None,
    trigger: TriggerSpec | None = None,
) -> WorkflowSpec:
    return WorkflowSpec(
        template_code="doc_classify",
        name="Quy trình kiểm thử",
        trigger=trigger or MANUAL_TRIGGER,
        steps=steps,
        edges=edges or [],
    )


def _step(step_key: str, tool_code: str = "doc.read", config: dict | None = None) -> StepSpec:
    return StepSpec(step_key=step_key, tool_code=tool_code, config=config or {})


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


# --- V-1: tool_code phải tồn tại và is_enabled=True ---------------------


def test_v1_tool_not_found():
    spec = _spec([_step("step_a", tool_code="tool.khong_ton_tai")])
    errors = validate_spec(spec, tools={})
    assert any(e.rule == "V-1" and e.step_key == "step_a" for e in errors)


def test_v1_tool_disabled():
    spec = _spec([_step("step_a", tool_code="tool.tat")])
    errors = validate_spec(spec, tools={"tool.tat": _tool(is_enabled=False)})
    assert any(e.rule == "V-1" and e.step_key == "step_a" for e in errors)


def test_v1_passes_when_tool_enabled():
    spec = _spec([_step("step_a", tool_code="tool.on")])
    errors = validate_spec(spec, tools={"tool.on": _tool(is_enabled=True)})
    assert not any(e.rule == "V-1" for e in errors)


# --- V-2: step_key duy nhất, cạnh trỏ tới bước có thật -------------------


def test_v2_duplicate_step_key():
    spec = _spec([_step("step_a"), _step("step_a")])
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert any(e.rule == "V-2" and "lặp lại" in e.message for e in errors)


def test_v2_edge_points_to_missing_step():
    spec = _spec(
        [_step("step_a")],
        edges=[EdgeSpec(from_key="step_a", to_key="b_khong_ton_tai")],
    )
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert any(e.rule == "V-2" and e.step_key == "b_khong_ton_tai" for e in errors)


def test_v2_passes_when_edges_valid():
    spec = _spec(
        [_step("step_a"), _step("step_b")],
        edges=[EdgeSpec(from_key="step_a", to_key="step_b")],
    )
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert not any(e.rule == "V-2" for e in errors)


# --- V-3: đồ thị không được có chu trình ----------------------------------


def test_v3_cycle_detected():
    spec = _spec(
        [_step("step_a"), _step("step_b"), _step("step_c")],
        edges=[
            EdgeSpec(from_key="step_a", to_key="step_b"),
            EdgeSpec(from_key="step_b", to_key="step_c"),
            EdgeSpec(from_key="step_c", to_key="step_a"),  # đóng vòng
        ],
    )
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert any(e.rule == "V-3" for e in errors)


def test_v3_passes_when_acyclic():
    spec = _spec(
        [_step("step_a"), _step("step_b"), _step("step_c")],
        edges=[
            EdgeSpec(from_key="step_a", to_key="step_b"),
            EdgeSpec(from_key="step_b", to_key="step_c"),
        ],
    )
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert not any(e.rule == "V-3" for e in errors)


# --- V-4: output_schema bước trước tương thích input_schema bước sau -----


def test_v4_schema_mismatch():
    spec = _spec(
        [
            _step("step_a", tool_code="doc.read"),
            _step("step_b", tool_code="doc.classify"),
        ],
        edges=[EdgeSpec(from_key="step_a", to_key="step_b")],
    )
    tools = {
        "doc.read": _tool(output_schema={"properties": {"raw_text": {}}}),
        "doc.classify": _tool(
            input_schema={"required": ["image_bytes"], "properties": {"image_bytes": {}}}
        ),
    }
    errors = validate_spec(spec, tools)
    assert any(e.rule == "V-4" and e.step_key == "step_b" for e in errors)


def test_v4_passes_when_compatible():
    spec = _spec(
        [
            _step("step_a", tool_code="doc.read"),
            _step("step_b", tool_code="doc.classify"),
        ],
        edges=[EdgeSpec(from_key="step_a", to_key="step_b")],
    )
    tools = {
        "doc.read": _tool(output_schema={"properties": {"raw_text": {}}}),
        "doc.classify": _tool(
            input_schema={"required": ["raw_text"], "properties": {"raw_text": {}}}
        ),
    }
    errors = validate_spec(spec, tools)
    assert not any(e.rule == "V-4" for e in errors)


def test_v4_skips_when_schema_missing():
    # Chưa có lược đồ để so sánh -> không đủ căn cứ kết luận, không báo lỗi giả.
    spec = _spec(
        [_step("step_a"), _step("step_b")],
        edges=[EdgeSpec(from_key="step_a", to_key="step_b")],
    )
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert not any(e.rule == "V-4" for e in errors)


# --- V-5: trigger hợp lệ + tham số bắt buộc của tool ----------------------


def test_v5_invalid_cron():
    spec = _spec([_step("step_a")], trigger=TriggerSpec(type="cron", cron_expr="not a cron"))
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert any(e.rule == "V-5" for e in errors)


def test_v5_valid_cron_passes():
    spec = _spec([_step("step_a")], trigger=TriggerSpec(type="cron", cron_expr="*/5 * * * *"))
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert not any(e.rule == "V-5" for e in errors)


def test_v5_file_watch_missing_dir():
    spec = _spec(
        [_step("step_a")],
        trigger=TriggerSpec(type="file_watch", watch_path="C:/duong_dan_khong_ton_tai_xyz"),
    )
    tools = {"doc.read": _tool()}
    errors = validate_spec(spec, tools)
    assert any(e.rule == "V-5" for e in errors)


def test_v5_missing_required_param():
    spec = _spec([_step("step_a", tool_code="doc.read", config={})])
    tools = {"doc.read": _tool(required_params=["duong_dan_thu_muc"])}
    errors = validate_spec(spec, tools)
    assert any(e.rule == "V-5" and e.step_key == "step_a" for e in errors)


def test_v5_required_param_present_passes():
    spec = _spec([_step("step_a", tool_code="doc.read", config={"duong_dan_thu_muc": "/data"})])
    tools = {"doc.read": _tool(required_params=["duong_dan_thu_muc"])}
    errors = validate_spec(spec, tools)
    assert not any(e.rule == "V-5" for e in errors)


# --- Toàn bộ spec hợp lệ -> không có lỗi nào ------------------------------


def test_validate_spec_fully_valid_returns_empty():
    spec = _spec(
        [
            _step("doc_in", tool_code="doc.read"),
            _step("doc_out", tool_code="doc.classify"),
        ],
        edges=[EdgeSpec(from_key="doc_in", to_key="doc_out")],
    )
    tools = {
        "doc.read": _tool(output_schema={"properties": {"raw_text": {}}}),
        "doc.classify": _tool(
            input_schema={"required": ["raw_text"], "properties": {"raw_text": {}}}
        ),
    }
    errors = validate_spec(spec, tools)
    assert errors == []
