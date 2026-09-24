# IMPLEMENTATION_PLAN.md — Trạng thái hiện tại của project

> Claude PHẢI đọc file này trước khi tiếp tục 1 project đang làm dở — không tự bịa lại kế hoạch từ đầu nếu đã có plan.

> **2026-08-28:** Owner đã gỡ VS Code/Cline khỏi máy. Từ đây Claude Code trực tiếp làm cả Architect **và** Implementer (không còn phối hợp qua khối "giao task cho Cline" nữa) — nhưng vẫn giữ nguyên kỷ luật tự review bằng bằng chứng thật (`scripts/verify`, Claim Gate) thay vì tự tuyên bố xong.

## Task: TASK-008 — Hoàn thiện toàn bộ hệ thống (API, worker, công cụ, nối giao diện, triển khai)

**Status:** DONE (2026-09-24) — Claude Code làm trực tiếp theo yêu cầu Owner "hoàn thành luôn, viết API, test đầy đủ, báo cáo". Chưa đo độ chính xác trên model thật (không có GPU trong môi trường làm việc) — xem "Còn lại".

**Completed (theo thứ tự trong IMPLEMENTATION_PLAN cũ `compiler → queue → storage → models → services → api → tools → agents → workers → nối frontend`, phần còn thiếu):**
- `core/`: errors (định dạng lỗi thống nhất + `is_transient`), logging (structlog JSON, trace_id), security (argon2, JWT access/refresh, Fernet). Config thêm `COOKIE_SECURE`, `STATIC_DIR`, `REPORT_FONT_PATH`, `FS_ALLOWED_ROOTS`.
- Alembic: `env.py`, `script.py.mako` (bản cũ là stub), migration `0001` (21 bảng hiện có) + `0002` (`refresh_tokens`). API tự `upgrade head` khi khởi động; DB cũ tạo bằng `create_all` được `stamp` đúng phiên bản. Bỏ `create_all` tạm thời ở `main.py`.
- `domain/templates/`: 5 mẫu + `registry.py` (+ `base.py`); 5 mã khớp đúng `TemplateCode` (có test khoá). `compiler.py` đưa danh mục mẫu + bộ khung mẫu + gợi ý môi trường vào prompt (`PROMPT_VERSION = v2`), chữ ký `compile()` giữ tương thích.
- `tools/`: 14 công cụ + registry + `sync_tools_to_db` + chặn đường dẫn ngoài thư mục cho phép. `agents/crew.py`: 3 tác tử tuần tự Python thuần (ADR-004).
- `services/`: auth, employee, workflow (mới), compiler, run (mới), execution, review, report, metrics (mới), settings (mới); document_service tách `extract_document` + ghi `llm_calls`.
- `workers/`: worker (heartbeat, SIGTERM, không chết vì job lỗi), reaper (sửa trạng thái run của worker chết), scheduler (cron + file_watch, đọc lại bảng schedules mỗi phút). Adapter queue thêm `extend_lease`, `fail(retry=False)`, reap hết lượt → failed.
- `api/v1/`: 38 điểm cuối / 9 router, xác thực + phân quyền mọi điểm cuối, SSE nhật ký, `PATCH /documents/{id}`, lọc `q`.
- Frontend: nối toàn bộ màn hình với backend thật (xem CHECKLIST.md TASK-008).
- Scripts: `seed_demo.py`, `gen_synthetic_invoices.py`, `eval_run.py`, `eval/score.py`. Deploy: worker trong compose, volume `/data`, phông PDF, nginx profile https.
- Tài liệu: README (lưu đồ, workflow, công nghệ, lựa chọn model, báo cáo), ARCHITECTURE, SECURITY, DECISIONS (ADR-004..008).

**Evidence (chạy thật, không suy đoán):**
- `pytest` → `276 passed`, độ phủ 92% (`--cov=app`); `ruff check .` → All checks passed; `mypy app` → no issues (92 tệp).
- `scripts/verify` → `RESULT: PASS` (Secret scan, npm typecheck, npm build, pytest, ruff) — lần đầu PASS kể từ khi có script.
- E2E: uvicorn + worker thật + giao diện build, máy chủ mô hình GIẢ tương thích OpenAI (không có GPU), Playwright/Chromium → 20/20 bước PASS; log API/worker 0 dòng lỗi. Chuỗi trạng thái trong DB: `pending→claimed→running→needs_review→retrying→pending→claimed→running→succeeded`.
- Docker: build ảnh bằng Dockerfile của repo (bỏ riêng bước `apt-get` vì proxy sandbox trả 403 cho `deb.debian.org`) → thành công; container API + worker chạy trọn luồng: biên dịch → PUT phiên bản 2 → duyệt → 3 hoá đơn (2 đạt ghi Excel, 1 chờ xác nhận).

**Bug thật phát hiện + đã sửa (có test khoá lại):**
1. `job_queue` thật không có DEFAULT mức SQL cho `status/attempts` → enqueue lỗi NOT NULL (test cũ dùng DDL tự viết có DEFAULT nên không lộ).
2. Import vòng khi import một model trước `app.db.base` → chuyển danh sách model vào `app/models/__init__.py`.
3. Giữ khoá ghi SQLite suốt lời gọi mô hình → "database is locked" (ADR-008).
4. QC-06 so trùng với chính extraction cũ của cùng chứng từ → bản sửa tay luôn trượt QC-06.
5. `xlsx.append_rows` ghi tiêu đề xuống dòng 2 với tệp đích mới.
6. Upload ghi `llm_calls` 2 lần/lời gọi.
7. Bản build frontend mặc định chế độ dữ liệu giả → bản triển khai không gọi backend.
8. `LLM_API_KEY` rỗng → header `Bearer ` không hợp lệ, mọi lời gọi mô hình + `/health` lỗi.
9. Frontend gọi `/workflows/{employee_id}`; nút "Duyệt và kích hoạt", "Từ chối" không gọi API; bảng người dùng ở Cấu hình viết cứng.
10. `docker-compose.yml` lưu DB ngoài volume `/data`, thiếu worker; `make lint` gọi `npm run lint` không tồn tại.
11. Tên tệp người dùng chèn thô vào `Content-Disposition`.

**Giả định/quyết định cần Toàn xác nhận:**
1. ADR-004 — bỏ thư viện CrewAI khỏi `requirements.txt` (code không import; `PROJECT.md` còn ghi CrewAI). `requirements-no-crewai.txt` và `.req_temp.txt` nay trùng/thừa — chưa xoá, chờ Owner.
2. ADR-006 — sau xác nhận, run chỉ chạy lại nhánh ĐẠT cho chứng từ vừa duyệt.
3. Quyền: USER được xác nhận chứng từ + xuất báo cáo; MANAGER tạo/duyệt/chạy/huỷ nhân viên AI; `/admin/metrics` mọi người dùng xem (chấm đỏ thanh điều hướng).
4. Tạo nhân viên AI chỉ lưu khi biên dịch thành công (lỗi → không tạo bản ghi rác, nhưng mô tả vẫn lưu vào audit_logs).
5. Chỉ số: `minutes_per_doc` = cấu hình `manual_minutes_per_doc` (mặc định 4 phút tiết kiệm/chứng từ); báo cáo chỉ tính chứng từ `ok`.

**Còn lại (chưa làm / chưa kiểm được):**
- Chạy `make eval-data && make eval` trên máy có vLLM + Qwen3-VL để xác nhận ≥90% trường đúng, ≤25 giây/hoá đơn.
- Build Docker đầy đủ bước `apt-get` ở mạng có truy cập `deb.debian.org`.
- LDAP, sao lưu tự động (`BACKUP_PATH`), rate limit đăng nhập, tự host phông JetBrains Mono cho mạng offline, `deskew()` (vẫn no-op từ TASK-006).

---

## Task: TASK-001 — Hiện thực `domain/validators.py` (V-1 → V-5)

**Status:** DONE (2026-08-28, Claude tự implement + tự verify — có evidence bên dưới)

**Completed:**
- `schemas/workflow_spec.py`, `domain/qc_rules.py`, `domain/state.py` — xong 2026-08-27.
- `PROJECT.md` / `SPEC.md` / `ARCHITECTURE.md` — draft xong 2026-08-28, chờ Toàn duyệt.
- `.clinerules` — tạo 2026-08-28, nay không còn cần thiết vì đã gỡ Cline; giữ lại không xoá (không có hại, có thể tái dùng nếu cài lại Cline sau này).
- **TASK-001 — `domain/validators.py`** (2026-08-28):
  - Hiện thực đủ V-1 → V-5 theo đúng docstring gốc (không đổi thiết kế).
  - V-5 phần cron: dùng `apscheduler.triggers.cron.CronTrigger.from_crontab()` — apscheduler đã sẵn trong `requirements.txt`, không thêm dependency mới.
  - `tools` truyền vào `validate_spec()` là ánh xạ duck-typed (dict/object: `is_enabled, input_schema, output_schema, required_params`) — không import `app/tools/base.py` (còn stub) hay bất cứ gì từ `adapters/api/workers`, giữ đúng ranh giới `domain/`.
  - Viết 17 test case trong `tests/unit/test_validators.py` (≥1 case cho mỗi V-1..V-5, có cả ca pass lẫn ca fail; V-3 có ca dựng chu trình 3 bước đúng yêu cầu gốc của file test).
  - **Sửa hạ tầng test bị nghẽn:** `backend/pyproject.toml` thiếu `pythonpath = ["."]` trong `[tool.pytest.ini_options]` → pytest báo `ModuleNotFoundError: No module named 'app'` (cùng gốc lỗi đã ghi trong `memory.md` OS Brain cho `scripts/test_llm.py`, nhưng chưa ai áp cho pytest). Đã thêm 1 dòng cấu hình, xác minh lại bằng test import thật trước/sau. Không đổi hành vi code, chỉ sửa cấu hình test.
  - **Evidence — pytest (Must pass):**
    ```
    cd backend && .venv/Scripts/pytest.exe tests/unit/test_validators.py -v
    ...
    collected 17 items
    tests\unit\test_validators.py .................          [100%]
    17 passed in 0.27s
    ```
  - **Evidence — ruff (chỉ 2 file của task):** `ruff check app/domain/validators.py tests/unit/test_validators.py` → `All checks passed!`
  - **Evidence — mypy:** `mypy app/domain/validators.py` → `Success: no issues found in 1 source file`
  - **Phát hiện phụ (KHÔNG thuộc phạm vi TASK-001, không tự sửa):** chạy `bash scripts/verify` toàn dự án → `npm typecheck` PASS, `npm build` PASS, `pytest` PASS (17 passed), nhưng **`ruff check .` FAIL với 41 lỗi** trong 6 file khác đã hiện thực từ 2026-08-27 (`adapters/llm_openai_compatible.py`, `db/base.py`, `domain/qc_rules.py`, `domain/state.py`, `ports/llm.py`, `schemas/workflow_spec.py`) — chủ yếu `UP035/UP007` (kiểu `Optional[X]`/`Sequence` cũ, nên đổi `X | None`/`collections.abc`) + vài dòng quá 100 ký tự. Không liên quan tới `validators.py`. Đã tách thành task riêng (spawn_task `task_b232c26f` — "Dọn lint ruff cho 6 file backend đã hiện thực trước đó") để không lẫn vào review TASK-001.
  - Không có sai khác so với docstring gốc, không có giả định mới cần Toàn xác nhận cho riêng file này.

