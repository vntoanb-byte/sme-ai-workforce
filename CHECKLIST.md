# CHECKLIST.md — Definition of Done kiểm chứng được

> Mỗi `[x]` PHẢI có bằng chứng (log/output/link) đi kèm. Không đánh dấu `[x]` vì "AI nghĩ rằng đã làm".

## Task hiện tại: TASK-008 — Hoàn thiện toàn bộ hệ thống

- [x] Requirement satisfied — 9 router/38 điểm cuối, 14 công cụ, 5 mẫu, worker/lập lịch, nối giao diện, script demo/đánh giá, README (lưu đồ, công nghệ, lựa chọn model, báo cáo)
- [x] SPEC satisfied — 5 user flow của SPEC.md chạy thật qua giao diện (E2E); 8/8 quy tắc QC có ca đạt + không đạt; `GET /health` đủ 3 check. Tiêu chí ≥90%/≤25s: **CHƯA đo được trên model thật** (không có GPU) — có sẵn công cụ đo `make eval`
- [x] Code implemented
- [x] Unit + integration tests passed — evidence: `pytest` → `276 passed`, độ phủ 92%
- [x] Build passed — evidence: `scripts/verify` → `[PASS] npm typecheck`, `[PASS] npm build`, `RESULT: PASS`; Docker build (trừ bước apt bị proxy chặn) + container chạy trọn luồng
- [x] E2E — evidence: Playwright/Chromium 20/20 PASS trên uvicorn + worker thật, log 0 lỗi
- [x] Security checked — evidence: mọi điểm cuối yêu cầu JWT + test phân quyền 401/403 (`test_api_auth.py`); argon2; refresh token thu hồi được; cookie chỉ nhận cho GET; chặn đường dẫn ngoài thư mục (`test_path_guard`); `JWT_SECRET` mẫu không được dùng; secret scan PASS
- [x] No secrets committed — `scripts/verify` "Secret scan (diff)" → PASS; `.env` không commit
- [x] Architecture respected — grep: `domain/` chỉ import `app.domain|app.ports|app.schemas`; không `os.environ` ngoài `core/config.py`; `run.status` chỉ gán trong `domain/state.py`; tiền tệ Decimal (float chỉ ở biên API); lược đồ mới qua migration 0002
- [x] No forbidden changes — không đổi SPEC, không xoá dữ liệu/test, không git nguy hiểm; thay đổi kiến trúc có ADR (004–008) chờ Owner xác nhận
- [x] Documentation updated — README, ARCHITECTURE, SECURITY, DECISIONS, IMPLEMENTATION_PLAN, memory

## Task đã xong: TASK-005a — `models/user.py` + `employee.py` + `workflow.py`

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

## Task đã xong: TASK-006 — Luồng upload chứng từ → AI đọc → QC (bản tối giản)

- [x] Requirement satisfied — đủ 10 file lõi (schemas/invoice.py, utils/hashing.py+images.py, 2 services, api/deps.py, api/v1/documents.py+__init__.py, main.py) + 3 file test
- [x] SPEC satisfied — khớp `frontend/src/api/types.ts` (DocumentRow/DocumentDetail/QCResult), `domain/qc_rules.py`, `ports/llm.py`/`ports/storage.py`
- [x] Code implemented — Cline viết phần lõi (crash giữa chừng do lỗi CLI nội bộ, không phải lỗi code — xem IMPLEMENTATION_PLAN.md), Claude Code hoàn thiện test + tự sửa 4 bug thật khi review
- [x] Unit tests passed — evidence: `pytest -v` → `94 passed` (baseline 73 + 21 mới)
- [x] Integration tests passed — `tests/integration/test_api_documents.py` (11 test, FastAPI TestClient + fake LLM) PASS; **quan trọng hơn:** đã tự chạy `uvicorn app.main:app` THẬT (không phải TestClient) + `curl` upload ảnh thật → 200, `GET /documents`/`GET /documents/{id}/file` đúng dữ liệu (đối chiếu byte-for-byte bằng `cmp`)
- [x] Build passed — `npm typecheck`/`npm build` PASS qua `scripts/verify`
- [x] Security checked — `# TODO SECURITY` ghi rõ trong `documents.py` (chưa có auth, quyết định có chủ đích TASK-006); giới hạn `MAX_UPLOAD_MB` chặn trước khi đọc hết file vào RAM
- [x] No secrets committed — `scripts/verify` mục "Secret scan (diff)" → PASS; không in `LLM_API_KEY`/`accessToken` ra bất kỳ đâu
- [x] Architecture respected — `domain/qc_rules.py` không bị sửa, `services/` không import `api/`; tiền tệ `Decimal`/`Numeric`, không `float`
- [x] No forbidden changes — không đụng `models/*.py` (TASK-005a/b), không đụng `domain/*.py`; `core/config.py` chỉ thêm đúng 1 field `CORS_ORIGINS` (ngoại lệ duy nhất được phép trong Requirements)
- [x] Documentation updated — `IMPLEMENTATION_PLAN.md` cập nhật đầy đủ evidence + 4 bug đã sửa + sự cố Cline crash

**4 bug thật đã phát hiện + tự sửa khi review (1 nghiêm trọng):**
1. **🔴 Import vòng vỡ khi chạy `uvicorn app.main:app` thật** — server crash ngay khi khởi động (pytest không phát hiện vì `conftest.py` tình cờ che mất thứ tự import). Bug ảnh hưởng đúng con đường Owner sẽ dùng để chạy app thật — mức độ nghiêm trọng cao nhất trong các bug đã gặp từ đầu dự án.
2. `list_documents()`: `qc_failed` scalar_subquery thiếu `.label()` đúng chỗ → `AttributeError` khi có document trong danh sách (pytest bắt được).
3. `utils/images.py`: `Image.LANCZOS` (stub cũ) → `Image.Resampling.LANCZOS`.
4. `document_service.py`: biến `artifact` bị gán 2 kiểu khác nhau giữa 2 nhánh if → tách biến `existing_artifact`.

**Sự cố quy trình:** Cline CLI crash giữa nhiệm vụ (lỗi nội bộ `hook dispatch failed`, không phải lỗi model/encoding) sau khi đã sửa xong code (xác nhận qua đọc log — bản sửa cuối cùng đúng). Claude Code không dispatch lại mà tự hoàn thiện phần còn thiếu (test) + tự review, tránh rủi ro crash lần 2.

**Giả định cần Toàn xác nhận (NOTE trong code):** (1) trích xuất đồng bộ, không qua job_queue; (2) chưa có auth cho endpoint documents; (3) `Party.tax_code`/`Totals.vat_rate` viết lỏng để QC bắt lỗi thay vì Pydantic chặn cứng; (4) `deskew()` chưa hiện thực.

**Lưu ý còn tồn:** `scripts/verify` vẫn FAIL vì lint debt cũ (38 lỗi, không đổi). Phát hiện thêm 1 lỗi mypy debt cũ trong `domain/qc_rules.py` (chưa từng bị bắt vì trước giờ chỉ chạy mypy từng file lẻ) — gộp vào task dọn debt đã tách riêng. **Owner cần điền `LLM_API_KEY` thật vào `backend/.env` để thấy trích xuất AI thành công** — hiện tại toàn bộ pipeline đã chạy đúng, chỉ thiếu key thật.
