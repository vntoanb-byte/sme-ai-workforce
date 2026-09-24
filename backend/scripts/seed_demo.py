"""
Nạp dữ liệu trình diễn

Tạo dữ liệu mẫu để demo trước hội đồng mà không phụ thuộc mạng/GPU — đi qua
ĐÚNG các service thật (quy trình từ mẫu, chuyển trạng thái qua domain/state,
QC bằng 8 quy tắc thật), không chèn thẳng số liệu bịa vào bảng:

  1. Người dùng mẫu cho cả ba vai trò: ketoan (USER), quanly (USER+MANAGER),
     admin (cả ba) — cùng mật khẩu --password.
  2. 2 nhân viên AI đã duyệt ("Kế toán hoá đơn", "Báo cáo cuối ngày") và vài chục
     lần chạy đã xong, mỗi lần có hoá đơn (ảnh tổng hợp) đã đọc + QC.
  3. 3 chứng từ đang chờ xác nhận (lỗi tổng tiền, mã số thuế, thuế suất) để
     trình diễn màn hình kiểm tra.

Dùng (chạy SAU khi API đã khởi động ít nhất một lần hoặc đã `alembic upgrade head`):
    python scripts/seed_demo.py [--password Demo@12345] [--runs 24]
Chạy lại lần hai: không tạo trùng (phát hiện nhân viên demo đã có thì dừng).
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen_synthetic_invoices import add_noise, make_invoice, render  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.domain.state import RunStatus, transition  # noqa: E402
from app.domain.templates.registry import build_spec  # noqa: E402
from app.models.artifact import Document  # noqa: E402
from app.models.employee import AIEmployee  # noqa: E402
from app.models.extraction import Extraction  # noqa: E402
from app.models.run import Run, RunStep  # noqa: E402
from app.models.user import User  # noqa: E402
from app.ports.storage import FileStorage  # noqa: E402
from app.schemas.invoice import SCHEMA_VERSION, InvoiceExtraction  # noqa: E402
from app.services import auth_service, qc_service, run_service, workflow_service  # noqa: E402
from app.services.document_service import ensure_artifact  # noqa: E402

DEMO_EMPLOYEE = "Kế toán hoá đơn"
USERS = (
    ("ketoan", "Nguyễn Thị Hoa", "hoa@anphat.vn", ["USER"]),
    ("quanly", "Trần Thu Hương", "huong@anphat.vn", ["USER", "MANAGER"]),
    ("admin", "Quản trị hệ thống", "admin@anphat.vn", ["USER", "MANAGER", "ADMIN"]),
)


def _users(db: Session, password: str) -> list[str]:
    """Tạo tài khoản demo còn thiếu; trả về tên các tài khoản VỪA tạo (tài khoản có
    sẵn — vd. admin tạo từ FIRST_ADMIN_* — giữ nguyên mật khẩu cũ)."""
    created = []
    for username, name, email, roles in USERS:
        if db.scalar(select(User).where(User.username == username)) is None:
            auth_service.create_user(
                db, username=username, full_name=name, email=email, password=password, roles=roles
            )
            created.append(username)
    return created


def _employee(db: Session, name: str, code: str, cron: str, desc: str, config: dict) -> AIEmployee:
    employee = AIEmployee(name=name, job_description=desc, status="draft")
    db.add(employee)
    db.flush()
    spec = build_spec(
        code,
        name=name,
        description=desc,
        trigger={"type": "cron", "cron_expr": cron, "timezone": settings.TIMEZONE},
        config={"scan_folder": {"path": settings.WATCH_PATH}, **config},
    )
    wf = workflow_service.save_new_version(db, employee, spec)
    workflow_service.approve(db, wf, None)
    return employee


def _document(
    db: Session,
    storage: FileStorage,
    run: Run,
    data: dict[str, Any],
    rng: random.Random,
    at: datetime,
) -> Document:
    img = render(data)
    if rng.random() < 0.4:
        img = add_noise(img, rng)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    name = f"IMG_{at:%Y%m%d}_{rng.randint(1000, 9999)}.jpg"
    doc = Document(
        filename=name, source_kind="image", status="processing", created_at=at, updated_at=at
    )
    doc.artifact = ensure_artifact(db, storage, buf.getvalue(), name)
    db.add(doc)
    db.flush()
    inv = InvoiceExtraction.model_validate(data)
    extraction = Extraction(
        document_id=doc.id,
        run_id=run.id,
        schema_version=SCHEMA_VERSION,
        model_name=settings.LLM_MODEL,
        latency_ms=rng.randint(9000, 21000),
        invoice_no=inv.invoice_no,
        issue_date=inv.issue_date,
        seller_name=inv.seller.name,
        seller_tax_code=inv.seller.tax_code,
        currency=inv.currency,
        subtotal=inv.totals.subtotal,
        vat_rate=inv.totals.vat_rate,
        vat_amount=inv.totals.vat_amount,
        total=inv.totals.total,
        extracted_data_json=json.dumps(inv.model_dump(mode="json"), ensure_ascii=False),
        created_at=at,
        updated_at=at,
    )
    db.add(extraction)
    db.flush()
    doc.status = "needs_review" if qc_service.evaluate(db, extraction) else "ok"
    return doc


def _started_run(db: Session, employee: AIEmployee, at: datetime, rng: random.Random) -> Run:
    """Run đã qua PENDING → CLAIMED → RUNNING (qua domain/state), các bước đã xong."""
    run = Run(
        employee_id=employee.id,
        workflow_id=employee.current_workflow_id,
        trigger_type="cron",
        status="pending",
        created_at=at,
        updated_at=at,
    )
    db.add(run)
    db.flush()
    log = run_service.transition_logger(db)
    transition(run, RunStatus.CLAIMED, "Tiến trình demo nhận việc", log)
    transition(run, RunStatus.RUNNING, "Bắt đầu thực thi", log)
    run.started_at = at
    for step in employee.current_workflow.steps:  # type: ignore[union-attr]
        run.steps.append(
            RunStep(
                step_key=step.step_key,
                order_index=step.order_index,
                label=step.label,
                status="SUCCEEDED",
                duration_ms=rng.randint(800, 60000),
            )
        )
    return run


def seed_demo(db: Session, storage: FileStorage, password: str, runs: int = 24) -> str:
    if db.scalar(select(AIEmployee).where(AIEmployee.name == DEMO_EMPLOYEE)):
        return "Đã có dữ liệu demo — bỏ qua."
    rng = random.Random(7)
    created_users = _users(db, password)
    invoices = _employee(
        db,
        DEMO_EMPLOYEE,
        "invoice_to_excel",
        "0 8 * * *",
        "Mỗi sáng 8 giờ, đọc các hoá đơn mới trong thư mục Scan, nhập vào tệp "
        "SoHoaDon2026.xlsx và kiểm tra xem tổng tiền có khớp không.",
        {"write_excel": {"file": "SoHoaDon2026.xlsx"}},
    )
    reports = _employee(
        db,
        "Báo cáo cuối ngày",
        "invoice_report",
        "30 17 * * *",
        "Cuối mỗi ngày lúc 17h30, tổng hợp hoá đơn đã xử lý trong ngày thành báo cáo "
        "Excel và PDF gửi quản lý.",
        {},
    )
    now = datetime.now(UTC)
    for i in range(runs):
        day = now - timedelta(days=runs - i, hours=rng.randint(0, 3))
        employee = invoices if i % 3 else reports
        run = _started_run(db, employee, day, rng)
        if employee is invoices:
            for n in range(rng.randint(1, 3)):
                _document(
                    db, storage, run, make_invoice(rng, i * 10 + n), rng, day + timedelta(minutes=n)
                )
        transition(run, RunStatus.SUCCEEDED, "Hoàn tất lần chạy", run_service.transition_logger(db))
        run.finished_at = day + timedelta(minutes=rng.randint(1, 8))

    # Lần chạy gần nhất: 3 chứng từ cần người xác nhận.
    last = _started_run(db, invoices, now - timedelta(hours=2), rng)
    broken = []
    for n, fault in enumerate(("total", "tax_code", "vat_rate")):
        data = make_invoice(rng, 900 + n)
        if fault == "total":
            data["totals"]["total"] = str(int(data["totals"]["total"]) - 10000)
        elif fault == "tax_code":
            code = data["seller"]["tax_code"]
            data["seller"]["tax_code"] = code[:8] + "I" + code[9:]  # AI đọc nhầm 1 → I
        else:
            data["totals"]["vat_rate"] = "7"
        broken.append(_document(db, storage, last, data, rng, now - timedelta(hours=2, minutes=-n)))
    transition(
        last,
        RunStatus.NEEDS_REVIEW,
        "3 chứng từ không đạt kiểm tra — chờ người xác nhận",
        run_service.transition_logger(db),
    )
    last.finished_at = now - timedelta(hours=1, minutes=50)
    db.flush()
    pending = sum(1 for d in broken if d.status == "needs_review")
    return (
        f"Đã tạo tài khoản [{', '.join(created_users) or 'không có tài khoản mới'}] "
        f"(mật khẩu: {password}), 2 nhân viên AI, {runs + 1} lần chạy, "
        f"{pending} chứng từ chờ xác nhận."
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Nạp dữ liệu trình diễn")
    parser.add_argument("--password", default="Demo@12345", help="Mật khẩu chung của 3 tài khoản")
    parser.add_argument("--runs", type=int, default=24)
    args = parser.parse_args(argv)

    from app.adapters.storage_local import LocalFileStorage
    from app.db import init_db
    from app.db.session import SessionLocal

    init_db.upgrade_db()
    with SessionLocal() as db:
        init_db.seed(db)
        message = seed_demo(db, LocalFileStorage(settings.STORAGE_PATH), args.password, args.runs)
        db.commit()
    print(message)


if __name__ == "__main__":
    main()
