# PROJECT.md

> Sự thật ổn định của project — KHÔNG đặt trạng thái task hay quy trình làm việc ở đây (xem `IMPLEMENTATION_PLAN.md`).
>
> **DRAFT 2026-08-28** — soạn từ `docs/`, `README.md`, source code stub và context OS Brain (`02 - Projects/sme-ai-workforce/`). Cần Toàn duyệt lại, đặc biệt các mục đánh dấu "(giả định)".

## Project dùng để làm gì

Nền tảng tạo và vận hành "nhân viên AI" cho doanh nghiệp nhỏ và vừa (SME). Người dùng mô tả công việc bằng tiếng Việt tự nhiên → hệ thống biên dịch thành một quy trình (workflow) xử lý chứng từ, chạy tự động theo lịch, có tầng kiểm soát chất lượng (QC) tự động và bước xác nhận thủ công khi hệ thống nghi ngờ kết quả.

Đồ án tốt nghiệp, không phải sản phẩm thương mại đã vận hành — nhưng mục tiêu là có khả năng dùng thật cho SME, không chỉ demo bảo vệ.

## Người dùng là ai

Nhân viên kế toán/vận hành ở SME Việt Nam — khối lượng chứng từ đều đặn (khoảng 300–500 chứng từ/tháng), **không có đội IT riêng** để vận hành hạ tầng phức tạp.

## Vấn đề cần giải quyết

- Xử lý thủ công một khối lượng chứng từ lặp lại (đọc hoá đơn, đối chiếu bảng tính, tổng hợp báo cáo) tốn thời gian và dễ sai sót.
- SME muốn tự động hoá nhưng không đủ nguồn lực để cài đặt/vận hành hệ thống nhiều thành phần (Redis, Celery, GPU cluster...) — mọi thành phần thêm vào là một thứ có thể hỏng mà không ai sửa được (lý do ADR-001).
- Dữ liệu chứng từ (hoá đơn, kế toán) nhạy cảm — cần chạy được **100% offline** trên máy chủ nội bộ, không phụ thuộc dịch vụ AI bên thứ ba khi dùng dữ liệu thật (xem `SECURITY.md`).

## Phạm vi

**4 module chính** (theo `README.md` / OS Brain PROJECT.md):
1. Đọc chứng từ (trích xuất hoá đơn từ ảnh/PDF qua Qwen3-VL).
2. Xử lý bảng tính (làm sạch, đối chiếu Excel).
3. Biên dịch quy trình tiếng Việt — mô tả công việc bằng tiếng Việt → phân loại vào **tập mẫu có sẵn** (`domain/templates/`) rồi điền tham số qua lời gọi có ràng buộc schema (ADR-002, **không** phải agent tự lập kế hoạch tự do).
4. Lập lịch / chạy nền (APScheduler + hàng đợi bảng SQLite `job_queue`, ADR-001).

**Tầng kiểm soát chất lượng:** 8 quy tắc tất định (`domain/qc_rules.py`, đã hiện thực) — QC-01 khớp tổng dòng với subtotal, QC-02 subtotal+VAT=total, QC-03 thuế suất hợp lệ, QC-04 checksum mã số thuế, QC-05 ngày lập hợp lý, QC-06 số hoá đơn không trùng, QC-07 trường bắt buộc đầy đủ, QC-08 thành tiền dòng khớp số lượng×đơn giá.

**Xác nhận thủ công:** không có màn hình riêng — dùng chung danh sách chứng từ, lọc `status=needs_review` (ADR-003).

**Báo cáo:** tổng hợp theo kỳ, xuất Excel/PDF.

**Quản trị:** người dùng/phân quyền cơ bản, cấu hình LLM, xem chỉ số vận hành.

## Ngoài phạm vi

- Agent tự chủ suy luận kế hoạch nhiều bước (ADR-002) — chỉ dùng CrewAI ở chế độ `Process.sequential`, phạm vi tool giới hạn theo từng tác tử.
- Hàng đợi phân tán/scale ngang (Redis + Celery) ở bản triển khai nội bộ — chỉ dành cho kịch bản "web công khai" sau này, chuyển qua cùng giao diện `JobQueue` (ADR-001).
- Xoá dữ liệu thật: nhân viên AI (`ai_employees`) chỉ archived, không xoá (`DELETE /employees/{id}` chỉ đánh dấu archived — theo docstring `api/v1/employees.py`).
- Màn hình "hàng đợi chờ xác nhận" tách riêng (ADR-003).

## Công nghệ chính

| Lớp | Công nghệ |
|---|---|
| Backend | Python 3.11+, FastAPI 0.115, SQLAlchemy 2.0 + Alembic, Pydantic 2.9, SQLite (WAL mode) |
| AI Engine | Qwen3-VL 8B Instruct (quantized 4-bit) qua vLLM endpoint (OpenAI-compatible), gọi qua `httpx` |
| Agent | CrewAI 0.80 — chỉ chế độ tuần tự (ADR-002) |
| Bảo mật | argon2-cffi (hash mật khẩu), PyJWT (token) |
| Xử lý tài liệu | Pillow, pypdfium2, opencv-python-headless, numpy |
| Bảng tính/báo cáo | pandas, openpyxl, ReportLab |
| Lập lịch / Log | APScheduler, structlog |
| Frontend | React 18 + Vite + TypeScript, TailwindCSS, TanStack Query, react-router-dom |
| DevOps | Docker, Docker Compose, nginx (reverse proxy) |

**Kiến trúc:** Ports & Adapters — 4 cổng trừu tượng (`LLMProvider`, `Repository`, `FileStorage`, `JobQueue`); lõi nghiệp vụ (`domain/`, `services/`, `tools/`) không đổi giữa môi trường nội bộ (offline) và môi trường web công khai (sau này), chỉ đổi adapter. Chi tiết xem `ARCHITECTURE.md`.
