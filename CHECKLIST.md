# CHECKLIST.md — Definition of Done kiểm chứng được

> Mỗi `[x]` PHẢI có bằng chứng (log/output/link) đi kèm. Không đánh dấu `[x]` vì "AI nghĩ rằng đã làm".

## Task hiện tại: TASK-003 — `ports/queue.py` + `adapters/queue_sqlite.py`

- [x] Requirement satisfied — giao thức giành việc đúng ADR-001 (BEGIN IMMEDIATE + SELECT + UPDATE + kiểm rowcount)
- [x] SPEC satisfied — đối chiếu docstring gốc + ADR-001 (nguồn cụ thể hơn SPEC.md cho file này)
- [x] Code implemented — `ports/queue.py` + `adapters/queue_sqlite.py` (Cline viết, Claude review không sửa gì)
- [x] Unit tests passed — evidence: `pytest -v` toàn dự án → `41 passed in 0.79s`; riêng `test_queue_sqlite.py` chạy 5 lần liên tiếp đều `10 passed`, không flaky
- [x] Integration tests passed — evidence: test đồng thời thật (`threading.Barrier`, file SQLite thật, không `:memory:`) — coi là integration test cho property quan trọng nhất (khoá ghi thật)
- [x] Build passed — `npm typecheck`/`npm build` PASS qua `scripts/verify`
- [x] Security checked — evidence: không có input người dùng chưa qua bind parameter (chống SQL injection — mọi câu SQL dùng `text()` + tham số `:name`, không nối chuỗi trực tiếp)
- [x] No secrets committed — evidence: `scripts/verify` mục "Secret scan (diff)" → PASS
- [x] Architecture respected — evidence: `git diff --stat` xác nhận không đụng `db/session.py` (trừ phần Claude tự sửa trước khi giao), `db/base.py`, `schemas/`, `domain/*`, `ports/llm.py`; `mypy`/`ruff` PASS
- [x] No forbidden changes — chỉ đổi đúng 3 file trong `Allowed files` + `db/session.py` (Claude tự sửa, ngoài phạm vi giao Cline, có lý do rõ ràng)
- [x] Documentation updated — `IMPLEMENTATION_PLAN.md` cập nhật đầy đủ evidence + 2 giả định cần Toàn xác nhận

**Không phát hiện bug khi review** (khác TASK-002) — code Cline viết đúng ngay từ đầu cho task này.

**Giả định cần Toàn xác nhận:** (1) lược đồ cột bảng `job_queue` (chưa có model ORM/Alembic thật); (2) trạng thái `'succeeded'` (không có trong docstring gốc).

**Lưu ý còn tồn:** `scripts/verify` toàn dự án vẫn FAIL vì lint debt có sẵn (task `task_b232c26f`, chưa chạy) — không liên quan TASK-003.
