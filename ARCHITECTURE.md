# ARCHITECTURE.md

> Kiến trúc hiện tại — không phải kiến trúc mong muốn. Cập nhật khi kiến trúc thật đổi, không cập nhật trước.
>
> **Cập nhật 2026-09-24 (TASK-008)** — toàn bộ module đã hiện thực, kiểm thử tự động (268+ ca) và kiểm thử end-to-end trên trình duyệt. Quyết định mới: ADR-004..008 trong `docs/DECISIONS.md`.

## Cấu trúc thư mục

```
backend/
  app/api/        tầng HTTP — 9 router /api/v1 + GET /health, xác thực JWT ở api/deps.py
  app/services/   điều phối use-case (auth, employee, workflow, compiler, run, execution,
                  review, report, metrics, settings, document, qc)
  app/domain/     nghiệp vụ thuần — compiler, validators V-1..V-5, qc_rules, state, templates/
  app/ports/      4 giao diện trừu tượng (LLMProvider, Repository, FileStorage, JobQueue)
  app/adapters/   hiện thực cụ thể: llm_openai_compatible, storage_local, queue_sqlite
  app/tools/      14 công cụ (fs, doc, vision, qc, xlsx, report) + registry + đồng bộ bảng tools
  app/agents/     crew tuần tự 3 tác tử, giới hạn phạm vi công cụ
  app/workers/    worker (heartbeat, SIGTERM), scheduler (cron, file_watch), reaper
  app/models/     SQLAlchemy — 22 bảng / 7 file
  app/schemas/    Pydantic (WorkflowSpec, InvoiceExtraction, DTO API)
  app/core/       config, security (argon2/JWT/Fernet), logging (structlog), errors
  app/db/         base, session (PRAGMA SQLite), init_db (Alembic + seed)
  alembic/        env.py + versions 0001 (21 bảng) → 0002 (refresh_tokens)
frontend/         React 18 + Vite + TypeScript + Tailwind — nối backend thật
deploy/           Docker Compose (vllm + app + worker [+ nginx]), nginx, gói ngoại tuyến
eval/             score.py (chấm điểm), dataset/ + ground_truth/ sinh bằng scripts
docs/             ARCHITECTURE.md, DECISIONS.md (ADR-001..008), SCREENS.md
```

## Module

| Module | Trạng thái | Ghi chú |
|---|---|---|
| `core/*` | ✅ | config (thêm COOKIE_SECURE, STATIC_DIR, REPORT_FONT_PATH, FS_ALLOWED_ROOTS), errors thống nhất `{error:{code,message,details,trace_id}}`, logging JSON + trace_id, security |
| `db/*` + Alembic | ✅ | API tự `alembic upgrade head` khi khởi động; DB cũ tạo bằng create_all được `stamp` đúng phiên bản |
| `domain/*` | ✅ | compiler dùng danh mục mẫu (few-shot) + bộ khung mẫu trong prompt (PROMPT_VERSION v2) |
| `domain/templates/*` | ✅ | 5 mẫu khớp đúng 5 mã `TemplateCode` (đã đối chiếu) |
| `adapters/*` | ✅ | queue thêm `extend_lease`, `fail(retry=False)`, reap hết lượt → failed |
| `models/*` | ✅ | thêm `RefreshToken` (migration 0002) |
| `services/*` | ✅ | ghi `llm_calls` cho mọi lời gọi mô hình |
| `tools/*` | ✅ | chỉ đọc tệp dưới WATCH_PATH/FS_ALLOWED_ROOTS; không bao giờ ghi đè tệp gốc |
| `agents/crew.py` | ✅ | Python thuần, không dùng thư viện CrewAI (ADR-004) |
| `workers/*` | ✅ | lịch đọc lại từ bảng schedules mỗi phút (ADR-007) |
| `api/v1/*` | ✅ | 38 điểm cuối, OpenAPI tại /api/v1/openapi.json |
| `frontend/` | ✅ | nối backend thật; `npm run dev` mặc định dữ liệu giả, bản build luôn gọi backend |

## Dependency

Hướng phụ thuộc bắt buộc (quy tắc kiến trúc — không được vi phạm, xem `AGENTS.md` Mục 4):

```
api/ → services/ → domain/ → (ports/, schemas/)
                 → ports/
services/execution_service → agents/ → tools/ → services/{document,qc,report}
workers/ → services/
api/deps.py, workers/worker.py = "composition root": nơi DUY NHẤT dựng adapters/ cụ thể
domain/  ✕ KHÔNG được import api/, adapters/, workers/ (kiểm bằng grep: chỉ import
         app.domain, app.ports, app.schemas)
```

Chỉ `core/config.py` đọc biến môi trường (`os.environ`) — mọi nơi khác import `settings` đã dựng sẵn.

## Data flow

