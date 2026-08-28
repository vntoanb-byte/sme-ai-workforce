# ARCHITECTURE.md

> Kiến trúc hiện tại — không phải kiến trúc mong muốn. Cập nhật khi kiến trúc thật đổi, không cập nhật trước.
>
> **DRAFT 2026-08-28** — soạn từ `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, docstring các file trong `backend/app/`, và context OS Brain. Trạng thái "đã hiện thực" vs "còn stub" ghi rõ theo từng phần — không suy đoán.

## Cấu trúc thư mục

```
backend/
  app/api/        tầng HTTP (FastAPI routers) — CÒN STUB (trừ main.py rút gọn chỉ có GET /health)
  app/services/   điều phối use-case — CÒN STUB
  app/domain/     nghiệp vụ thuần — biên dịch, kiểm chứng, quy tắc QC, state machine
  app/ports/      4 giao diện trừu tượng (LLMProvider, Repository, FileStorage, JobQueue)
  app/adapters/   hiện thực cụ thể 4 cổng
  app/tools/      danh mục công cụ cho tác tử — CÒN STUB
  app/agents/     CrewAI crew (Process.sequential) — CÒN STUB
  app/workers/    tiến trình nền + bộ lập lịch (APScheduler) — CÒN STUB
  app/models/     SQLAlchemy models — CÒN STUB
  app/schemas/    Pydantic schemas
  app/core/       config, security, logging, errors
  app/db/         base, session, init_db
  app/utils/      dates, hashing, images, money
