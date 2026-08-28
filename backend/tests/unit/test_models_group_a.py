"""
Kiểm thử lược đồ NHÓM A + B + C (TASK-005a)

Bằng chứng quan trọng nhất: Base.metadata.create_all(engine) chạy không lỗi —
lược đồ 9 bảng nhất quán (không FK trỏ sai, composite FK hợp lệ). Test
CASCADE/SET NULL cần PRAGMA foreign_keys=ON — copy đúng 2 event connect/begin
từ app/db/session.py (như test_queue_sqlite.py) thay vì import app.db.session để
không đụng engine/DB thật theo settings.DATABASE_URL. Dùng SQLite FILE trong
tmp_path (không :memory:), đúng convention test_queue_sqlite.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, event, func, inspect, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.employee import AIEmployee, Schedule
from app.models.user import Role, User, user_roles
from app.models.workflow import Tool, Workflow, WorkflowEdge, WorkflowStep


def _register_events(engine) -> None:
    """Copy 2 event trong app/db/session.py — test độc lập, không đụng DB thật."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _do_begin(conn) -> None:
        if conn.get_execution_options().get("sqlite_begin_immediate"):
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            conn.exec_driver_sql("BEGIN")
        # Hoãn kiểm tra FK tới COMMIT — workflow_edges (FK ghép trỏ
        # workflow_steps) và workflow_steps được flush trong cùng 1
        # transaction, thứ tự insert do SQLAlchemy tự quyết.
        conn.exec_driver_sql("PRAGMA defer_foreign_keys=ON")


@pytest.fixture()
def engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'models_a.db').as_posix()}")
    _register_events(engine)
    # BẰNG CHỨNG QUAN TRỌNG NHẤT: lược đồ 9 bảng tạo được, không FK trỏ sai.
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


def test_create_all_creates_all_nine_tables(engine):
    tables = set(inspect(engine).get_table_names())
    assert {
        "users",
        "roles",
        "user_roles",
        "ai_employees",
        "schedules",
        "workflows",
        "workflow_steps",
        "workflow_edges",
        "tools",
    } <= tables


def test_user_role_many_to_many(session):
    user = User(
        username="toan",
        full_name="Nguyễn Văn Toàn",
        email="toan@example.com",
        password_hash="argon2-hash-giả",
    )
    role = Role(code="MANAGER")
    user.roles.append(role)
    session.add(user)
    session.commit()

    session.expire_all()  # đọc lại từ DB thật, không dùng object trong memory

    loaded = session.get(User, user.id)
    assert loaded is not None
    assert [r.code for r in loaded.roles] == ["MANAGER"]

    loaded_role = session.get(Role, role.id)
    assert loaded_role is not None
    assert [u.id for u in loaded_role.users] == [user.id]
def _make_employee() -> AIEmployee:
    return AIEmployee(
        name="Kế toán hoá đơn",
        job_description="Đọc hoá đơn mua vào, kiểm tra rồi ghi vào Excel",
    )


def test_workflow_graph_insert_and_query(session):
    employee = _make_employee()
    session.add(employee)
    session.flush()  # lấy employee.id

    workflow = Workflow(
        employee_id=employee.id,
        version=1,
        status="pending",
        template_code="invoice_to_excel",
        name="Xử lý hoá đơn mua vào",
        description="Mô tả quy trình",
    )
    workflow.steps = [
        WorkflowStep(
            step_key="read_invoice",
            order_index=1,
            tool_code="vision.extract_invoice",
            label="Đọc hoá đơn",
        ),
        WorkflowStep(
            step_key="validate_invoice",
            order_index=2,
            tool_code="qc.validate_invoice",
            label="Kiểm tra QC",
            on_error="retry",
            retry_max=2,
        ),
        WorkflowStep(
            step_key="write_excel",
            order_index=3,
            tool_code="xlsx.append_rows",
            label="Ghi Excel",
        ),
    ]
    workflow.edges = [
        WorkflowEdge(from_key="read_invoice", to_key="validate_invoice"),
        WorkflowEdge(
            from_key="validate_invoice", to_key="write_excel", condition="success"
        ),
    ]
    workflow.schedule = Schedule(
        trigger_type="cron",
        cron_expr="0 8 * * *",
        timezone="Asia/Ho_Chi_Minh",
    )
    session.add(workflow)
    session.commit()

    session.expire_all()

    wf = session.get(Workflow, workflow.id)
    assert wf is not None
    assert wf.employee_id == employee.id
    assert wf.status == "pending"
    assert len(wf.steps) == 3
    assert [s.step_key for s in wf.steps] == [
        "read_invoice",
        "validate_invoice",
        "write_excel",
    ]
    assert len(wf.edges) == 2
    edges = {(e.from_key, e.to_key, e.condition) for e in wf.edges}
    assert ("read_invoice", "validate_invoice", None) in edges
    assert ("validate_invoice", "write_excel", "success") in edges
    assert wf.schedule is not None
    assert wf.schedule.trigger_type == "cron"

    # relationship ngược: employee.workflows chứa workflow vừa tạo.
    emp = session.get(AIEmployee, employee.id)
    assert emp is not None
    assert [w.id for w in emp.workflows] == [workflow.id]


