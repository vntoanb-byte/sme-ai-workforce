"""
Phiên làm việc với cơ sở dữ liệu

Tạo engine, SessionLocal, và QUAN TRỌNG NHẤT là đặt các PRAGMA của SQLite ngay
khi mỗi kết nối được mở. Thiếu bước này hệ thống sẽ gặp lỗi 'database is
locked'.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# SQLite không tự tạo thư mục cha của file DB — tạo trước nếu DATABASE_URL
# trỏ tới 1 file cục bộ (bỏ qua với DB trong bộ nhớ ':memory:' hoặc DSN khác).
_url = make_url(settings.DATABASE_URL)
if _url.get_backend_name() == "sqlite" and _url.database and _url.database != ":memory:":
    Path(_url.database).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