frontend/         React 18 + Vite + TypeScript + Tailwind — ĐÃ DỰNG UI ĐẦY ĐỦ (~4400 dòng), chạy trên mock API
deploy/           Docker Compose, nginx, gói cài đặt ngoại tuyến
eval/             bộ dữ liệu đánh giá và script chấm điểm
docs/             ARCHITECTURE.md, DECISIONS.md (3 ADR), SCREENS.md
```

## Module

| Module | Trạng thái | Ghi chú |
|---|---|---|
| `core/config.py` | ✅ Xong | `Settings` đầy đủ theo `.env.example` |
| `db/base.py`, `db/session.py` | ✅ Xong | 4 PRAGMA SQLite; tự tạo thư mục `./data/` trước khi mở engine |
| `ports/llm.py` | ✅ Xong | `LLMProvider` Protocol, `LLMResult`, 3 exception |
| `adapters/llm_openai_compatible.py` | ✅ Xong (chưa đủ 100%) | Circuit breaker (mở sau 5 lỗi liên tiếp, đóng thử lại 60s), ghép ảnh base64, guided JSON. **Thiếu:** ghi 1 dòng vào `llm_calls` cho mỗi lời gọi (bảng `llm_calls` nay đã xác nhận thuộc `models/audit.py` — xem Database bên dưới) |
| `domain/qc_rules.py` | ✅ Xong | 8 quy tắc QC-01→QC-08, dùng `Decimal`, đối chiếu khớp mock data |
| `domain/state.py` | ✅ Xong | `RunLike` là Protocol, chưa nối `models/run.py` thật (TODO trong code) |
| `schemas/workflow_spec.py` | ✅ Xong | Có 4 giả định cần Toàn xác nhận lại (xem `memory.md`) |
| `domain/validators.py` | ⬜ Chưa làm | |
| `domain/compiler.py` | ⬜ Chưa làm | Output là `WorkflowSpec`; cần `adapters/llm_openai_compatible.py` để chạy thật |
| `domain/templates/*.py` | ⬜ Chưa làm | 5 file mẫu + `registry.py` |
| `adapters/queue_sqlite.py` | ⬜ Chưa làm | **File quan trọng nhất backend** (tự nhận trong docstring) — giao thức `BEGIN IMMEDIATE` + kiểm `rowcount` (ADR-001) |
| `adapters/storage_local.py` | ⬜ Chưa làm | |
| `models/*.py` (7 file) | ⬜ Chưa làm | Toàn bộ chỉ có docstring mô tả bảng |
| `services/*.py` (7 file) | ⬜ Chưa làm | |
| `api/v1/*.py` (8 router + admin) | ⬜ Chưa làm | `main.py` hiện tại **chưa mount** router v1 (bản rút gọn chỉ có `/health`) |
| `tools/*.py` (6 file) | ⬜ Chưa làm | |
| `agents/crew.py` | ⬜ Chưa làm | |
| `workers/*.py` (3 file) | ⬜ Chưa làm | |
| `frontend/` | ✅ UI xong, API mock | Chưa nối API thật |

## Dependency

Hướng phụ thuộc bắt buộc (quy tắc kiến trúc — không được vi phạm, xem `AGENTS.md` Mục 4):

```
api/ → services/ → domain/
                 → adapters/ → ports/
workers/ → services/
domain/  ✕ KHÔNG được import api/, adapters/, workers/
```

Chỉ `core/config.py` đọc biến môi trường (`os.environ`) — mọi nơi khác import `settings` đã dựng sẵn.

## Data flow

1. Upload chứng từ → `api/v1/documents.py` → `services/document_service.py` → lưu file qua `ports/storage` (adapter: `adapters/storage_local.py`) + tạo bản ghi `artifacts`/`documents`.
2. Trích xuất → gọi `ports/llm` (adapter: `adapters/llm_openai_compatible.py`, Qwen3-VL qua vLLM OpenAI-compatible endpoint) → ghi `extractions`.
3. QC → `domain/qc_rules.py` chạy 8 quy tắc tất định (không qua LLM) → ghi `qc_results`; nếu có cảnh báo/nghiêm trọng → `status=needs_review`.
4. Xác nhận thủ công → `api/v1/reviews.py` → `services/review_service.py` → ghi `human_reviews`, cập nhật trạng thái qua `domain/state.py`.
5. Chạy nền theo lịch → `workers/scheduler.py` (APScheduler) đăng việc vào bảng `job_queue` (cùng transaction với `runs`, ADR-001) → `workers/worker.py` giành việc bằng `BEGIN IMMEDIATE` + kiểm `rowcount` → `agents/crew.py` (CrewAI sequential) thực thi từng bước theo `WorkflowSpec`.
6. Biên dịch quy trình → `services/compiler_service.py` → `domain/compiler.py` gọi LLM có ràng buộc schema, phân loại vào 1 trong 5 mẫu (`domain/templates/`) → trả `WorkflowSpec`.

## Database

SQLite (WAL mode). 4 nhóm bảng theo `models/*.py` (hiện chỉ là docstring, chưa có class thật):

| File model | Bảng |
|---|---|
| `models/user.py` | `users`, `roles`, `user_roles` |
| `models/employee.py` | `ai_employees`, `schedules` |
| `models/workflow.py` | `workflows`, `workflow_steps`, `workflow_edges`, `tools` |
| `models/run.py` | `runs`, `run_steps`, `run_logs`, `job_queue` |
| `models/extraction.py` | `extractions`, `qc_results`, `human_reviews` |
| `models/artifact.py` | `artifacts`, `documents` |
| `models/audit.py` | `audit_logs`, `llm_calls`, `settings` |

DDL đầy đủ nằm ở "Phụ lục A" tài liệu thiết kế (.docx, ngoài repo — chưa đọc trực tiếp, không suy đoán chi tiết cột). Quy tắc bắt buộc khi hiện thực: mọi FK có `ondelete` rõ ràng, cột JSON dùng `Text` (đọc/ghi qua `json.dumps/loads` ở tầng service), `Index`/`UniqueConstraint` trong `__table_args__`, relationship 2 chiều `back_populates`. Không sửa lược đồ tại chỗ — tăng `SCHEMA_VERSION` + migration Alembic mới.

## API

Base: FastAPI, router `v1` (chưa mount vào `main.py` — hiện tại chỉ có `GET /health`). Theo docstring từng file (chưa hiện thực):

| Router | Endpoint chính |
|---|---|
| `auth.py` | `POST /login`, `POST /refresh`, `POST /logout`, `GET /me` |
| `employees.py` | `GET/POST /employees`, `GET/PATCH/DELETE /employees/{id}` (DELETE chỉ archived) |
| `workflows.py` | `GET/PUT /workflows/{id}`, `POST /workflows/{id}/approve`, `POST /workflows/{id}/validate` |
| `documents.py` | `POST /documents/presign`, `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/file` |
| `runs.py` | `POST /runs`, `GET /runs`, `GET /runs/{id}`, `GET /runs/{id}/logs` (SSE), `POST /runs/{id}/cancel` |
| `reviews.py` | `GET /reviews`, `POST /reviews/{id}/resolve`, `GET /reviews/stats` |
| `reports.py` | `POST /reports/preview`, `POST /reports/export`, `GET /reports/{artifact_id}/download` |
| `tools.py` | `GET /tools` |
| `admin.py` | `GET/POST/PATCH /admin/users`, `GET/PUT /admin/settings`, `GET /admin/metrics`, `POST /admin/llm/test` |

`GET /health` (đã hiện thực, đã test thật 2026-08-27) — check database + storage + `GET {LLM_BASE_URL}/models`.

## Ranh giới module (không được tuỳ tiện vượt qua)

1. `domain/` không import `api/`, `adapters/`, `workers/`.
2. Chỉ `core/config.py` đọc biến môi trường.
3. Đổi trạng thái phải qua `domain/state.py`, không gán cột DB trực tiếp.
4. Frontend không chứa logic nghiệp vụ — mọi tính toán do backend làm.
5. `qc_rules.py` nhận `data` kiểu duck-typed (dict hoặc object), không import cứng `schemas/invoice.py` — quyết định có chủ đích vì file đó còn stub tại thời điểm hiện thực (xem `log.md`).

## Những phần không được tuỳ tiện thay đổi

- **ADR-001** (hàng đợi bảng SQLite thay Redis) — không tự đổi sang Celery/Redis khi chưa có yêu cầu chuyển sang triển khai web công khai.
- **ADR-002** (CrewAI chỉ `Process.sequential`, không tự suy luận kế hoạch) — không tự thêm vòng lặp agent tự chủ.
- **ADR-003** (không tách màn hình "hàng đợi chờ xác nhận" riêng) — dùng chung danh sách chứng từ + filter.
- 5 mã `TemplateCode` trong `schemas/workflow_spec.py` hiện suy từ tên file — **phải đối chiếu lại** khi `domain/templates/registry.py` được hiện thực, không tự sửa `workflow_spec.py` trước.
- Tiền tệ luôn `Decimal`, không bao giờ `float`.