def test_employee_current_workflow_and_tool(session):
    employee = _make_employee()
    session.add(employee)
    session.flush()

    workflow = Workflow(
        employee_id=employee.id,
        version=1,
        template_code="invoice_to_excel",
        name="Quy trình có bước",
    )
    workflow.steps = [
        WorkflowStep(
            step_key="read_invoice",
            order_index=1,
            tool_code="vision.extract_invoice",
            label="Đọc",
        )
    ]
    session.add(workflow)
    session.flush()
    employee.current_workflow_id = workflow.id
    session.add(
        Tool(
            code="fs.list_new_files",
            name="Liệt kê tệp mới",
            category="fs",
            input_schema_json="{}",
            output_schema_json="{}",
        )
    )
    session.commit()

    session.expire_all()

    emp = session.get(AIEmployee, employee.id)
    assert emp is not None
    assert emp.current_workflow is not None
    assert emp.current_workflow.id == workflow.id
    assert emp.created_by is None

    tool = session.execute(
        select(Tool).where(Tool.code == "fs.list_new_files")
    ).scalar_one()
    assert tool.name == "Liệt kê tệp mới"
    assert tool.is_enabled is True
    assert tool.input_schema_json == "{}"
def test_delete_user_cascades_user_roles(session, engine):
    user = User(
        username="toan",
        full_name="Toàn",
        email="toan@example.com",
        password_hash="x",
    )
    user.roles.append(Role(code="ADMIN"))
    session.add(user)
    session.commit()

    session.expire_all()
    # Xoá qua SQL CORE (không qua ORM cascade) để chứng minh ondelete=CASCADE
    # ở tầng DB hoạt động thật với PRAGMA foreign_keys=ON.
    with Session(engine) as s2:
        s2.execute(delete(User).where(User.id == user.id))
        s2.commit()

    # rollback() (không chỉ expire_all()) để kết thúc transaction WAL cũ của
    # session này — nếu không, nó vẫn thấy snapshot TRƯỚC khi s2 xoá+commit
    # (WAL cho mỗi transaction 1 điểm nhìn cố định tới khi tự bắt đầu lại) —
    # đã tự kiểm chứng bằng script độc lập: CASCADE ở DB hoạt động đúng ngay
    # lập tức, chỉ session đang mở transaction cũ mới thấy "trễ".
    session.rollback()
    remaining = session.execute(
        select(func.count()).select_from(user_roles)
    ).scalar_one()
    assert remaining == 0


def test_delete_workflow_sets_null_current_workflow(session, engine):
    employee = _make_employee()
    session.add(employee)
    session.flush()

    workflow = Workflow(
        employee_id=employee.id,
        version=1,
        template_code="invoice_to_excel",
        name="Quy trình",
    )
    workflow.steps = [
        WorkflowStep(
            step_key="read_invoice",
            order_index=1,
            tool_code="vision.extract_invoice",
            label="Đọc",
        )
    ]
    session.add(workflow)
    session.flush()
    employee.current_workflow_id = workflow.id
    session.commit()

    session.expire_all()
    emp_before = session.get(AIEmployee, employee.id)
    assert emp_before is not None
    assert emp_before.current_workflow_id == workflow.id

    # Xoá qua SQL CORE — DB tự xử lý SET NULL cho
    # ai_employees.current_workflow_id (dùng session mới, không vướng
    # identity map của session cũ).
    with Session(engine) as s2:
        s2.execute(delete(Workflow).where(Workflow.id == workflow.id))
        s2.commit()

    # rollback() để kết thúc transaction WAL cũ — xem giải thích ở
    # test_delete_user_cascades_user_roles phía trên, cùng nguyên nhân.
    session.rollback()
    emp_after = session.get(AIEmployee, employee.id)
    assert emp_after is not None
    assert emp_after.current_workflow_id is None


def test_orm_delete_workflow_cascades_steps_edges_schedule(session):
    employee = _make_employee()
    session.add(employee)
    session.flush()

    workflow = Workflow(
        employee_id=employee.id,
        version=1,
        template_code="invoice_to_excel",
        name="Quy trình",
    )
    workflow.steps = [
        WorkflowStep(
            step_key="step_a",
            order_index=1,
            tool_code="vision.extract_invoice",
            label="Bước A",
        ),
        WorkflowStep(
            step_key="step_b",
            order_index=2,
            tool_code="xlsx.append_rows",
            label="Bước B",
        ),
    ]
    workflow.edges = [WorkflowEdge(from_key="step_a", to_key="step_b")]
    workflow.schedule = Schedule(trigger_type="manual")
    session.add(workflow)
    session.commit()

    session.delete(workflow)
    session.commit()

    session.expire_all()
    assert session.get(Workflow, workflow.id) is None
    assert (
        session.execute(
            select(func.count())
            .select_from(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow.id)
        ).scalar_one()
        == 0
    )
    assert (
        session.execute(
            select(func.count())
            .select_from(WorkflowEdge)
            .where(WorkflowEdge.workflow_id == workflow.id)
        ).scalar_one()
        == 0
    )
    assert (
        session.execute(
            select(func.count())
            .select_from(Schedule)
            .where(Schedule.workflow_id == workflow.id)
        ).scalar_one()
        == 0
    )