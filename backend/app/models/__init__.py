"""
models

Nạp mọi model SQLAlchemy (7 nhóm bảng) — import gói này (hoặc app.db.base)
là đủ để Base.metadata có toàn bộ bảng.
"""

from app.models.artifact import Artifact, Document
from app.models.audit import AuditLog, LlmCall, Setting
from app.models.employee import AIEmployee, Schedule
from app.models.extraction import Extraction, HumanReview, QCResult
from app.models.run import JobQueueEntry, Run, RunLog, RunStep
from app.models.user import RefreshToken, Role, User, user_roles
from app.models.workflow import Tool, Workflow, WorkflowEdge, WorkflowStep

__all__ = [
    "AIEmployee", "Artifact", "AuditLog", "Document", "Extraction", "HumanReview",
    "JobQueueEntry", "LlmCall", "QCResult", "RefreshToken", "Role", "Run", "RunLog",
    "RunStep", "Schedule", "Setting", "Tool", "User", "Workflow", "WorkflowEdge",
    "WorkflowStep", "user_roles",
]
