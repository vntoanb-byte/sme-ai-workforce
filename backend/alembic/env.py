"""
Cấu hình môi trường Alembic

Kết nối Alembic với metadata của SQLAlchemy để tự sinh tệp di trú.

Cần hiện thực:
  1. target_metadata = Base.metadata
  2. Đọc DATABASE_URL từ settings thay vì từ alembic.ini
  3. Bật render_as_batch=True — BẮT BUỘC với SQLite, vì SQLite không hỗ trợ
     ALTER COLUMN
"""
