# SME AI Workforce

Nền tảng tạo và vận hành nhân viên AI cho doanh nghiệp nhỏ và vừa.
Người dùng mô tả công việc bằng tiếng Việt, hệ thống dựng thành quy trình xử lý chứng từ
chạy tự động theo lịch, có kiểm tra kết quả (8 quy tắc QC) và có người xác nhận khi nghi ngờ.

## Bắt đầu nhanh (phát triển)

```bash
make setup                 # tạo backend/.venv, cài phụ thuộc, npm ci, tạo backend/.env
# sửa backend/.env: LLM_BASE_URL/LLM_MODEL/LLM_API_KEY, JWT_SECRET, FIRST_ADMIN_PASSWORD
make migrate               # alembic upgrade head (API cũng tự chạy khi khởi động)
make seed                  # (tuỳ chọn) dữ liệu trình diễn: ketoan/quanly/admin, mật khẩu Demo@12345
make dev-api               # cửa sổ 1 — backend http://localhost:8080 (tài liệu API: /api/v1/docs)
make worker                # cửa sổ 2 — tiến trình xử lý nền + bộ lập lịch
VITE_USE_MOCK=false make dev-web   # cửa sổ 3 — giao diện http://localhost:5173 gọi backend thật
```

`npm run dev` không đặt `VITE_USE_MOCK` sẽ chạy bằng **dữ liệu giả** (phát triển giao diện
không cần backend). Bản build (`npm run build`, ảnh Docker) luôn gọi backend thật.

## Triển khai nội bộ (offline, Docker)

```bash
cp backend/.env.example backend/.env      # điền JWT_SECRET, CREDENTIAL_ENC_KEY, FIRST_ADMIN_PASSWORD
cd deploy && docker compose up -d         # vllm + app (API + giao diện) + worker
# HTTPS: đặt chứng chỉ vào deploy/certs rồi `docker compose --profile https up -d`
```

Dữ liệu (SQLite, kho tệp) nằm trong volume `app-data` (`/data`). Thư mục hồ sơ quét gắn
CHỈ ĐỌC vào `/mnt/scan` (biến `SCAN_DIR`). Đóng gói cho máy không có Internet:
`deploy/offline-bundle.sh`.

## Kiểm tra chất lượng

```bash
make test                  # pytest + độ phủ (268+ ca: đơn vị, tích hợp, đồng thời)
make lint                  # ruff + mypy + tsc
scripts/verify             # toàn dự án (secret scan, typecheck, build, pytest, ruff)
make eval-data && make eval   # bộ đánh giá trích xuất (≥90% trường đúng, ≤25 giây/hoá đơn)
```

## Cấu trúc

```
backend/          FastAPI + SQLAlchemy + SQLite (WAL) + Alembic
  app/api/        tầng HTTP — 9 router /api/v1 (auth, employees, workflows, documents,
                  runs + SSE, reviews, reports, tools, admin)
  app/services/   điều phối ca sử dụng (biên dịch, thực thi, xác nhận, báo cáo, chỉ số…)
  app/domain/     nghiệp vụ thuần — biên dịch, kiểm chứng V-1..V-5, quy tắc QC, máy trạng thái,
                  5 mẫu quy trình
  app/ports/      bốn giao diện trừu tượng (LLM, kho tệp, hàng đợi, CSDL)
  app/adapters/   hiện thực: mô hình tương thích OpenAI, kho tệp cục bộ, hàng đợi SQLite
  app/tools/      14 công cụ cho tác tử (fs, doc, vision, qc, xlsx, report)
  app/agents/     3 tác tử tuần tự, giới hạn phạm vi công cụ (ADR-002, ADR-004)
  app/workers/    tiến trình nền, bộ lập lịch (cron + theo dõi thư mục), thu hồi việc treo
  scripts/        seed_demo, gen_synthetic_invoices, eval_run, test_llm
frontend/         React 18 + Vite + TypeScript + Tailwind
deploy/           Docker Compose, nginx, gói cài đặt ngoại tuyến
eval/             bộ dữ liệu đánh giá và script chấm điểm (score.py)
docs/             kiến trúc và nhật ký quyết định (ADR-001..008)
```

## Quy tắc phát triển

1. **Lớp `domain/` không được import bất cứ thứ gì từ `api/`, `adapters/` hay `workers/`.**
   Đây là ranh giới quan trọng nhất — vi phạm là mất khả năng kiểm thử độc lập.
2. **Chỉ `core/config.py` được đọc biến môi trường.** Mọi nơi khác import `settings`.
3. **Mọi thay đổi trạng thái lần chạy đi qua `domain/state.py`**, không gán trực tiếp vào cột.
4. **Tiền tệ luôn dùng `Decimal`**, không bao giờ dùng `float` (chỉ đổi sang số ở biên API).
5. **Không sửa lược đồ tại chỗ** — tạo migration Alembic mới (`make migrate m="mô tả"`).
6. **Giao diện không chứa logic nghiệp vụ.** Mọi tính toán do backend làm.

## Trạng thái

Đã hiện thực đầy đủ backend, nối giao diện với backend thật, kiểm thử tự động và kiểm thử
end-to-end trên trình duyệt. Chi tiết, bằng chứng và các điểm cần Owner xác nhận:
`IMPLEMENTATION_PLAN.md` (TASK-008) và `CHECKLIST.md`.
