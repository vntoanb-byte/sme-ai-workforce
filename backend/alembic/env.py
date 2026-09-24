"""
Cấu hình môi trường Alembic

Kết nối Alembic với metadata của SQLAlchemy để tự sinh tệp di trú.
  1. target_metadata = Base.metadata (db/base.py import đủ mọi model)
  2. DATABASE_URL lấy từ settings (hoặc sqlalchemy.url do code truyền vào —
     dùng khi kiểm thử / khởi động qua app.db.init_db.upgrade_db)
  3. render_as_batch=True — BẮT BUỘC với SQLite (không hỗ trợ ALTER COLUMN)
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.db.base import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()


def _run(connection) -> None:  # noqa: ANN001
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