**Current:**
- TASK-001 xong. `scripts/verify` toàn dự án hiện **FAIL** — nhưng lý do là lint debt có sẵn (mục trên), không phải do TASK-001. Cần Toàn quyết định: xử lý task lint đã tách riêng ngay, hay để dồn xử lý 1 lần sau khi có thêm vài file nữa.

**Task: TASK-002 — Hiện thực `domain/compiler.py`**

**Status:** DONE (2026-08-28) — Cline CLI 2.0 viết bản đầu (headless, provider `openai-compatible`), Claude Code tự review + sửa 1 bug + tự verify.

**Completed (TASK-002):**
- `compile(text, llm, tools) -> tuple[WorkflowSpec | None, list[SpecError]]` — luồng `classify_intent` → `extract_params` → `validate_spec`, thử lại tối đa 3 lần, đính kèm lỗi lần trước vào prompt lần sau. Đúng ADR-002 (không vòng lặp agent tự chủ).
- `PROMPT_VERSION = "v1"` + log qua `structlog` ở mỗi lần gọi model (không thêm field vào `WorkflowSpec` vì `extra="forbid"`).
- **Bug thật phát hiện khi review (không phải từ test — test lúc đó chưa cover ca này):** nếu cả 3 lần `extract_params` đều lỗi cấu trúc Pydantic (`ValidationError`, không phải lỗi kết nối LLM), `compile()` trả về `(None, [])` — spec rỗng nhưng `errors` cũng rỗng, dễ khiến caller hiểu nhầm là hợp lệ. **Đã tự sửa** (thêm `SpecError(rule="COMPILE-2", ...)` khi rơi vào ca này) + thêm test hồi quy `test_compile_returns_compile_2_when_structure_always_invalid`.
- Ghi chú của Cline trong code (NOTE, không phải fact): vị trí gọi `structlog` đặt ở `compile()` thay vì bên trong `classify_intent`/`extract_params` để giữ nguyên chữ ký 2 hàm đó theo đúng yêu cầu — cần Owner xác nhận nếu muốn đổi.
- **Evidence — pytest:**
  ```
  cd backend && .venv/Scripts/pytest.exe tests/unit/test_compiler.py tests/unit/test_validators.py -v
  collected 31 items
  tests\unit\test_compiler.py ..............                               [ 45%]
  tests\unit\test_validators.py .................                          [100%]
  31 passed in 0.39s
  ```
- **Evidence — ruff:** `ruff check app/domain/compiler.py tests/unit/test_compiler.py` → `All checks passed!`
- **Evidence — mypy:** `mypy app/domain/compiler.py` → `Success: no issues found in 1 source file`
- **Evidence — scripts/verify toàn dự án:** `[PASS] Secret scan`, `[PASS] npm typecheck`, `[PASS] npm build`, `[PASS] pytest`, `[FAIL] ruff check` — vẫn đúng 41 lỗi debt cũ từ TASK-001 (task `task_b232c26f`), không phát sinh lỗi mới.
- Không đụng `schemas/workflow_spec.py`, `domain/validators.py`, `domain/qc_rules.py`, `domain/state.py` (đã kiểm bằng `git diff --stat`).
- Đã `git init` (project trước đó chưa có git) + commit baseline trước khi chạy Cline, rồi commit riêng kết quả TASK-002 sau khi review xong — có lịch sử revert được.
- **Quy trình mới ghi vào skill (2026-08-28):** Cline chạy qua CLI headless thật (`cline -P openai-compatible -c <project> "<task>"`), không còn khối giao task chép tay — xem `.claude/rules/20-collaboration.md`. Owner yêu cầu mọi lần chạy việc thật phải mở trực tiếp VS Code + terminal tail log cho Owner xem, không chạy ngầm im lặng — đã ghi thành quy tắc bắt buộc trong cùng file.

**Task: TASK-003 — Hiện thực `ports/queue.py` + `adapters/queue_sqlite.py`**

**Status:** DONE (2026-08-28) — Cline CLI viết, Claude Code review **không phát hiện bug** (khác TASK-002).

**Completed (TASK-003):**
- **Phát hiện + tự sửa TRƯỚC khi giao Cline:** `db/session.py` (đã làm ở phiên trước) chưa tắt "autobegin" ngầm của driver pysqlite — `BEGIN IMMEDIATE` tường minh (bắt buộc theo ADR-001) sẽ lỗi "cannot start a transaction within a transaction". Đã thêm `isolation_level=None` + event `begin` tuỳ chỉnh, hỗ trợ bật `BEGIN IMMEDIATE` có chọn lọc qua `execution_options(sqlite_begin_immediate=True)` (không áp toàn cục, tránh ảnh hưởng phần khác của app sau này). **Đã tự verify bằng test đa luồng thật** (không chỉ đọc code): 2 connection giả lập 2 worker, connection B bị chặn 0.875s chờ A commit, sau đó thấy đúng giá trị — chứng minh khoá ghi hoạt động đúng. `/health` vẫn PASS sau khi sửa.
- `SQLiteJobQueue` (implements `JobQueue` Protocol): `enqueue()` dùng chung Session với caller (ADR-001, không tự commit); `claim()` dùng đúng giao thức `BEGIN IMMEDIATE` + SELECT + UPDATE + kiểm `rowcount`; `fail()` có backoff `min(30×2^attempts, 900) + nhiễu ngẫu nhiên`; `reap_expired()` thu hồi lease quá hạn.
- **Test quan trọng nhất:** `test_claim_concurrent_only_one_worker_wins` — 2 thread thật cùng `claim()` 1 job trên **file SQLite thật** (không dùng `:memory:` vì mỗi connection `:memory:` là DB riêng, không mô phỏng đúng đụng độ), dùng `threading.Barrier` đồng bộ thời điểm bắt đầu — assert đúng 1 worker thắng. **Đã chạy 5 lần liên tiếp, không flaky.**
- **Evidence — pytest (toàn bộ, 41 test):**
  ```
  cd backend && .venv/Scripts/pytest.exe -v
  tests\unit\test_compiler.py     ..............  [ 34%]
  tests\unit\test_queue_sqlite.py ..........      [ 58%]
  tests\unit\test_validators.py   .................[100%]
  41 passed in 0.79s
  ```
  (chạy riêng `test_queue_sqlite.py` 5 lần liên tiếp — luôn `10 passed`, không flaky)
- **Evidence — ruff:** `ruff check app/ports/queue.py app/adapters/queue_sqlite.py tests/unit/test_queue_sqlite.py` → `All checks passed!`
- **Evidence — mypy:** `mypy app/ports/queue.py app/adapters/queue_sqlite.py` → `Success: no issues found in 2 source files`
- **Evidence — scripts/verify toàn dự án:** PASS hết trừ ruff (vẫn đúng 41 lỗi debt cũ, không phát sinh mới).
- Không đụng `db/session.py`, `db/base.py`, `schemas/workflow_spec.py`, `domain/*`, `ports/llm.py`, `adapters/llm_openai_compatible.py` (đã kiểm bằng `git diff --stat`).
- **Giả định cần Toàn xác nhận lại (ghi NOTE trong code):** (1) lược đồ cột bảng `job_queue` — suy từ SQL trong docstring gốc, chưa có model ORM/Alembic migration thật; (2) trạng thái `'succeeded'` — không có trong 3 trạng thái docstring gốc liệt kê (pending/claimed/failed), cần thiết để phân biệt "xong" với "chờ"/"lỗi".

**Task: TASK-004 — Hiện thực `ports/storage.py` + `adapters/storage_local.py`**

**Status:** DONE (2026-08-28) — Cline CLI viết, Claude Code review không phát hiện bug.

**Completed (TASK-004):**
- Lần chạy đầu tiên **lỗi thật** ("request body rejected... malformed messages") — nguyên nhân: codepage console Windows máy này là **437** (không phải UTF-8), Cline đọc file `.md` tiếng Việt qua lệnh PowerShell (`Get-Content`) làm vỡ encoding, text vỡ lẫn vào request gửi model. Đã sửa `.clinerules` (mục 2.5 mới) + nhắc thẳng trong prompt: bắt buộc dùng tool đọc file gốc, không qua shell cho nội dung file. Chạy lại thành công.
- `LocalFileStorage`: lưu tệp theo `<sha256[:2]>/<sha256[2:4]>/<sha256><ext>` tương đối `base_path`; khử trùng bằng kiểm sha256+kích thước trước khi ghi lại; ghi nguyên tử qua tệp tạm + `os.replace()`.
- **Evidence — pytest (toàn bộ, 50 test):**
  ```
  tests\unit\test_compiler.py     ..............  [ 28%]
  tests\unit\test_queue_sqlite.py ..........      [ 48%]
  tests\unit\test_storage_local.py .........      [ 66%]
  tests\unit\test_validators.py   .................[100%]
  50 passed in 0.88s
  ```
- **Evidence — ruff:** `All checks passed!` — **mypy:** `Success: no issues found in 2 source files`
- **Evidence — scripts/verify toàn dự án:** PASS hết trừ ruff (vẫn đúng 41 lỗi debt cũ, không phát sinh mới).
- Không đụng file ngoài `Allowed files` (đã kiểm `git diff --stat` cho `core/config.py`, `db/*`, `domain/*`, `ports/queue.py`, `adapters/queue_sqlite.py`, `schemas/*`).
- **Giả định cần Toàn xác nhận (NOTE trong code):** không thêm lớp `"artifacts/"` vào đường dẫn vì `settings.STORAGE_PATH` mặc định đã là `"./data/artifacts"` — tránh trùng lặp `"artifacts/artifacts/..."`.

**Task: TASK-005a — Hiện thực `models/user.py` + `employee.py` + `workflow.py` (9 bảng)**

