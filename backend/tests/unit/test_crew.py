"""Kiểm thử agents/crew.py — tuần tự, đúng thứ tự, giới hạn phạm vi công cụ."""

from __future__ import annotations

import pytest

from app.agents.crew import (
    DATA_AGENT,
    DOC_AGENT,
    QC_AGENT,
    StepPlan,
    agent_for,
    build_crew,
)
from app.core.errors import ValidationFailed


def test_agent_scopes() -> None:
    assert agent_for("fs.list_new_files") is DOC_AGENT
    assert agent_for("vision.extract_invoice") is DOC_AGENT
    assert agent_for("doc.render_pdf") is DOC_AGENT
    assert agent_for("xlsx.append_rows") is DATA_AGENT
    assert agent_for("report.build_pdf") is DATA_AGENT
    assert agent_for("qc.validate_invoice") is QC_AGENT
    assert not QC_AGENT.allows("xlsx.append_rows")
    with pytest.raises(ValidationFailed):
        agent_for("shell.exec")


def test_build_crew_keeps_validated_order() -> None:
    crew = build_crew(
        [
            StepPlan("scan", "fs.list_new_files", {"path": "x"}),
            StepPlan("read", "vision.extract_invoice", {}),
            StepPlan("check", "qc.validate_invoice", {}),
        ]
    )
    assert crew.process == "sequential"
    assert [t.step_key for t in crew.tasks] == ["scan", "read", "check"]
    assert [t.agent.key for t in crew.tasks] == ["doc", "doc", "qc"]
    assert crew.task("read").tool.code == "vision.extract_invoice"


def test_unknown_tool_rejected_before_running() -> None:
    with pytest.raises(ValidationFailed):
        build_crew([StepPlan("x", "email.send", {})])
