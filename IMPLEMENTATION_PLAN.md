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

**Next:**
- TASK-002: `domain/compiler.py` (output là `WorkflowSpec`; cần `adapters/llm_openai_compatible.py` — đã có bản đầu — để chạy thật)
- TASK-003: `adapters/queue_sqlite.py` (file quan trọng nhất backend — đọc `docs/DECISIONS.md` ADR-001 trước khi làm)
- TASK-004: `adapters/storage_local.py`
- Sau đó: `models/*` (đang là docstring stub, cần trước khi `services/*`/`api/v1/*` chạy thật được) → `services/*` → `api/v1/*` → `tools/*` → `agents/crew.py` (đọc ADR-002 trước) → `workers/*`
- Cuối cùng: nối frontend vào API thật

**Blocker:**
- Không còn (Cline/VS Code đã gỡ — không còn phụ thuộc phối hợp 2 tool).

**Files affected (TASK-001):**
- `backend/app/domain/validators.py` (mới, hiện thực đầy đủ)
- `backend/tests/unit/test_validators.py` (mới, 17 test)
- `backend/pyproject.toml` (thêm `pythonpath = ["."]` — sửa hạ tầng test)
