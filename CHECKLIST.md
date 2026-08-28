# CHECKLIST.md — Definition of Done kiểm chứng được

> Mỗi `[x]` PHẢI có bằng chứng (log/output/link) đi kèm. Không đánh dấu `[x]` vì "AI nghĩ rằng đã làm".

## Task hiện tại: TASK-005a — `models/user.py` + `employee.py` + `workflow.py`

- [x] Requirement satisfied — 9 bảng đúng lược đồ Claude tự thiết kế (không có Phụ lục A gốc)
- [x] SPEC satisfied — đối chiếu docstring gốc + frontend types.ts/mock data (nguồn cụ thể hơn SPEC.md)
- [x] Code implemented — Cline viết, Claude review + tự sửa 4 bug thật
- [x] Unit tests passed — evidence: `pytest -v` toàn dự án → `57 passed in 1.36s`; riêng test_queue_sqlite.py chạy lại 5 lần vẫn ổn định sau khi sửa db/session.py
- [x] Integration tests passed — `Base.metadata.create_all()` thật qua import vòng db/base.py↔models/*.py; `/health` PASS thật (database/storage/llm)
- [x] Build passed — `npm typecheck`/`npm build` PASS qua `scripts/verify`
- [x] Security checked — evidence: password lưu password_hash (argon2, không plaintext); mọi câu SQL/ORM dùng bind parameter
- [x] No secrets committed — evidence: `scripts/verify` mục "Secret scan (diff)" → PASS
- [x] Architecture respected — evidence: cột JSON dùng Text (đọc/ghi ở service layer, không trong models/); FK có ondelete rõ ràng; `mypy`/`ruff` PASS
- [x] No forbidden changes — chỉ đổi 3 file model + test + `db/base.py`/`db/session.py` (Claude tự sửa, có lý do rõ ràng) + `.gitignore` (bug hạ tầng phát hiện, không liên quan Cline)
- [x] Documentation updated — `IMPLEMENTATION_PLAN.md` cập nhật đầy đủ evidence + 4 bug đã sửa + bài học quy trình

**4 bug thật đã phát hiện + sửa khi review** (không phải chỉ tin lời Cline):
1. `Mapped["X" | None]` — SyntaxError khi de-stringify.
2. `WorkflowEdge.workflow` thiếu primaryjoin/foreign_keys tường minh.
3. Thứ tự insert workflow_steps/workflow_edges trong cùng transaction — sửa bằng `PRAGMA defer_foreign_keys=ON` (ảnh hưởng `db/session.py` toàn app, đã re-verify `/health` + test đồng thời TASK-003).
4. (Test) WAL snapshot isolation, không phải bug schema — sửa bằng `session.rollback()`.

**Bug hạ tầng phát hiện thêm:** `.gitignore` có `models/` không neo gốc, khiến `backend/app/models/` chưa từng được git track — đã sửa `/models/`.

**Lưu ý còn tồn:** `scripts/verify` toàn dự án vẫn FAIL vì lint debt có sẵn (task `task_b232c26f`, chưa chạy) — không liên quan TASK-005a.