**Status:** DONE (2026-08-28) — Claude Code tự thiết kế lược đồ đầy đủ 20 bảng/7 file trước (không có "Phụ lục A" trong repo — dựa trên docstring gốc + `frontend/src/api/types.ts`/`mock/data.ts` đã dựng UI thật + đối chiếu ngược `domain/state.py`/`ports/storage.py`/`ports/queue.py` đã xong), Cline CLI viết code nhóm A/B/C theo đúng đặc tả, Claude Code review phát hiện + tự sửa 4 bug thật.

**Completed (TASK-005a):**
- **Bug hạ tầng phát hiện trước khi bắt đầu (không phải do Cline):** `.gitignore` có dòng `models/` không neo gốc repo — vô tình khớp luôn `backend/app/models/` (source code), khiến TOÀN BỘ model (kể cả bản stub gốc) chưa từng được git track từ đầu dự án. Sửa thành `/models/`.
- **4 bug thật Claude tự phát hiện + sửa khi review** (Cline hết giờ do lạc hướng tìm "Must pass" trong `IMPLEMENTATION_PLAN.md` — lần này giao task trực tiếp qua prompt, không ghi vào file trước, để lại bài học ở mục Ghi chú bên dưới):
  1. `Mapped["X" | None]` (quote lẫn với `| None` ngoài quote) → SyntaxError khi SQLAlchemy de-stringify. Sửa thống nhất, sau đó `ruff --fix` chuyển về dạng không quote (`Mapped[X | None]`) — đã tự verify lại bằng pytest trước khi giữ bản ruff, không tin ruff mù quáng.
  2. `WorkflowEdge.workflow` thiếu `primaryjoin`/`foreign_keys` tường minh (vì `workflow_id` không có `ForeignKey` đơn, chỉ nằm trong FK ghép) — SQLAlchemy không tự suy được join, lỗi `InvalidRequestError` khi mapper configure.
  3. Insert `workflow_steps` + `workflow_edges` (FK ghép) trong cùng transaction bị SQLite chặn vì thứ tự insert không đảm bảo steps luôn trước edges — sửa bằng `PRAGMA defer_foreign_keys=ON` trong event `begin` của `db/session.py` (hoãn kiểm tra FK tới COMMIT thay vì từng câu lệnh). **Đây là thay đổi hạ tầng ảnh hưởng TOÀN app**, không riêng models — đã re-verify: `/health` PASS, test đồng thời TASK-003 chạy 5 lần liên tiếp vẫn ổn định.
  4. (Bug ở TEST, không phải schema) WAL snapshot isolation: session đang giữ transaction cũ vẫn thấy dữ liệu "trễ" sau khi 1 session khác COMMIT từ ngoài — sửa bằng `session.rollback()` trước khi đọc lại, không phải lỗi CASCADE/SET NULL (đã tự verify CASCADE/SET NULL hoạt động đúng ở DB bằng script độc lập trước khi kết luận).
- Thêm import 9 model mới vào `db/base.py` (import vòng với `models/*.py` — đã verify hoạt động đúng bằng `Base.metadata.create_all()` thật, không chỉ đọc code).
- **Evidence — pytest (toàn bộ, 57 test):**
  ```
  tests\unit\test_compiler.py       ..............  [ 24%]
  tests\unit\test_models_group_a.py .......         [ 36%]
  tests\unit\test_queue_sqlite.py   ..........      [ 54%]
  tests\unit\test_storage_local.py  .........       [ 70%]
  tests\unit\test_validators.py     .................[100%]
  57 passed in 1.36s
  ```
  (test đồng thời TASK-003 riêng chạy lại 5 lần liên tiếp — luôn `10 passed`)
- **Evidence — ruff:** `All checks passed!` (5 file: 3 model + `db/session.py` + test) — **mypy:** `Success: no issues found in 4 source files`
- **Evidence — `/health`:** PASS (database/storage/llm đều ok) sau khi sửa `db/session.py` 2 lần trong task này.
- **Evidence — scripts/verify toàn dự án:** PASS hết trừ ruff (vẫn đúng 41 lỗi debt cũ, không phát sinh mới).
- **Ghi chú quy trình (bài học, đã cập nhật `.claude/rules/20-collaboration.md`):** giao task trực tiếp qua prompt CLI (không ghi vào `IMPLEMENTATION_PLAN.md` trước) khiến Cline mất nhiều thời gian tìm sai chỗ lệnh "Must pass" — task lớn/phức tạp nên ghi khối task vào `IMPLEMENTATION_PLAN.md` trước khi gọi `cline`, không chỉ truyền qua đối số dòng lệnh.

**Task: TASK-005b — Hiện thực `models/run.py` + `extraction.py` + `artifact.py` + `audit.py` (Nhóm D-G, 11 bảng)**

**Status:** DONE (2026-08-29) — Cline CLI hiện thực, Claude Code tự review độc lập (không chỉ tin báo cáo của Cline) — **không phát hiện bug**.

**Review độc lập của Claude Code (2026-08-29) — chạy lại TỪ ĐẦU, không dựa vào log Cline:**
- `git diff --stat`: đúng phạm vi Allowed files (`db/base.py` + 4 model mới + `IMPLEMENTATION_PLAN.md` + test mới); các thay đổi frontend đang có trong working tree là của Owner từ trước, Cline không đụng vào.
- `pytest -v` (tự chạy lại): `73 passed in 2.17s` — khớp báo cáo.
- `ruff check app/models/run.py app/models/extraction.py app/models/artifact.py app/models/audit.py app/db/base.py tests/unit/test_models_group_d.py` → `All checks passed!`
- `mypy` 4 file model → `Success: no issues found in 4 source files`.
- Tự chạy `Base.metadata.create_all(engine)` trên engine thật (`app/db/session.py`) → 21 bảng, liệt kê đủ tên, không lỗi FK.
- Tự `PRAGMA table_info(job_queue)` trên DB thật → xác nhận `available_at/lease_until/created_at` là `VARCHAR`, KHÔNG có cột `updated_at` — khớp CHÍNH XÁC SQL thô trong `adapters/queue_sqlite.py`.
- Đọc trực tiếp toàn bộ 4 file model (không chỉ chạy test) — không phát hiện bug thật nào (khác TASK-002/005a); các quyết định `viewonly=True` cho 2 relationship một-chiều trùng cột FK (`Extraction.human_reviews`, `Artifact.documents`) là cách xử lý đúng, tránh SAWarning "copy column" mà TASK-005a từng gặp dạng khác.
- `bash scripts/verify` toàn dự án: `[PASS]` Secret scan, npm typecheck, npm build, pytest — `[FAIL]` ruff, nhưng đếm lại còn **38 lỗi** (giảm từ 41, vì `db/base.py` được phép sửa 3 lỗi `UP017` có sẵn để thoả Must pass) — xác nhận bằng `ruff check .` liệt kê file, cả 38 lỗi đều nằm ở 5 file debt cũ (`adapters/llm_openai_compatible.py`, `domain/qc_rules.py`, `domain/state.py`, `ports/llm.py`, `schemas/workflow_spec.py`), không có lỗi mới trong 4 file TASK-005b.
- Đọc `tests/unit/test_models_group_d.py` (16 test) — xác nhận không phải test hời hợt: có test cascade xoá Run/Document, test SET NULL khi xoá Extraction, và test `typeof()` SQLite xác nhận `job_queue` lưu TEXT thật (không phải DateTime).

Goal:
Hiện thực đầy đủ 4 file model còn lại (11 bảng cuối cùng của toàn bộ schema DB), theo đúng style đã dùng ở `models/user.py`/`employee.py`/`workflow.py` (TASK-005a): `class X(Base, TimestampMixin)`, `Mapped[...]`/`mapped_column`, FK có `ondelete` rõ ràng, JSON dùng `Text`, `__table_args__` cho Index/UniqueConstraint, relationship 2 chiều `back_populates` (trừ các chỗ ghi rõ "một chiều" bên dưới).

Allowed files:
- `backend/app/models/run.py`
- `backend/app/models/extraction.py`
- `backend/app/models/artifact.py`
- `backend/app/models/audit.py`
- `backend/app/db/base.py` (CHỈ thêm 4 dòng import model mới vào cuối, đúng như TODO đã ghi sẵn ở file này — không sửa gì khác)
- `backend/tests/unit/test_models_group_d.py` (file mới)

Requirements — lược đồ CHÍNH XÁC từng cột (không tự thêm/bớt cột ngoài danh sách này):

### `models/run.py`

**Run (`runs`)**
- `id` PK autoincrement
- `employee_id` FK `ai_employees.id` ondelete=CASCADE, not null
- `workflow_id` FK `workflows.id` ondelete=RESTRICT, not null (bản workflow đã chạy)
- `trigger_type` String(20) not null — `manual|cron|file_watch`
- `status` String(20) not null default `'pending'` — **PHẢI dùng đúng giá trị chữ THƯỜNG của `domain/state.py` RunStatus** (`pending,claimed,running,retrying,needs_review,succeeded,failed,cancelled`). Frontend `RunStatus` dùng chữ HOA — đó là việc của tầng API schema sau này, KHÔNG phải của models/.
- `started_at` DateTime(timezone=True) nullable
- `finished_at` DateTime(timezone=True) nullable
- `error_message` Text nullable
- `created_by` FK `users.id` ondelete=SET NULL, nullable (NULL nếu do cron/file_watch kích hoạt)
- + TimestampMixin
- **KHÔNG thêm cột `doc_count`/`stats` denormalize** — đúng tiền lệ `AIEmployee` (TASK-005a): đây là giá trị JOIN/tính toán ở service layer, không lưu ở models/.
- relationship: `employee`, `workflow`, `created_by_user` (một chiều), `steps` (list[RunStep], cascade `all, delete-orphan`, order_by `RunStep.order_index`), `logs` (list[RunLog], cascade `all, delete-orphan`, order_by `RunLog.created_at`), `job_queue_entries` (list[JobQueueEntry], cascade `all, delete-orphan`)

**RunStep (`run_steps`)**
- `id` PK, `run_id` FK `runs.id` ondelete=CASCADE not null
- `step_key` String(32) not null (copy snapshot từ `workflow_steps.step_key` lúc run bắt đầu — KHÔNG FK tới `workflow_steps`, vì workflow có thể đổi version sau khi run đã tạo)
- `order_index` Integer not null
- `label` String(200) not null
- `status` String(20) not null default `'PENDING'` — khớp chữ HOA `StepStatus` frontend (`PENDING,RUNNING,SUCCEEDED,FAILED,SKIPPED`) vì không có domain enum nào chi phối riêng step status
- `detail` Text nullable
- `duration_ms` Integer nullable
- `__table_args__`: `UniqueConstraint("run_id", "step_key")`
- + TimestampMixin
- relationship: `run` (back_populates=`steps`)

