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
    # isolation_level=None tắt chế độ "autobegin ngầm" của driver pysqlite —
    # nếu không tắt, pysqlite tự mở transaction ngay khi thấy câu lệnh DML đầu
    # tiên, khiến BEGIN IMMEDIATE tường minh (bắt buộc cho giao thức giành việc
    # ở adapters/queue_sqlite.py theo ADR-001) báo lỗi "cannot start a
    # transaction within a transaction". Đây là bẫy kỹ thuật kinh điển của
    # SQLAlchemy + pysqlite — xem event "begin" bên dưới để biết SQLAlchemy tự
    # phát ra BEGIN thường ra sao khi không có ai tự issue BEGIN IMMEDIATE.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


@event.listens_for(engine, "begin")
def _do_begin(conn) -> None:  # noqa: ANN001
    # Vì isolation_level=None đã tắt autobegin của pysqlite, SQLAlchemy cần
    # được dạy cách tự mở transaction. Mặc định phát BEGIN thường — code cần
    # giành khoá ghi NGAY LẬP TỨC (vd. adapters/queue_sqlite.py.claim(), theo
    # ADR-001) phải tự đánh dấu connection TRƯỚC khi chạm câu lệnh đầu tiên:
    #
    #   conn = engine.connect().execution_options(sqlite_begin_immediate=True)
    #   conn.execute(...)  # câu lệnh đầu tiên trên connection này sẽ tự kích
    #                      # hoạt "begin" ở trên với BEGIN IMMEDIATE, không phải
    #                      # BEGIN thường.
    #
    # KHÔNG tự gọi conn.exec_driver_sql("BEGIN IMMEDIATE") sau khi connection
    # đã autobegin (vd. sau execute() đầu tiên) — sẽ lỗi "cannot start a
    # transaction within a transaction" vì lúc đó transaction BEGIN thường đã
    # mở rồi. Đặt execution_options TRƯỚC câu lệnh đầu tiên là cách duy nhất
    # đúng với cơ chế autobegin của SQLAlchemy 2.0.
    if conn.get_execution_options().get("sqlite_begin_immediate"):
        conn.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        conn.exec_driver_sql("BEGIN")
    # SQLite chỉ kiểm tra FK ngay lập tức theo mặc định — nếu 1 transaction ghi
    # nhiều bảng có FK phụ thuộc lẫn nhau (vd. workflow_edges có FK ghép trỏ
    # workflow_steps, cả hai được flush trong cùng 1 transaction nhưng thứ tự
    # insert do SQLAlchemy tự quyết, không đảm bảo steps luôn ghi trước edges),
    # bật defer_foreign_keys để hoãn kiểm tra FK tới khi COMMIT — tự tắt lại
    # sau mỗi COMMIT/ROLLBACK (theo tài liệu SQLite), nên phải bật lại mỗi
    # transaction ở đây, không thể bật 1 lần trong event "connect".
    conn.exec_driver_sql("PRAGMA defer_foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
