"""
Khởi tạo cơ sở dữ liệu và dữ liệu gốc

  upgrade_db()      — `alembic upgrade head` (gọi lúc API khởi động). DB cũ được
                      tạo bằng Base.metadata.create_all() (trước khi có Alembic)
                      sẽ được `stamp` đúng phiên bản trước rồi mới nâng cấp,
                      không tạo lại bảng đã có.
  wait_for_schema() — tiến trình worker chờ API migrate xong (tránh 2 tiến
                      trình cùng migrate một file SQLite).
  seed()            — dữ liệu bắt buộc khi chạy lần đầu:
      1. 3 vai trò USER, MANAGER, ADMIN
      2. đồng bộ bảng tools từ registry trong mã nguồn
      3. tài khoản quản trị đầu tiên từ FIRST_ADMIN_* nếu chưa có quản trị viên
      4. cấu hình mặc định (settings)
"""

from __future__ import annotations

import time
from pathlib import Path

import structlog
from sqlalchemy import Engine, create_engine, inspect, select
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.core.config import settings
from app.db.base import Base
from app.models.user import Role, User

logger = structlog.get_logger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
INITIAL_REVISION = "0001"


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    url = database_url or settings.DATABASE_URL
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def head_revision() -> str:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    assert head is not None
    return head


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def upgrade_db(database_url: str | None = None) -> None:
    url = database_url or settings.DATABASE_URL
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        if "alembic_version" not in tables and "users" in tables:
            model_tables = set(Base.metadata.tables)
            target = "head" if model_tables <= tables else INITIAL_REVISION
            logger.info("db.stamp_legacy", revision=target)
            command.stamp(cfg, target)
    finally:
        engine.dispose()
    command.upgrade(cfg, "head")


def wait_for_schema(timeout: float = 120.0, interval: float = 2.0) -> None:
    from app.db.session import engine

    head = head_revision()
    deadline = time.monotonic() + timeout
    while True:
        try:
            if current_revision(engine) == head:
                return
        except Exception:  # noqa: BLE001 — DB chưa sẵn sàng, thử lại
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "Cơ sở dữ liệu chưa được nâng cấp lên phiên bản mới nhất — hãy khởi động "
                "API (tự chạy migration) hoặc chạy `alembic upgrade head` trước."
            )
        time.sleep(interval)


def seed(db: Session) -> None:
    from app.core.security import hash_password
    from app.services import settings_service
    from app.tools.base import sync_tools_to_db

    roles = {r.code: r for r in db.scalars(select(Role))}
    for code in ("USER", "MANAGER", "ADMIN"):
        if code not in roles:
            roles[code] = Role(code=code)
            db.add(roles[code])
    db.flush()

    sync_tools_to_db(db)
    settings_service.seed_defaults(db)

    has_admin = db.scalar(select(User.id).join(User.roles).where(Role.code == "ADMIN").limit(1))
    if has_admin is None:
        if settings.FIRST_ADMIN_PASSWORD:
            db.add(
                User(
                    username=settings.FIRST_ADMIN_USERNAME,
                    full_name="Quản trị hệ thống",
                    email=f"{settings.FIRST_ADMIN_USERNAME}@localhost",
                    password_hash=hash_password(settings.FIRST_ADMIN_PASSWORD),
                    is_active=True,
                    roles=[roles["USER"], roles["MANAGER"], roles["ADMIN"]],
                )
            )
            logger.info("db.first_admin_created", username=settings.FIRST_ADMIN_USERNAME)
        else:
            logger.warning(
                "db.no_admin",
                message="Chưa có quản trị viên và FIRST_ADMIN_PASSWORD trống — không tạo được.",
            )
    db.flush()