**RunLog (`run_logs`)**
- `id` PK, `run_id` FK `runs.id` ondelete=CASCADE not null
- `level` String(10) not null default `'INFO'` — `DEBUG|INFO|WARN|ERROR` (khớp frontend `LogLine.level`)
- `message` Text not null
- `from_status` String(20) nullable, `to_status` String(20) nullable — chỉ có giá trị khi dòng này ghi lại 1 lần transition (`domain/state.py transition()` gọi `log_fn(run, from_status, to_status, reason, at)` — `message` = `reason`)
- + TimestampMixin (`created_at` dùng làm `ts` khi stream SSE)
- **NOTE bắt buộc ghi trong code:** 1 bảng `run_logs` phục vụ CẢ (1) log transition từ `domain/state.py` lẫn (2) log tiến trình chung để `GET /runs/{id}/logs` (SSE) stream — đây là SUY LUẬN hợp nhất 2 nhu cầu vì docstring gốc chỉ liệt kê 1 bảng `run_logs`, không tách 2 bảng. Cần Toàn xác nhận lại.
- relationship: `run` (back_populates=`logs`)

**JobQueueEntry (`job_queue`)** — ⚠️ đọc kỹ comment đầu `backend/app/adapters/queue_sqlite.py` trước khi viết, PHẢI khớp CHÍNH XÁC:
- `id` PK autoincrement
- `run_id` FK `runs.id` ondelete=CASCADE not null
- `status` String(10) not null default `'pending'` — `pending|claimed|failed|succeeded`
- `priority` Integer not null default 0
- `available_at` **String(32) not null** — TEXT ISO8601 (`%Y-%m-%dT%H:%M:%S.%fZ`), **KHÔNG dùng DateTime**
- `claimed_by` String(100) nullable
- `lease_until` **String(32) nullable** — TEXT ISO8601, KHÔNG dùng DateTime
- `attempts` Integer not null default 0
- `max_attempts` Integer not null default 5
- `last_error` Text nullable
- `created_at` **String(32) not null** — TEXT ISO8601
- **Class này CHỈ kế thừa `Base`, KHÔNG kế thừa `TimestampMixin`** (SQL gốc trong `queue_sqlite.py` không có cột `updated_at`, và `created_at`/timestamp khác đều là TEXT chứ không phải `DateTime` như `TimestampMixin` tạo ra)
- relationship: `run` (back_populates=`job_queue_entries`)
- **KHÔNG sửa `adapters/queue_sqlite.py`** — file đó tiếp tục dùng SQL thô như hiện tại (đã test kỹ, ngoài phạm vi task này), model này chỉ để Alembic autogenerate nhìn thấy đúng bảng.

### `models/extraction.py`

**Extraction (`extractions`)**
- `id` PK, `document_id` FK `documents.id` ondelete=CASCADE not null
- `run_id` FK `runs.id` ondelete=SET NULL, **nullable** (NULL nếu trích xuất qua upload trực tiếp không qua workflow/run)
- `schema_version` String(20) not null, `model_name` String(100) not null
- `confidence` Numeric(5,4) nullable, `latency_ms` Integer not null
- `invoice_no` String(50) nullable, **indexed** (dùng cho QC-06 `existing_invoice_numbers` + lọc danh sách)
- `issue_date` Date nullable, indexed (lọc khoảng ngày)
- `seller_name` String(200) nullable, `seller_tax_code` String(20) nullable, `currency` String(10) nullable
- `subtotal` Numeric(18,2) nullable, `vat_rate` Numeric(5,2) nullable, `vat_amount` Numeric(18,2) nullable, `total` Numeric(18,2) nullable — **Decimal, KHÔNG BAO GIỜ float** (quy tắc kiến trúc bắt buộc)
- `extracted_data_json` Text not null — toàn bộ `InvoiceData` (kể cả `line_items[]`)
- + TimestampMixin
- **NOTE bắt buộc ghi trong code:** các cột `invoice_no/issue_date/seller_name/seller_tax_code/subtotal/vat_rate/vat_amount/total` là bản SAO CHÉP có chủ đích từ `extracted_data_json` — KHÁC quyết định "không denormalize" ở `AIEmployee`/`Document` bên dưới, vì đây là giá trị GỐC cần filter/sort/unique-check trực tiếp bằng SQL (QC-06, lọc theo ngày/nhà cung cấp), không phải giá trị tính toán qua JOIN. Cần Toàn xác nhận lại.
- relationship: `document` (back_populates=`extractions`), `run` (một chiều), `qc_results` (list[QCResult], cascade `all, delete-orphan`), `human_reviews` (một chiều)

**QCResult (`qc_results`)**
- `id` PK, `extraction_id` FK `extractions.id` ondelete=CASCADE not null
- `rule_code` String(10) not null (`QC-01`..`QC-08`, khớp `domain/qc_rules.py`)
- `severity` String(10) not null (`warning|critical`), `passed` Boolean not null
- `field` String(100) nullable, `message` Text not null
- + TimestampMixin
- relationship: `extraction` (back_populates=`qc_results`)

**HumanReview (`human_reviews`)**
- `id` PK, `document_id` FK `documents.id` ondelete=CASCADE not null
- `extraction_id` FK `extractions.id` ondelete=SET NULL, nullable
- `reviewer_id` FK `users.id` ondelete=SET NULL, nullable
- `action` String(10) not null — `approve|correct|reject` (khớp `POST /reviews/{id}/resolve`)
- `corrected_data_json` Text nullable (chỉ có giá trị khi `action='correct'`)
- `note` Text nullable
- + TimestampMixin
- relationship: `document` (back_populates=`human_reviews`), `extraction` (một chiều), `reviewer` (một chiều, FK `users`)

### `models/artifact.py`

**Artifact (`artifacts`)**
- `id` PK, `sha256` String(64) not null unique indexed (khớp `ArtifactRef.sha256`)
- `path` String(500) not null (khớp `ArtifactRef.path`), `size_bytes` **BigInteger** not null (khớp `ArtifactRef.size_bytes`), `content_type` String(100) nullable (khớp `ArtifactRef.content_type`)
- + TimestampMixin
- relationship: `documents` (list[Document], một chiều — KHÔNG cascade delete document khi artifact bị xoá, `FileStorage.delete()` là thao tác vật lý riêng)

**Document (`documents`)**
- `id` PK, `artifact_id` FK `artifacts.id` ondelete=RESTRICT not null (không cho xoá artifact còn document tham chiếu)
- `filename` String(255) not null, `source_kind` String(10) not null (`image|pdf`)
- `status` String(20) not null default `'processing'` — `processing|ok|needs_review|rejected|failed` (khớp frontend `DocStatus`)
- `uploaded_by` FK `users.id` ondelete=SET NULL, nullable
- + TimestampMixin
- `__table_args__`: `Index("ix_documents_status", "status")`
- **NOTE bắt buộc ghi trong code:** KHÔNG lưu `invoice_no/issue_date/seller_name/total/qc_failed` trên `documents` dù `DocumentRow` (frontend) có các trường này — áp dụng ĐÚNG tiền lệ `AIEmployee` (TASK-005a): đây là giá trị JOIN với `Extraction` mới nhất theo `document_id` + đếm `qc_results.passed=False`, `services/document_service.py` tự JOIN khi trả `DocumentRow`. Đây là quyết định MỚI của Claude (không phải lặp lại TASK-005a) — cần Toàn xác nhận lại, đối chiếu với NOTE ngược lại ở `Extraction` phía trên (2 quyết định khác nhau, đừng nhầm lẫn khi review).
- relationship: `artifact` (FK), `uploaded_by_user` (một chiều), `extractions` (list[Extraction], cascade `all, delete-orphan`, order_by `Extraction.created_at`), `human_reviews` (list[HumanReview], cascade `all, delete-orphan`)

### `models/audit.py`

**AuditLog (`audit_logs`)**
- `id` PK, `user_id` FK `users.id` ondelete=SET NULL, nullable (NULL nếu hệ thống tự ghi)
- `action` String(100) not null (vd `'document.extraction.correct'`), `entity_type` String(50) nullable, `entity_id` Integer nullable (KHÔNG FK — đa hình, trỏ nhiều bảng khác nhau tuỳ `entity_type`)
- `detail_json` Text nullable
- + TimestampMixin
- relationship: `user` (một chiều, KHÔNG back_populates)

**LlmCall (`llm_calls`)**
- `id` PK, `run_id` FK `runs.id` ondelete=SET NULL nullable, `document_id` FK `documents.id` ondelete=SET NULL nullable
- `model_name` String(100) not null, `prompt_tokens` Integer nullable, `completion_tokens` Integer nullable, `latency_ms` Integer not null
- `status` String(20) not null (`success|error`), `error_message` Text nullable
- + TimestampMixin
- Đây chính là bảng `llm_calls` mà `adapters/llm_openai_compatible.py` còn thiếu ghi 1 dòng cho mỗi lời gọi (xem `ARCHITECTURE.md`) — TASK-005b **chỉ tạo bảng**, việc nối `adapters/llm_openai_compatible.py` ghi vào bảng này là task RIÊNG sau, KHÔNG tự làm trong task này.
- relationship: `run` (một chiều), `document` (một chiều)

**Setting (`settings`)**
- `key` String(100) **primary_key** (vd `'LLM_BASE_URL_OVERRIDE'`)
- `value_json` Text not null
- `updated_by` FK `users.id` ondelete=SET NULL, nullable
- + TimestampMixin (`updated_at` có ý nghĩa thật ở bảng này — lần sửa cấu hình gần nhất)

### `db/base.py`
Thêm 4 dòng import (theo đúng comment TODO đã có sẵn ở cuối file):
```python
from app.models.run import JobQueueEntry, Run, RunLog, RunStep  # noqa: E402,F401
from app.models.extraction import Extraction, HumanReview, QCResult  # noqa: E402,F401
from app.models.artifact import Artifact, Document  # noqa: E402,F401
from app.models.audit import AuditLog, LlmCall, Setting  # noqa: E402,F401
```

### `tests/unit/test_models_group_d.py`
Theo đúng phong cách `tests/unit/test_models_group_a.py` (TASK-005a): tối thiểu 1 test tạo round-trip cho mỗi bảng trong 11 bảng (insert + query lại đúng giá trị), CỘNG THÊM:
- 1 test cascade xoá `Run` → `run_steps`/`run_logs`/`job_queue_entries` bị xoá theo
- 1 test cascade xoá `Document` → `extractions`/`human_reviews` bị xoá theo, nhưng xoá `Extraction` thì `human_reviews.extraction_id` chuyển `NULL` (SET NULL) chứ không xoá `human_reviews`
- 1 test xác nhận `job_queue.available_at`/`created_at` lưu đúng kiểu chuỗi TEXT (không phải kiểu ngày giờ) — đối chiếu định dạng với `adapters/queue_sqlite.py._fmt()`

