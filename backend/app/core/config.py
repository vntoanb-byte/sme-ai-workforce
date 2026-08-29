"""
Cấu hình ứng dụng

Đọc toàn bộ tham số từ biến môi trường bằng Pydantic Settings. Đây là nơi DUY
NHẤT được phép đọc os.environ — mọi module khác import settings từ đây.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Đường dẫn TUYỆT ĐỐI tới backend/.env, neo theo vị trí chính file này —
# KHÔNG phụ thuộc thư mục làm việc (cwd) lúc tiến trình khởi động. Phát hiện
# thật (TASK-007): khi chạy qua công cụ preview (cwd khác backend/), đường dẫn
# TƯƠNG ĐỐI ".env" cũ không tìm thấy tệp, mọi biến rơi về giá trị mặc định
# (LLM_API_KEY rỗng → lỗi "Illegal header value" khi gọi model).
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # ─── Mô hình ───
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "qwen/qwen3-vl-8b-instruct"
    LLM_API_KEY: str = ""
    LLM_TIMEOUT_SEC: int = 120
    LLM_MAX_RETRIES: int = 3

    # ─── Cơ sở dữ liệu và kho tệp ───
    DATABASE_URL: str = "sqlite:///./data/app.db"
    STORAGE_PATH: str = "./data/artifacts"
    BACKUP_PATH: str = "./data/backup"

    # ─── Xử lý nền ───
    WORKER_CONCURRENCY: int = 1
    JOB_LEASE_SECONDS: int = 900
    JOB_POLL_INTERVAL_SEC: int = 2
    WATCH_PATH: str = "./data/scan"
    TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # ─── Xử lý ảnh ───
    IMAGE_MAX_LONG_EDGE: int = 1280
    IMAGE_MAX_PIXELS: int = 1638400
    PDF_RENDER_DPI: int = 150

    # ─── Bảo mật ───
    JWT_SECRET: str = ""
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7
    CREDENTIAL_ENC_KEY: str = ""
    MAX_UPLOAD_MB: int = 20

    # ─── CORS ───
    # Danh sách origin được phép gọi API. Mặc định là dev server Vite; khi
    # deploy thật phải đổi theo domain thật.
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # ─── Tài khoản quản trị đầu tiên ───
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_PASSWORD: str = ""


settings = Settings()
