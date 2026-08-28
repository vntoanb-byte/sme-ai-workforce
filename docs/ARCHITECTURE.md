# Kiến trúc

Xem tài liệu thiết kế kỹ thuật (bản .docx) để có đầy đủ sơ đồ và mô tả.

Tóm tắt: kiến trúc bốn cổng (Ports & Adapters).

| Cổng | Nội bộ | Web công khai |
|---|---|---|
| `LLMProvider` | vLLM + Qwen3-VL 8B | vLLM trên nút GPU riêng |
| `Repository` | SQLite (WAL) | PostgreSQL |
| `FileStorage` | Hệ thống tệp | MinIO / S3 |
| `JobQueue` | Bảng SQLite | Celery + Redis |

Lõi nghiệp vụ (`domain/`, `services/`, `tools/`) giống hệt nhau ở cả hai môi trường.
