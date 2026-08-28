# SME AI Workforce

Nền tảng tạo và vận hành nhân viên AI cho doanh nghiệp nhỏ và vừa.
Người dùng mô tả công việc bằng tiếng Việt, hệ thống dựng thành quy trình xử lý chứng từ
chạy tự động theo lịch, có kiểm tra kết quả và có người xác nhận khi nghi ngờ.

## Bắt đầu nhanh

```bash
make setup                 # cài phụ thuộc, tạo file .env
# điền LLM_API_KEY và JWT_SECRET vào backend/.env
make migrate m="init"      # tạo lược đồ cơ sở dữ liệu
make dev-api               # cửa sổ 1 — backend
make dev-web               # cửa sổ 2 — giao diện
make worker                # cửa sổ 3 — tiến trình xử lý nền
```

Mở http://localhost:5173

## Cấu trúc

```
backend/          FastAPI + SQLAlchemy + SQLite
  app/api/        tầng HTTP
  app/services/   điều phối ca sử dụng
  app/domain/     nghiệp vụ thuần — biên dịch, kiểm chứng, quy tắc QC
  app/ports/      bốn giao diện trừu tượng
  app/adapters/   hiện thực cụ thể của bốn cổng
  app/tools/      danh mục công cụ cho tác tử
  app/workers/    tiến trình nền và bộ lập lịch
frontend/         React 18 + Vite + TypeScript + Tailwind
deploy/           Docker Compose, nginx, gói cài đặt ngoại tuyến
eval/             bộ dữ liệu đánh giá và script chấm điểm
docs/             kiến trúc và nhật ký quyết định
```

## Quy tắc phát triển

1. **Lớp `domain/` không được import bất cứ thứ gì từ `api/`, `adapters/` hay `workers/`.**
   Đây là ranh giới quan trọng nhất — vi phạm là mất khả năng kiểm thử độc lập.
2. **Chỉ `core/config.py` được đọc biến môi trường.** Mọi nơi khác import `settings`.
3. **Mọi thay đổi trạng thái đi qua `domain/state.py`**, không gán trực tiếp vào cột.
4. **Tiền tệ luôn dùng `Decimal`**, không bao giờ dùng `float`.
5. **Không sửa lược đồ tại chỗ** — tăng `SCHEMA_VERSION` và tạo phiên bản mới.
6. **Giao diện không chứa logic nghiệp vụ.** Mọi tính toán do backend làm.

## Trạng thái

Bộ khung. Chưa hiện thực — mỗi tệp có phần mô tả trách nhiệm và danh sách việc cần làm.
