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

## Task đã xong: TASK-005b — `models/run.py` + `extraction.py` + `artifact.py` + `audit.py`

- [x] Requirement satisfied — 12 bảng đúng lược đồ Claude thiết kế (tiêu đề task ghi nhầm "11 bảng", đếm thật theo Requirements là 12, đã ghi rõ trong IMPLEMENTATION_PLAN.md)
- [x] SPEC satisfied — đối chiếu `domain/state.py`, `ports/queue.py`+`adapters/queue_sqlite.py`, `ports/storage.py`, `domain/qc_rules.py`, frontend types.ts/mock data
- [x] Code implemented — Cline viết theo đúng spec cột, Claude Code đọc lại toàn bộ 4 file, không phát hiện bug
- [x] Unit tests passed — evidence: `pytest -v` toàn dự án (Claude tự chạy lại) → `73 passed in 2.17s` (baseline 57 + 16 test mới)
- [x] Integration tests passed — `Base.metadata.create_all()` thật trên engine `app/db/session.py` → 21 bảng, không lỗi FK; `PRAGMA table_info(job_queue)` xác nhận đúng kiểu cột TEXT khớp `adapters/queue_sqlite.py`
- [x] Build passed — `npm typecheck`/`npm build` PASS qua `scripts/verify`
- [x] Security checked — evidence: mọi FK dùng bind parameter qua ORM; `entity_id` trong `audit_logs` cố ý không FK (đa hình) nhưng không nhận input trực tiếp từ user chưa qua validate ở tầng models/
- [x] No secrets committed — `scripts/verify` mục "Secret scan (diff)" → PASS
- [x] Architecture respected — cột JSON dùng Text; FK có ondelete rõ ràng; tiền tệ dùng `Numeric`/`Decimal` không dùng float; `mypy`/`ruff` PASS trên 4 file mới
- [x] No forbidden changes — `git diff --stat` xác nhận chỉ đổi đúng Allowed files; không đụng `models/user.py`/`employee.py`/`workflow.py`/`domain/`/`ports/`/`adapters/`/`api/`
- [x] Documentation updated — `IMPLEMENTATION_PLAN.md` cập nhật đầy đủ evidence review độc lập của Claude

**Không phát hiện bug thật nào** (khác TASK-002/005a) — 2 quyết định kỹ thuật đáng chú ý của Cline khi hiện thực đúng theo Requirements:
1. `db/base.py`: sửa thêm 3 lỗi ruff `UP017` có sẵn (`datetime.timezone.utc` → `datetime.UTC`) để thoả Must pass — thay đổi cơ học, không đổi hành vi, đã re-verify.
2. `Extraction.human_reviews` và `Artifact.documents`: thêm `viewonly=True` cho quan hệ một-chiều trùng cột FK, tránh SAWarning "copy column" — đúng theo yêu cầu Requirements, không tự sáng tạo.

**Giả định cần Toàn xác nhận lại (NOTE trong code, chưa phải quyết định cuối):**
1. `Extraction` denormalize `invoice_no/issue_date/seller_name/seller_tax_code/subtotal/vat_rate/vat_amount/total` từ JSON ra cột riêng (phục vụ QC-06 + lọc danh sách).
2. `Document` KHÔNG denormalize `invoice_no/total/qc_failed` (tính qua JOIN ở service layer) — NGƯỢC với quyết định 1, cố ý.
3. `RunLog` dùng 1 bảng cho cả log transition (`domain/state.py`) lẫn log SSE stream.

**Lưu ý còn tồn:** `scripts/verify` toàn dự án vẫn FAIL vì lint debt cũ — nhưng đã giảm từ 41 → 38 lỗi (task `task_b232c26f` xử lý sau, không liên quan TASK-005b).
