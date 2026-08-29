# IMPLEMENTATION_PLAN.md — Trạng thái hiện tại của project

> Claude PHẢI đọc file này trước khi tiếp tục 1 project đang làm dở — không tự bịa lại kế hoạch từ đầu nếu đã có plan.

> **2026-08-28:** Owner đã gỡ VS Code/Cline khỏi máy. Từ đây Claude Code trực tiếp làm cả Architect **và** Implementer (không còn phối hợp qua khối "giao task cho Cline" nữa) — nhưng vẫn giữ nguyên kỷ luật tự review bằng bằng chứng thật (`scripts/verify`, Claim Gate) thay vì tự tuyên bố xong.

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