Must pass:
- `cd backend && .venv/Scripts/pytest.exe -v` — TOÀN BỘ test phải pass (hiện đang 57 passed, sau task này phải tăng lên, không được giảm)
- `.venv/Scripts/ruff.exe check app/models/run.py app/models/extraction.py app/models/artifact.py app/models/audit.py app/db/base.py tests/unit/test_models_group_d.py` → `All checks passed!`
- `.venv/Scripts/mypy.exe app/models/run.py app/models/extraction.py app/models/artifact.py app/models/audit.py` → `Success: no issues found`
- Script xác nhận `Base.metadata.create_all()` chạy được không lỗi FK (test tương tự cách TASK-005a đã verify qua import vòng `db/base.py`↔`models/*.py`)

Do not:
- Sửa `models/user.py`, `employee.py`, `workflow.py` (TASK-005a đã DONE, không đụng lại)
- Sửa bất kỳ file nào trong `domain/`, `ports/`, `adapters/`, `api/`, `schemas/`, `services/`
- Đổi kiểu cột `job_queue` khác với SQL thô đã có trong `adapters/queue_sqlite.py`
- Thêm cột denormalize khác ngoài danh sách đã cho (đặc biệt: KHÔNG thêm `doc_count`/`stats` vào `runs`, KHÔNG thêm `invoice_no`/`total`/`qc_failed` vào `documents` — 2 quyết định NGƯỢC NHAU với `Extraction` đã ghi rõ NOTE ở trên, đọc kỹ trước khi code)
- Đổi ADR-001/ADR-002/ADR-003
- Thêm dependency mới

**Blocker:**
- Không còn. (Ghi chú lịch sử: dòng cũ ở đây từng nói "Cline/VS Code đã gỡ" — 2026-08-28 sau đó Owner cài lại Cline CLI 2.0 + mở lại VS Code để xem trực tiếp; không phải mâu thuẫn, là diễn biến thật trong cùng ngày, xem log chi tiết ở `02 - Projects/sme-ai-workforce/log.md` trong OS Brain.)

**Current:**
- TASK-005b đã hiện thực xong (Cline, 2026-08-29), chờ Claude Review. Bằng chứng thật từng lệnh Must pass:

  `pytest -v` (toàn bộ, baseline 57 → 73 passed, +16 test mới):
  ```
  collected 73 items
  tests\unit\test_compiler.py ..............                               [ 19%]
  tests\unit\test_models_group_a.py .......                                [ 28%]
  tests\unit\test_models_group_d.py ................                       [ 50%]
  tests\unit\test_queue_sqlite.py ..........                               [ 64%]
  tests\unit\test_storage_local.py .........                               [ 76%]
  tests\unit\test_validators.py .................                          [100%]
  ============================= 73 passed in 2.28s ==============================
  ```

  `ruff check app/models/run.py app/models/extraction.py app/models/artifact.py app/models/audit.py app/db/base.py tests/unit/test_models_group_d.py`:
  ```
  All checks passed!
  ```

  `mypy app/models/run.py app/models/extraction.py app/models/artifact.py app/models/audit.py`:
  ```
  Success: no issues found in 4 source files
  ```

  Script xác nhận create_all (import vòng `db/base.py` ↔ `models/*.py`, chạy trên engine thật từ `app/db/session.py`):
  ```
  create_all OK - 21 tables
  ```
  Lưu ý số bảng: 21 = 9 bảng TASK-005a + 12 bảng TASK-005b. Tiêu đề task ghi "11 bảng" nhưng đếm theo danh sách Requirements là 12 class/bảng (runs, run_steps, run_logs, job_queue, extractions, qc_results, human_reviews, artifacts, documents, audit_logs, llm_calls, settings) — Cline hiện thực đủ 12 theo từng dòng Requirements.

- Sai khác so với Requirements (cả 2 đều là điều kiện bắt buộc để thoả Must pass, KHÔNG đổi lược đồ cột):
  1. `db/base.py`: ngoài 4 dòng import model mới, còn phải sửa 3 lỗi ruff UP017 CÓ SẴN từ trước (`datetime.timezone.utc` → `datetime.UTC` trong TimestampMixin) vì Must pass bắt buộc `ruff check ... app/db/base.py → All checks passed!`; file nằm trong Allowed files nên được phép sửa — thay đổi cơ học, không đổi hành vi. NOTE cũ ("run.py/extraction.py/... VẪN LÀ STUB") hết giá trị nên thay bằng chú thích "Nhóm A-G". 7 dòng import xếp theo thứ tự isort (artifact, audit, employee, extraction, run, user, workflow) — nếu để thứ tự "run, extraction, artifact, audit" như bản mẫu, ruff I001 sẽ fail; nội dung từng dòng giữ nguyên bản mẫu.
  2. `Extraction.human_reviews` và `Artifact.documents`: Requirements ghi "một chiều" — hiện thực MỘT CHIỀU + `viewonly=True` (không back_populates) để tránh SAWarning "relationship will copy column ... conflicts" khi flush; toàn bộ pytest chạy không có warning. Không đổi gì về cột.

- Giả định Cline tự quyết / ghi NOTE trong code, cần Claude/Owner xác nhận lại:
  1. 3 quyết định đã có NOTE trong docstring code (đều do Claude soạn sẵn trong Requirements, Cline giữ nguyên, không tự đổi): (a) `Extraction` VẪN denormalize invoice_no/issue_date/seller_name/seller_tax_code/subtotal/vat_rate/vat_amount/total; (b) `Document` KHÔNG có invoice_no/total/qc_failed; (c) `RunLog` 1 bảng phục vụ cả transition log (from_status/to_status) lẫn SSE stream log.
  2. `Run.status` chữ THƯỜNG (khớp domain/state.py RunStatus) — `RunStep.status` chữ HOA (khớp StepStatus frontend) — đúng Requirements.
  3. `JobQueueEntry` không kế thừa TimestampMixin + cột TEXT ISO8601 khớp `_fmt()` — đúng Requirements; adapter `queue_sqlite.py` không đụng tới.

- Nội dung test `tests/unit/test_models_group_d.py` (16 test): 1 test create_all đủ 12 bảng mới, 11 round-trip cho từng bảng (12 bảng, gộp `job_queue` test riêng), 2 cascade xoá (Run → steps/logs/job_queue; Document → extractions/human_reviews và Extraction → human_reviews SET NULL), 1 test `job_queue.available_at/created_at` là TEXT (khớp `_fmt()` của queue_sqlite, `typeof()` trả `('text', 'text')`).

**Sau TASK-005b:** `domain/templates/*.py` (đối chiếu lại 5 mã `TemplateCode`) → `services/*` → `api/v1/*` → `tools/*` → `agents/crew.py` (đọc ADR-002 trước) → `workers/*` → cuối cùng nối frontend vào API thật.

**Task: TASK-006 — Luồng upload chứng từ → AI đọc → QC → xem kết quả (bản tối giản, bỏ qua workflow/employee/job_queue)**

**Status:** DONE (2026-08-29) — Cline hiện thực phần lõi (schemas/services/api/deps/main), CRASH giữa chừng do lỗi nội bộ CLI (`hook dispatch failed`, không liên quan encoding/model) TRƯỚC khi kịp viết test. Claude Code tự đọc lại toàn bộ code Cline đã viết (không hỏng, đã tự sửa xong 1 file bị chèn lộn code trước khi crash), viết đủ 3 file test còn thiếu, tự review VÀ PHÁT HIỆN + SỬA 4 bug thật (1 nghiêm trọng — xem bên dưới).

