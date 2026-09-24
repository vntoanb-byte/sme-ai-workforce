# memory.md

> Không tự động coi toàn bộ nội dung ở đây là sự thật tuyệt đối — kiểm tra lại nếu nghi ngờ đã lỗi thời.

## North Star

Xem `03 - context/priorities.md` trong OS Brain (`C:\Users\DELL\Documents\My-OS-Brain`) — 3 ưu tiên 90 ngày, trong đó ưu tiên 2 là "Hoàn thiện MVP SME AI Workforce — workflow chạy end-to-end".

## Quyết định quan trọng còn hiệu lực

- ADR-001/002/003 trong `docs/DECISIONS.md` — không tự vi phạm (hàng đợi SQLite thay Redis, CrewAI chỉ sequential, không tách màn hình review riêng).
- `backend/pyproject.toml` có `pythonpath = ["."]` trong `[tool.pytest.ini_options]` (thêm 2026-08-28) — bắt buộc để `import app...` hoạt động trong pytest; đừng xoá khi sửa file này.
- Cline/VS Code đã bị gỡ khỏi máy (2026-08-28) — Claude Code làm cả Architect lẫn Implementer trực tiếp, không còn phối hợp qua `.clinerules`/khối giao task nữa (file `.clinerules` vẫn còn, không gây hại, không cần dùng).

## Việc quan trọng đang dở (context cần giữ qua nhiều phiên)

- TASK-008 (2026-09-24): toàn bộ module đã hiện thực + nối giao diện + E2E — chi tiết/bằng chứng ở `IMPLEMENTATION_PLAN.md`.
- `scripts/verify` toàn dự án nay PASS (đã dọn nợ lint) — giữ nguyên trạng thái này khi sửa tiếp.
- Chờ Owner: xác nhận ADR-004 (bỏ thư viện CrewAI) và ADR-006 (chạy tiếp sau xác nhận); đo `make eval` trên máy có vLLM.
- Mẫu mã: DB/WorkflowSpec dùng `invoice_to_excel`, giao diện dùng `TPL_INVOICE_TO_EXCEL` — đổi DUY NHẤT ở `services/workflow_service.py` (mâu thuẫn cũ đã giải quyết).
- Kiểm thử E2E dùng máy chủ mô hình giả tương thích OpenAI (không commit) — khi có GPU, chạy lại với vLLM thật.
