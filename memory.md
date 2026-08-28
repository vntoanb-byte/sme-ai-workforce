# memory.md

> Không tự động coi toàn bộ nội dung ở đây là sự thật tuyệt đối — kiểm tra lại nếu nghi ngờ đã lỗi thời.

## North Star

Xem `03 - context/priorities.md` trong OS Brain (`C:\Users\DELL\Documents\My-OS-Brain`) — 3 ưu tiên 90 ngày, trong đó ưu tiên 2 là "Hoàn thiện MVP SME AI Workforce — workflow chạy end-to-end".

## Quyết định quan trọng còn hiệu lực

- ADR-001/002/003 trong `docs/DECISIONS.md` — không tự vi phạm (hàng đợi SQLite thay Redis, CrewAI chỉ sequential, không tách màn hình review riêng).
- `backend/pyproject.toml` có `pythonpath = ["."]` trong `[tool.pytest.ini_options]` (thêm 2026-08-28) — bắt buộc để `import app...` hoạt động trong pytest; đừng xoá khi sửa file này.
- Cline/VS Code đã bị gỡ khỏi máy (2026-08-28) — Claude Code làm cả Architect lẫn Implementer trực tiếp, không còn phối hợp qua `.clinerules`/khối giao task nữa (file `.clinerules` vẫn còn, không gây hại, không cần dùng).

## Việc quan trọng đang dở (context cần giữ qua nhiều phiên)

- TASK-001 (`domain/validators.py`) đã DONE (2026-08-28) — chi tiết đầy đủ ở `IMPLEMENTATION_PLAN.md`.
- `scripts/verify` toàn dự án đang FAIL vì lint debt có sẵn ở 6 file (không phải lỗi mới) — xem `IMPLEMENTATION_PLAN.md` mục Current. Task dọn lint đã tách riêng, chưa chạy.
- Tiếp theo theo thứ tự: `domain/compiler.py` → `adapters/queue_sqlite.py` → `adapters/storage_local.py` → `models/*` → `services/*` → `api/v1/*` → `tools/*` → `agents/crew.py` → `workers/*` → nối frontend.