Owner muốn thấy 1 luồng THẬT chạy được ngay trong ngày. Claude Code (Architect) quyết định CẮT PHẠM VI có chủ đích khỏi lộ trình gốc (domain/templates → services/* đầy đủ → 8 router) để ưu tiên 1 lát cắt dọc (vertical slice) demo được — xem "Phạm vi bị cắt" bên dưới.

**Sự cố Cline (2026-08-29):** Cline viết xong 9/10 file lõi đúng spec, nhưng khi tự sửa lỗi cấu trúc trong `documents.py` (code bị chèn lộn giữa các hàm) thì CLI crash với `hook dispatch failed: session.hook requires a valid hook event payload` + `The request body was rejected by the upstream provider as invalid`. Đọc lại log xác nhận: bản sửa cuối cùng của Cline ĐÃ ĐÚNG (compile sạch, không còn code lộn xộn) — crash xảy ra SAU khi sửa xong, khi Cline đang chuẩn bị bước tiếp theo. Claude Code không dispatch lại Cline (tránh rủi ro crash lần 2 tốn thêm lượt gọi) mà tự hoàn thiện phần còn thiếu (viết test) và tự review toàn bộ.

**4 bug thật Claude Code phát hiện + tự sửa khi review (đọc code thật + chạy `uvicorn app.main:app` thật, không chỉ tin pytest):**
1. **🔴 NGHIÊM TRỌNG — Import vòng vỡ khi khởi động server thật:** `uvicorn app.main:app` (lệnh Owner sẽ dùng để chạy app) CRASH ngay lập tức với `ImportError: cannot import name 'Artifact' from partially initialized module 'app.models.artifact' (circular import)`. Nguyên nhân: `app/api/v1/documents.py` import trực tiếp `app.models.artifact` — nếu đây là lần đầu tiên module đó được nạp (đúng trường hợp khi `uvicorn` nạp `app.main` từ đầu), nó kích hoạt `app.db.base` nạp LẦN ĐẦU, và `db/base.py` tự import ngược lại `app.models.artifact` trong khi module đó CHƯA nạp xong (mới chạy tới dòng import `Base`) → lỗi. `pytest` KHÔNG lộ ra bug này vì `tests/conftest.py` (Claude tự viết) tình cờ `from app.db.base import Base` TRƯỚC `from app.main import app`, khiến chuỗi model đã nạp xong sẵn trước khi `app.main` chạy. **Đã tự xác minh bằng cách chạy `uvicorn` thật** (không chỉ đọc code) — lỗi tái hiện, sau đó sửa `main.py` (thêm `from app.db.base import Base` TRƯỚC `from app.api.v1 import api_router`, có `# noqa: I001` vì thứ tự này cố ý ngược isort) — chạy lại `uvicorn` thật, `/health` PASS, `POST /api/v1/documents` thật (curl, ảnh PNG thật tự tạo) trả 200 thành công.
2. `app/api/v1/documents.py` — `list_documents()`: cột `qc_failed` dựng từ `scalar_subquery()` nhưng `.label("qc_failed")` bị gắn nhầm vào cột BÊN TRONG subquery thay vì chính `scalar_subquery()` — SQLAlchemy đặt tên cột ẩn danh, `row.qc_failed` ném `AttributeError` khi có ≥1 document trong danh sách. Lỗi này pytest CÓ bắt được (integration test `test_list_documents_reflects_uploaded_document` fail thật) — đã sửa bằng cách chuyển `.label("qc_failed")` ra ngoài `.scalar_subquery()`.
3. `app/utils/images.py` — `Image.LANCZOS` chạy được thật (Pillow 11.3.0 giữ alias tương thích ngược) nhưng type stub không còn khai báo (mypy báo lỗi) — đổi sang `Image.Resampling.LANCZOS` (API hiện hành từ Pillow 9.1+).
4. `app/services/document_service.py` — `_ensure_artifact()`: biến `artifact` được gán 2 kiểu khác nhau (`Artifact` rồi `Artifact | None`) trong 2 nhánh `if` khác nhau của cùng 1 hàm khiến mypy báo lỗi gán kiểu không tương thích — đổi tên biến nhánh thứ 2 thành `existing_artifact: Artifact | None` tường minh.

**Evidence — pytest (Claude tự viết `tests/conftest.py` + 3 file test, tự chạy lại):**
```
collected 94 items
tests\integration\test_api_documents.py ...........                      [ 11%]
tests\unit\test_compiler.py ..............                               [ 26%]
tests\unit\test_document_service.py ......                               [ 32%]
tests\unit\test_models_group_a.py .......                                [ 40%]
tests\unit\test_models_group_d.py ................                       [ 57%]
tests\unit\test_qc_service.py ....                                       [ 61%]
tests\unit\test_queue_sqlite.py ..........                               [ 72%]
tests\unit\test_storage_local.py .........                               [ 81%]
tests\unit\test_validators.py .................                          [100%]
94 passed in 2.56s
```
(baseline 73 → 94, +21 test: 15 unit mới `test_document_service.py`/`test_qc_service.py` + 6 tận dụng lại chỗ trống `tests/integration/test_api_documents.py` — file stub gốc đã có sẵn tên, Claude phát hiện và điền vào ĐÚNG file đó thay vì tạo file trùng tên mới)

**Evidence — ruff:** `ruff check` trên toàn bộ 14 file Allowed files + test → `All checks passed!`. `ruff check .` (toàn dự án) → 38 lỗi (không đổi so với TASK-005b, không phát sinh mới từ TASK-006).

**Evidence — mypy:** `mypy --follow-imports=silent` trên 9 file nguồn TASK-006 → `Success: no issues found in 9 source files` (dùng `--follow-imports=silent` để không kéo theo lỗi có sẵn của `domain/qc_rules.py`, đã phát hiện thêm 1 lỗi mypy debt cũ ở đó — NGOÀI PHẠM VI, không sửa, ghi vào Ghi chú bên dưới).

**Evidence — chạy SERVER THẬT (không phải TestClient), sau khi sửa bug #1:**
```
uvicorn app.main:app --port 8123
GET /health -> {"ok":true,"checks":{"database":{"ok":true},"storage":{"ok":true,...},"llm":{"ok":true,"status_code":200}}}
POST /api/v1/documents (multipart, ảnh PNG thật tự tạo bằng PIL) -> 200
  {"id":1,"filename":"test_invoice.png","status":"failed", ...}
```
`status="failed"` là ĐÚNG NHƯ MONG ĐỢI — đối chiếu `scripts/test_llm.py` (chạy thật) xác nhận `LLM_API_KEY` trong `.env` vẫn là placeholder → lỗi 401 thật từ OpenRouter, được `document_service.ingest()` bắt đúng và trả `status=failed` thay vì crash 500. Đã test thêm `GET /api/v1/documents` (thấy đúng document trong danh sách) và `GET /api/v1/documents/1/file` (tải lại đúng byte-for-byte file gốc, xác nhận bằng `cmp`). **Owner điền `LLM_API_KEY` thật vào `backend/.env` là có thể thấy trích xuất thật thành công ngay** — không cần sửa code gì thêm.
Đã dọn lại 2 bản ghi test (`documents`/`artifacts` id=1) khỏi `data/app.db` sau khi verify xong, để DB dev sạch cho Owner tự thử.

**Ghi chú/giả định cần Toàn xác nhận lại** (đã ghi NOTE trong code, xem Requirements ở trên): (1) trích xuất đồng bộ không qua job_queue; (2) không auth cho endpoint documents (CẢNH BÁO BẢO MẬT tạm thời); (3) `Party.tax_code`/`Totals.vat_rate` viết lỏng hơn mô tả gốc; (4) `deskew()` chưa hiện thực (no-op).

**Nợ kỹ thuật phát hiện thêm (KHÔNG sửa, ngoài phạm vi TASK-006):** `mypy` phát hiện `app/domain/qc_rules.py:120` có lỗi `union-attr` có sẵn (chưa từng bị `mypy` bắt vì trước giờ chỉ chạy `mypy` trên từng file lẻ, chưa ai chạy với `--follow-imports` kéo theo file này) — gộp chung vào task dọn lint/type debt đã tách riêng trước đó (`task_b232c26f`).

Goal:
Người dùng tải 1 ảnh hoá đơn lên qua API thật → hệ thống gọi LLM thật (Qwen3-VL qua OpenRouter, cần `LLM_API_KEY` thật trong `backend/.env`, Owner tự điền) → chạy 8 quy tắc QC → trả về kết quả đầy đủ (JSON) để xem được thật, không qua mock.

**Quyết định kiến trúc quan trọng cho task này (Claude tự quyết, cần Toàn xác nhận lại):**
1. **Trích xuất chạy ĐỒNG BỘ ngay trong `POST /documents`** (gọi LLM, chờ trả lời, chạy QC, rồi mới response) — KHÔNG qua `job_queue`/worker. Lý do: `workers/*.py` (worker + scheduler) vẫn là stub, ngoài phạm vi hôm nay; khớp acceptance criteria "≤25s/hoá đơn" nên chờ đồng bộ chấp nhận được cho demo. Luồng qua `job_queue` (chạy nền, theo lịch, qua `AIEmployee`/`Workflow`) làm ở task RIÊNG sau khi có `workers/*.py` + `domain/templates/*.py`.
2. **KHÔNG cần đăng nhập/JWT cho task này** — `api/deps.py` chỉ hiện thực `get_db()`/`get_llm()`/`get_storage()`, KHÔNG làm `get_current_user()`/`require_role()` (cần `models/user.py` + JWT, việc riêng). Endpoint `documents` tạm thời KHÔNG bảo vệ bằng auth — **CẢNH BÁO BẢO MẬT tạm thời, phải thêm auth trước khi deploy thật**, ghi rõ trong code bằng `# TODO SECURITY`.
3. **KHÔNG dùng `core/errors.py`** (cây `AppError` đầy đủ) — dùng thẳng `fastapi.HTTPException` trong router cho task này, đơn giản hoá. Nâng cấp lên `AppError` là việc sau.
4. **Chỉ mount router `documents` vào `api/v1/__init__.py`** — 7 router còn lại (auth, employees, workflows, runs, reviews, reports, tools, admin) vẫn là docstring stub, KHÔNG import (import sẽ lỗi vì chưa có `router = APIRouter()`).
5. **`utils/images.py`: CHỈ làm `exif_transpose` + resize theo cạnh dài** (`IMAGE_MAX_LONG_EDGE`, `IMAGE_MAX_PIXELS`) — **BỎ QUA `deskew()` (biến đổi Hough)** cho task này, để `deskew()` là hàm riêng trả nguyên ảnh không đổi kèm `# TODO: chưa hiện thực deskew Hough`. Lý do: deskew là thuật toán CV riêng biệt, không chặn việc thấy luồng chạy được hôm nay, làm sau nếu ảnh nghiêng thật gây sai kết quả.

Allowed files:
- `backend/app/schemas/invoice.py`
- `backend/app/utils/hashing.py`
- `backend/app/utils/images.py`
- `backend/app/services/document_service.py`
- `backend/app/services/qc_service.py`
- `backend/app/api/deps.py`
- `backend/app/api/v1/documents.py`
- `backend/app/api/v1/__init__.py`
- `backend/app/main.py`
- `backend/tests/unit/test_document_service.py` (mới)
- `backend/tests/unit/test_qc_service.py` (mới)
- `backend/tests/integration/test_documents_api.py` (mới — dùng FastAPI `TestClient`, LLM giả lập bằng fake `LLMProvider`, KHÔNG gọi mạng thật trong test)

Requirements:

### `schemas/invoice.py`
Pydantic v2, `model_config = ConfigDict(extra="forbid")` (giữ đúng phong cách `workflow_spec.py`):
```python
SCHEMA_VERSION = "invoice_v1"

class Party(BaseModel):
    name: str
    tax_code: str | None = None   # pattern 10 hoặc 13 số, validate ở service layer bằng domain/qc_rules QC-04, KHÔNG ràng buộc regex cứng ở đây (mã có thể chưa đủ 10 số lúc AI đọc nhầm — để QC-04 báo lỗi thay vì Pydantic chặn thẳng)
    address: str | None = None

class LineItem(BaseModel):
    line_no: int
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal

class Totals(BaseModel):
    subtotal: Decimal
    vat_rate: Decimal   # KHÔNG dùng Literal[0,5,8,10] cứng — để QC-03 (domain/qc_rules.py) báo lỗi khi AI đọc sai, Pydantic chỉ ép kiểu Decimal
    vat_amount: Decimal
    total: Decimal

class InvoiceExtraction(BaseModel):
    invoice_no: str
    invoice_form: str | None = None
    issue_date: date
    currency: str = "VND"
    seller: Party
    buyer: Party | None = None
    line_items: list[LineItem]
    totals: Totals
```
**NOTE bắt buộc ghi trong code:** `Totals.vat_rate`/`Party.tax_code` cố ý viết lỏng hơn mô tả gốc (bỏ `Literal[0,5,8,10]`, bỏ `pattern`) — vì `domain/qc_rules.py` (đã hiện thực, đã test) đã coi các sai lệch này là dữ liệu AI đọc SAI cần QC-03/QC-04 bắt lỗi và báo `needs_review`, không phải lỗi hệ thống cần chặn cứng ở tầng Pydantic (chặn cứng sẽ làm cả request lỗi 422 thay vì lưu lại kèm cảnh báo QC — sai mục tiêu "human-in-the-loop" của `AGENTS.md`). Cần Toàn xác nhận lại.
Thêm hàm `invoice_json_schema() -> dict` trả về `InvoiceExtraction.model_json_schema()` dùng làm tham số `schema=` khi gọi `llm.complete()`. **CẢNH BÁO ghi trong code:** JSON Schema sinh từ `Decimal` có thể không tương thích 100% với `guided_json` của vLLM (một số backend guided-decoding không hỗ trợ `anyOf`/`format` mà Pydantic sinh cho Decimal) — nếu khi Owner test thật gặp lỗi `LLMInvalidOutput`, đây là nghi phạm đầu tiên cần kiểm tra, KHÔNG tự đổi sang `float`.

### `utils/hashing.py`
```python
def sha256_bytes(data: bytes) -> str: ...
def sha256_stream(fileobj: BinaryIO, chunk_size: int = 65536) -> str: ...  # đọc theo khối 64KB, không load hết file vào RAM
```

### `utils/images.py`
```python
def preprocess(img: PIL.Image.Image) -> PIL.Image.Image:
    # thứ tự: ImageOps.exif_transpose -> deskew (no-op ở task này) -> resize theo
    # cạnh dài (settings.IMAGE_MAX_LONG_EDGE) với Image.LANCZOS, trần
    # settings.IMAGE_MAX_PIXELS -> convert("RGB")

def deskew(img: PIL.Image.Image) -> PIL.Image.Image:
    # TODO: chưa hiện thực biến đổi Hough — trả nguyên ảnh không đổi (no-op có
    # chủ đích, ghi rõ NOTE, KHÔNG được âm thầm bỏ qua yêu cầu gốc mà không ghi chú).
    return img
```

### `services/document_service.py`
```python
def ingest(
    db: Session, storage: FileStorage, llm: LLMProvider,
    file_bytes: bytes, filename: str, content_type: str | None,
) -> Document:
    """Luồng đầy đủ: lưu file (khử trùng) -> tạo Artifact+Document -> tiền xử
    lý ảnh -> gọi LLM trích xuất (schema=invoice_json_schema()) -> tạo
    Extraction -> gọi qc_service.evaluate() -> cập nhật Document.status -> trả
    về Document đã load đủ quan hệ (KHÔNG tự commit — caller ở api/v1/documents.py
    commit sau khi toàn bộ flow xong, để 1 lỗi giữa chừng rollback được cả).

    Nếu file KHÔNG phải image/pdf theo content_type: Document.status='rejected',
    KHÔNG gọi LLM.
    Nếu LLM ném LLMTimeout/LLMUnavailable/LLMInvalidOutput: bắt lại, tạo
    Document.status='failed', KHÔNG để lỗi văng ra ngoài làm crash request (trả
    Document với status failed, KHÔNG phải HTTP 500 — người dùng vẫn thấy chứng
    từ trong danh sách, biết là lỗi, thử lại sau khi Owner sửa LLM_API_KEY).
    """
```
Khử trùng: dùng `sha256_bytes()` trước, gọi `storage.exists(sha256)` — nếu đã tồn tại, KHÔNG tạo `Artifact` mới (dùng lại `Artifact` cũ theo `sha256`), vẫn tạo `Document` MỚI trỏ tới `artifact_id` đó (2 lần upload cùng file = 2 `Document` khác nhau, đúng theo `Document`/`Artifact` là quan hệ 1-nhiều đã thiết kế ở TASK-005b — KHÔNG chặn upload trùng ở tầng này, việc chặn trùng "sớm" là của endpoint `POST /documents/presign`).

### `services/qc_service.py`
```python
def evaluate(
    db: Session, extraction: Extraction,
) -> bool:  # trả về needs_review
    """Gọi domain/qc_rules.run_qc(data, existing_invoice_numbers) với `data` =
    chính đối tượng `extraction` (đã có đủ thuộc tính invoice_no/issue_date/...
    theo cấu trúc InvoiceExtraction nhờ denormalize ở TASK-005b — xem NOTE
    models/extraction.py) — KHÔNG cần dựng lại object từ extracted_data_json.
    existing_invoice_numbers: SELECT invoice_no FROM extractions WHERE
    invoice_no IS NOT NULL AND id != extraction.id (dùng cho QC-06).
    Ghi 1 dòng QCResult (models/extraction.py) cho MỖI kết quả trả về từ
    run_qc(), gắn extraction_id. KHÔNG tự commit.
    """
```
**Lưu ý khớp kiểu:** `extraction.issue_date` là `datetime.date` (cột `Date`), `qc_rules.py` dùng `_get(data, "issue_date")` rồi so sánh với `date`/`datetime` — đã tương thích, không cần convert. `extraction.seller_name`/`seller_tax_code` là 2 cột phẳng, nhưng `qc_rules.py` đọc qua path `"seller.name"`/`"seller.tax_code"` (object lồng nhau!) — **Extraction (ORM) KHÔNG có thuộc tính `seller` lồng nhau**, chỉ có `seller_name`/`seller_tax_code` phẳng. **PHẢI dựng 1 object/dict trung gian** khớp đúng cấu trúc `InvoiceExtraction` (`{seller: {name, tax_code}, totals: {subtotal, vat_rate, vat_amount, total}, invoice_no, issue_date}`) từ các cột phẳng của `Extraction` TRƯỚC khi gọi `run_qc()` — KHÔNG truyền thẳng đối tượng `Extraction` ORM vào `run_qc()` (sẽ đọc `seller.name` ra `None` sai, làm QC-04/QC-07 luôn fail giả). Đây là điểm dễ sai nhất của task này — Cline đọc kỹ `qc_rules.py` dòng 7-11 (docstring cấu trúc `data`) trước khi viết.

### `api/deps.py`
```python
def get_db() -> Generator[Session, None, None]: ...  # SessionLocal(), close() ở finally
def get_llm() -> LLMProvider: ...  # trả về instance OpenAICompatibleLLM (adapters/llm_openai_compatible.py) dựng từ settings
def get_storage() -> FileStorage: ...  # trả về LocalFileStorage (adapters/storage_local.py) dựng từ settings.STORAGE_PATH
```
KHÔNG viết `get_current_user()`/`require_role()` trong task này (xem Quyết định #2).

### `api/v1/documents.py`
- `POST /documents/presign` — body `{sha256: str}` → `{"exists": bool}` (gọi `storage.exists(sha256)`, KHÔNG đọc DB).
- `POST /documents` — multipart file, gọi `document_service.ingest()`, `db.commit()`, trả `DocumentDetail`-shape JSON (khớp `frontend/src/api/types.ts` `DocumentDetail`: id, filename, source_kind, status, invoice_no, issue_date, seller_name, total, qc_failed, created_at, file_url, schema_version, model_name, confidence, latency_ms, data, qc[]) — `data` dựng từ `extracted_data_json` (parse JSON), `qc` từ `qc_results` vừa tạo. Giới hạn dung lượng: từ chối > `settings.MAX_UPLOAD_MB` bằng `HTTPException(413, ...)` TRƯỚC khi đọc hết file vào RAM.
- `GET /documents` — query `status`/`from`/`to` (lọc theo `issue_date` của extraction mới nhất) + phân trang `limit`/`offset` — JOIN `Document` với `Extraction` mới nhất theo `document_id` (subquery `ORDER BY created_at DESC LIMIT 1`) để trả `invoice_no/issue_date/seller_name/total`; `qc_failed` = đếm `QCResult.passed=False` của extraction đó. Trả danh sách khớp `DocumentRow[]`.
- `GET /documents/{id}` — tương tự nhưng đủ trường `DocumentDetail` (extraction mới nhất + toàn bộ `qc_results` của nó). 404 nếu không có.
- `GET /documents/{id}/file` — `StreamingResponse` từ `storage.open(ArtifactRef(...))` dựng từ `Document.artifact` (sha256/path/size_bytes/content_type).
- **KHÔNG làm** `PATCH /documents/{id}/extraction` trong task này (để sau).

### `api/v1/__init__.py`
```python
from fastapi import APIRouter
from app.api.v1 import documents

api_router = APIRouter()
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
# 7 router còn lại (auth, employees, workflows, runs, reviews, reports, tools,
# admin) CHƯA include — vẫn là docstring stub, thêm dần khi hiện thực.
```

### `main.py`
- Thêm `from app.api.v1 import api_router` + `app.include_router(api_router, prefix="/api/v1")`.
- Thêm `CORSMiddleware` cho phép origin `http://localhost:5173` (Vite dev server) — **thêm setting mới `CORS_ORIGINS: list[str] = ["http://localhost:5173"]` vào `core/config.py`** (file NGOÀI Allowed files ở trên — nếu cần sửa, đây là ngoại lệ DUY NHẤT được phép, chỉ thêm 1 dòng field mới, không sửa field khác).
- KHÔNG thêm exception handler/static mount/scheduler startup (giữ nguyên "bản rút gọn có chủ đích" như comment đầu file hiện tại, cập nhật lại comment cho khớp trạng thái mới).

**Phạm vi bị CẮT khỏi task này (làm sau, KHÔNG tự làm thêm):**
- `domain/templates/*.py`, tạo/duyệt nhân viên AI, lập lịch, `agents/crew.py`, `workers/*.py` — luồng qua `job_queue`/chạy nền theo lịch.
- Đăng nhập/JWT/phân quyền cho toàn bộ API.
- `PATCH /documents/{id}/extraction` (sửa tay của con người).
- `core/errors.py` (cây lỗi có cấu trúc).
- `deskew()` ảnh nghiêng thật (Hough transform).
- Nối frontend (làm ở TASK-007 sau khi TASK-006 review xong).

Must pass:
- `cd backend && .venv/Scripts/pytest.exe -v` — toàn bộ pass, không giảm số test hiện có (73).
- `ruff check` + `mypy` trên toàn bộ file trong Allowed files → sạch.
- `tests/integration/test_documents_api.py` dùng FastAPI `TestClient` + fake `LLMProvider` (implement Protocol, trả `LLMResult` giả lập cố định) — test tối thiểu: (1) upload 1 ảnh giả → 200, `status` là `ok` hoặc `needs_review` tuỳ dữ liệu giả; (2) `GET /documents` trả đúng danh sách; (3) `GET /documents/{id}` trả đủ `qc[]`; (4) upload file không phải ảnh/pdf → `status=rejected`; (5) fake LLM ném `LLMUnavailable` → `status=failed`, response vẫn 200 (không phải 500).
- Chạy `make dev-api` (hoặc `uvicorn app.main:app`) thật, gọi `GET /health` vẫn PASS như cũ (không phá vỡ endpoint sẵn có).

Do not:
- Sửa `models/*.py` (TASK-005a/b đã DONE)
- Sửa `domain/*.py` (đã DONE, đã test)
- Làm thêm router nào khác ngoài `documents`
- Thêm auth/JWT (ngoài phạm vi, xem Quyết định #2)
- Đổi `schemas/workflow_spec.py`
- Thêm dependency mới (mọi thứ cần đã có trong `requirements.txt`: `fastapi`, `pydantic`, `Pillow`, `pypdfium2`)
- Tự ý làm `deskew()` thật hoặc `PATCH /documents/{id}/extraction` (đã cắt phạm vi, xem trên)

**Files affected (TASK-001):**
- `backend/app/domain/validators.py` (mới, hiện thực đầy đủ)
- `backend/tests/unit/test_validators.py` (mới, 17 test)
- `backend/pyproject.toml` (thêm `pythonpath = ["."]` — sửa hạ tầng test)

**Files affected (TASK-002):**
- `backend/app/domain/compiler.py` (mới, hiện thực đầy đủ — Cline viết bản đầu, Claude sửa 1 bug)
- `backend/tests/unit/test_compiler.py` (mới, 14 test)

**Files affected (TASK-003):**
- `backend/app/db/session.py` (sửa TRƯỚC khi giao Cline — Claude tự làm, hỗ trợ `BEGIN IMMEDIATE`)
- `backend/app/ports/queue.py` (hiện thực đầy đủ)
- `backend/app/adapters/queue_sqlite.py` (hiện thực đầy đủ)
- `backend/tests/unit/test_queue_sqlite.py` (mới, 10 test, có test đồng thời thật)

**Files affected (TASK-004):**
- `backend/app/ports/storage.py` (hiện thực đầy đủ)
- `backend/app/adapters/storage_local.py` (hiện thực đầy đủ)
- `backend/tests/unit/test_storage_local.py` (mới, 9 test)
- `.clinerules` (thêm mục 2.5 — bắt buộc dùng tool đọc file gốc, tránh vỡ encoding qua PowerShell)

**Files affected (TASK-005a):**
- `.gitignore` (sửa `models/` → `/models/` — bug hạ tầng, không liên quan Cline)
- `backend/app/db/session.py` (thêm `PRAGMA defer_foreign_keys=ON` — Claude tự sửa khi review)
- `backend/app/db/base.py` (thêm import 9 model mới)
- `backend/app/models/user.py`, `employee.py`, `workflow.py` (hiện thực đầy đủ, 9 bảng)
- `backend/tests/unit/test_models_group_a.py` (mới, 7 test)

**Task: TASK-007 — Nối trang Documents (frontend) vào API thật, thay mock**

**Status:** DONE (2026-08-29) — Claude Code tự làm trực tiếp (không qua Cline, việc nhỏ + đã hiểu rõ code sẵn có) + tự verify bằng cả TestClient lẫn trình duyệt thật (Browser pane, LM Studio thật).

Goal: bật `VITE_USE_MOCK=false` cho trang Chứng từ (Documents), để Owner xem được UI thật (không phải Swagger) đang gọi đúng backend TASK-006.

**Phát hiện quan trọng khi khảo sát trước khi code:** `frontend/src/api/client.ts` đã có sẵn công tắc `USE_MOCK` + `frontend/src/features/documents/UploadDrawer.tsx` đã tự tính sha256 client-side và để sẵn comment "Trong bản thật: gọi /documents/presign..." — kiến trúc frontend đã được thiết kế đúng ngay từ đầu để chuyển sang backend thật, chỉ cần nối dây, không cần viết lại.

**5 bug thật phát hiện + sửa (qua verify bằng trình duyệt thật, KHÔNG chỉ tin typecheck/test):**
1. Tiền tệ (`total`, `totals.subtotal/vat_rate/vat_amount/total`, `line_items[].quantity/unit_price/amount`) bị trả về dạng CHUỖI (Pydantic/FastAPI serialize `Decimal` thành `str` mặc định) trong khi `frontend/src/api/types.ts` khai báo `number` — sửa `documents.py` thêm hàm `_floatify()` đệ quy ép Decimal→float ở đúng biên API (không đụng Decimal nội bộ). Bắt được TRƯỚC khi chạm trình duyệt, qua đọc kỹ `types.ts` đối chiếu response thật.
2. **`uvicorn app.main:app` chạy qua công cụ preview có cwd khác `backend/`** → `.env` không tìm thấy (đường dẫn tương đối) → mọi setting rơi về mặc định (`LLM_API_KEY=""` → lỗi `Illegal header value`) — sửa `core/config.py` neo `env_file` theo đường dẫn TUYỆT ĐỐI từ vị trí chính file, không phụ thuộc cwd.
3. **`no such table: documents`** — app CHƯA BAO GIỜ tự tạo bảng khi khởi động (trước giờ chạy được chỉ vì đã có người tự gọi `create_all()` thủ công một lần trên `data/app.db` sẵn có, khi verify TASK-005b) — thêm `lifespan` (không dùng `on_event` đã deprecated) gọi `Base.metadata.create_all(engine)` lúc khởi động, có NOTE rõ đây là TẠM THỜI, không thay Alembic thật.
4. `InvoicePreview.tsx` **crash trắng trang** (`Cannot read properties of null (reading 'name')`) khi `data.buyer` là `null` — hoá đơn thật thường không có thông tin bên mua (mock luôn có sẵn nên chưa lộ). Sửa null-safe cho `buyer` và `seller.tax_code` (cũng có thể null khi AI đọc thiếu).
5. `file_url` trả về từ `storage.url_for(ref)` là `"/artifacts/{path}"` — route này **CHƯA BAO GIỜ được mount** ở `main.py` (không `StaticFiles`, không router khớp) → `<img>` vỡ. Sửa `documents.py` trả thẳng `f"/api/v1/documents/{document.id}/file"` (route thật đã có từ TASK-006). Đồng thời phát hiện `DocumentReviewPage.tsx` **chưa từng truyền `fileUrl` cho `<InvoicePreview>`** dù component đã có sẵn nhánh code xử lý — nối `fileUrl={doc.file_url}` (mock trả `file_url: ''` nên hành vi cũ ở chế độ mock không đổi).

**Việc khác đã làm:**
- `frontend/vite.config.ts`: đổi proxy target `8080` → `8123` (đúng cổng backend TASK-006).
- `frontend/.env` (mới, KHÔNG commit — đã gitignore): `VITE_USE_MOCK=false`.
- `documents.ts`: `uploadDocument` nhận `File` thật + `FormData` (trước đó chỉ nhận filename, mô phỏng mock); thêm `presignDocument`; `listDocuments` tự quy đổi `page/page_size` (kiểu frontend) → `limit/offset` (kiểu backend thật), bỏ qua `q` (backend chưa hỗ trợ tìm kiếm).
- `UploadDrawer.tsx`: nối presign thật trước khi upload (đúng comment để sẵn), dùng `uploadDocument(file)` mới.
- `client.ts`: `/auth/*` CỐ Ý vẫn đi qua mock dù `USE_MOCK=false` — backend thật chưa có auth (quyết định TASK-006), nếu không có bước này người dùng bị kẹt ở màn đăng nhập, không vào xem được tính năng thật. Ghi rõ "XOÁ ngay khi có JWT thật".
- `.claude/launch.json` (OS Brain, ngoài repo): thêm config `sme-backend` (cmd.exe wrapper `cd /d <backend> && uvicorn ...` — bắt buộc để cwd đúng, xem bug #2).

**Evidence — verify bằng trình duyệt thật (Browser pane), KHÔNG chỉ TestClient:**
- Đăng nhập (qua mock tạm thời) → vào `/documents` → gọi API thật, danh sách rỗng đúng (DB mới, không lỗi).
- Upload 1 ảnh hoá đơn thật (tự tạo, có bảng chi tiết dòng hàng) qua UI thật (giả lập chọn file bằng DataTransfer vì Browser pane không có tool upload file) → **LM Studio thật (Bionic, model qwen/qwen3-vl-8b) đọc đúng**: số hoá đơn "0005678", tổng tiền "3.300.000" khớp chính xác ảnh gốc, độ trễ 11.0 giây.
- Mở trang chi tiết → ảnh gốc hiển thị đúng (không vỡ), cảnh báo QC-05 (AI đọc nhầm năm 2026→2008) hiển thị đúng ngay trên form — chứng minh cả luồng UI xem/đối chiếu hoạt động, không chỉ API.
- Test dedup: upload lại đúng bytes cũ → đúng hiện "Đã có" (presign chặn, không tạo document mới) — khớp thiết kế SPEC.md "chống trùng sớm".
- Dọn sạch dữ liệu test (documents/extractions/qc_results/artifacts) khỏi `data/app.db` sau khi verify xong.

**Evidence — pytest/ruff/mypy (backend):** `94 passed` (không đổi số lượng, thêm 2 assertion khoá bug #1 và #5 vào `test_api_documents.py`); `ruff check` sạch; `mypy` sạch (trừ 1 lỗi debt cũ `qc_rules.py` không đổi).

**Evidence — frontend:** `npm run typecheck` sạch sau mọi thay đổi.

**Bug #6 (phát hiện SAU khi báo DONE, do Toàn hỏi "mấy cái khác thì chưa nối backend hả"):** `VITE_USE_MOCK=false` là công tắc TOÀN CỤC — bật lên khiến CẢ APP (Dashboard, Employees, Runs, Reports...) đều cố gọi backend thật, nhưng backend chỉ có router `documents`. Xác nhận thật bằng Browser pane: mở `/` (Dashboard) sau khi bật cờ → lỗi "Hệ thống gặp sự cố không xác định" (500, backend không có route đó). Sửa `client.ts`: đổi từ `MOCK_ONLY_PATHS` (danh sách CẤM dùng thật, chỉ có `/auth/`) sang `REAL_BACKEND_PATHS` (danh sách CHO PHÉP dùng thật, chỉ có `/documents`) — an toàn hơn về hướng mặc định (thêm router mới vào danh sách khi hiện thực xong, thay vì phải nhớ trừ ra). Verify lại bằng Browser pane: `/` và `/runs` chạy mock bình thường trở lại, `/documents` vẫn gọi đúng backend thật (0 bản ghi vì DB đã dọn sạch).

**Giả định/quyết định cần Toàn xác nhận:** (1) auth tạm thời qua mock cho tới khi có JWT thật; (2) `q` (tìm kiếm) chưa lọc được ở backend, chỉ bị bỏ qua im lặng — cần làm full-text search sau nếu Owner cần gấp.

**Chưa làm (ngoài phạm vi, để sau):** `PATCH /documents/{id}/extraction` (nút "Xác nhận và lưu" trên UI hiện sẽ lỗi 404 nếu bấm — CHƯA test kỹ luồng này, cần Owner biết trước khi demo).