1. Đăng nhập → `api/v1/auth.py` → access token (bộ nhớ trình duyệt) + refresh token cookie HttpOnly xoay vòng (ADR-005).
2. Tạo nhân viên AI → `services/compiler_service.py` → `domain/compiler.py` (phân loại vào 1 trong 5 mẫu + điền tham số có ràng buộc schema + V-1..V-5) → lưu phiên bản quy trình `pending` → duyệt (`workflow_service.approve`) → nhân viên `active`, bật lịch.
3. Kích hoạt (thủ công `POST /runs`, cron, hoặc có tệp mới trong thư mục theo dõi) → `run_service.create_run` ghi `runs` + `job_queue` CÙNG transaction (ADR-001).
4. `workers/worker.py` giành việc (`BEGIN IMMEDIATE` + `rowcount`), heartbeat gia hạn lease → `execution_service.execute` → `agents/crew.py` chạy tuần tự: `fs.list_new_files` → `vision.extract_invoice` (khử trùng sha256) → `qc.validate_invoice` → nhánh đạt (`xlsx.append_rows`/`report.*`) | nhánh không đạt (`qc.escalate`).
5. Có chứng từ không đạt → run `NEEDS_REVIEW`; người duyệt xử lý (`/reviews/{id}/resolve` hoặc `PATCH /documents/{id}`) → ghi `human_reviews` + `audit_logs` (trước/sau) → chứng từ cuối cùng xong thì run tự quay lại hàng đợi chạy tiếp nhánh đạt (ADR-006).
6. Tải lên trực tiếp (`POST /documents`) → trích xuất + QC đồng bộ.
7. Nhật ký: mỗi dòng `run_logs` commit ngay; `GET /runs/{id}/logs` (SSE) đọc bảng này nên chạy đúng khi worker là tiến trình khác.
8. Báo cáo: `report_service.aggregate` (SQL GROUP BY trên extraction mới nhất của chứng từ đã xác nhận) → Excel (openpyxl) / PDF (ReportLab, phông tiếng Việt).

## Database

SQLite (WAL mode), 22 bảng / 7 file model, quản lý bằng Alembic (`alembic/versions/0001`, `0002`):

| File model | Bảng |
|---|---|
| `models/user.py` | `users`, `roles`, `user_roles`, `refresh_tokens` |
| `models/employee.py` | `ai_employees`, `schedules` (trigger của từng phiên bản quy trình — ADR-007) |
| `models/workflow.py` | `workflows`, `workflow_steps`, `workflow_edges`, `tools` |
| `models/run.py` | `runs`, `run_steps`, `run_logs`, `job_queue` |
| `models/extraction.py` | `extractions`, `qc_results`, `human_reviews` |
| `models/artifact.py` | `artifacts`, `documents` |
| `models/audit.py` | `audit_logs` (kể cả mô tả gốc khi biên dịch, tệp đầu ra của lần chạy), `llm_calls`, `settings` |

Quy tắc: mọi FK có `ondelete` rõ ràng, cột JSON dùng `Text`, không sửa lược đồ tại chỗ — migration mới.

## API

Base `/api/v1`, tài liệu tương tác `/api/v1/docs`. Vai trò: USER (mọi người dùng), MANAGER, ADMIN.

| Router | Endpoint | Quyền ghi |
|---|---|---|
| `auth.py` | `POST /login`, `POST /refresh`, `POST /logout`, `GET /me` | — |
| `employees.py` | `GET/POST /employees`, `GET/PATCH/DELETE /employees/{id}` (DELETE chỉ archived) | MANAGER |
| `workflows.py` | `GET/PUT /workflows/{id}`, `POST /workflows/{id}/approve`, `POST /workflows/{id}/validate` | MANAGER |
| `documents.py` | `POST /documents/presign`, `POST /documents`, `GET /documents` (status, from/to, q), `GET/PATCH /documents/{id}`, `GET /documents/{id}/file` | USER |
| `runs.py` | `POST /runs`, `GET /runs`, `GET /runs/{id}`, `GET /runs/{id}/logs` (SSE), `POST /runs/{id}/cancel` | MANAGER |
| `reviews.py` | `GET /reviews`, `POST /reviews/{id}/resolve`, `GET /reviews/stats` | USER |
| `reports.py` | `POST /reports/preview`, `POST /reports/export`, `GET /reports/{artifact_id}/download` | USER |
| `tools.py` | `GET /tools` | — |
| `admin.py` | `GET/POST/PATCH /admin/users`, `GET/PUT /admin/settings`, `GET /admin/metrics` (mọi người dùng xem), `POST /admin/llm/test` | ADMIN |

`GET /health` — kiểm tra database + storage + `GET {LLM_BASE_URL}/models`.

## Ranh giới module (không được tuỳ tiện vượt qua)

1. `domain/` không import `api/`, `adapters/`, `workers/`.
2. Chỉ `core/config.py` đọc biến môi trường.
3. Đổi trạng thái phải qua `domain/state.py`, không gán cột DB trực tiếp.
4. Frontend không chứa logic nghiệp vụ — mọi tính toán do backend làm.
5. `qc_rules.py` nhận `data` kiểu duck-typed (dict hoặc object), không import cứng `schemas/invoice.py`.
6. Bộ lập lịch chỉ chạy trong tiến trình worker (không chạy trong uvicorn — tránh kích hoạt trùng khi nhiều tiến trình API).

## Những phần không được tuỳ tiện thay đổi

- **ADR-001** (hàng đợi bảng SQLite thay Redis) — không tự đổi sang Celery/Redis khi chưa có yêu cầu chuyển sang triển khai web công khai.
- **ADR-002** (CrewAI chỉ `Process.sequential`, không tự suy luận kế hoạch) — không tự thêm vòng lặp agent tự chủ.
- **ADR-003** (không tách màn hình "hàng đợi chờ xác nhận" riêng) — dùng chung danh sách chứng từ + filter.
- 5 mã `TemplateCode` trong `schemas/workflow_spec.py` — đã đối chiếu khớp 5 mẫu thật trong `domain/templates/` (có test khoá lại).
- Tiền tệ luôn `Decimal`, không bao giờ `float`.
