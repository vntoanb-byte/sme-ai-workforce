# SECURITY.md

## Secret / `.env` / API key
- Mọi bí mật chỉ nằm trong `backend/.env` (đã `.gitignore`); chỉ `core/config.py` đọc biến môi trường.
- `JWT_SECRET` bắt buộc đặt khi vận hành (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
  Để trống hoặc để nguyên giá trị mẫu của `.env.example` → hệ thống dùng khoá ngẫu nhiên tạm
  (an toàn nhưng mọi phiên mất khi khởi động lại) và ghi cảnh báo — không bao giờ ký token bằng giá trị mẫu công khai.
- `CREDENTIAL_ENC_KEY`: mã hoá (Fernet) các cấu hình khoá `secret.*` lưu trong bảng `settings`;
  API không bao giờ trả giá trị thật (chỉ `••••••`).
- `LLM_API_KEY` có thể để trống với vLLM nội bộ.

## Personal data
- Dữ liệu chứng từ (hoá đơn, mã số thuế) chỉ nằm trên máy chủ nội bộ; triển khai `deploy/docker-compose.yml`
  dùng mô hình chạy tại chỗ (vLLM) — không gửi dữ liệu thật ra dịch vụ AI bên ngoài.
- Dịch vụ trung gian qua Internet (OpenRouter, …) CHỈ dùng khi phát triển với dữ liệu giả/tổng hợp
  (`scripts/gen_synthetic_invoices.py`).
- Nhật ký lời gọi mô hình (`llm_calls`) chỉ lưu số token, độ trễ, lỗi — không lưu nội dung chứng từ.

## Authentication / Permission
- Mật khẩu băm argon2 (không lưu plaintext); tối thiểu 8 ký tự; so sánh thời gian cố định kể cả khi tài khoản không tồn tại.
- Access token JWT 15 phút giữ trong bộ nhớ trình duyệt (không localStorage). Refresh token 7 ngày trong cookie
  `HttpOnly; SameSite=Strict; Path=/api/v1/auth`, xoay vòng mỗi lần làm mới, thu hồi được (bảng `refresh_tokens`).
  Đổi mật khẩu / khoá tài khoản thu hồi mọi phiên.
- Cookie `access_token` chỉ được chấp nhận cho GET/HEAD (ảnh chứng từ, SSE, tải tệp) → thao tác ghi bắt buộc header
  `Authorization` (chống CSRF).
- Phân quyền ở backend cho MỌI điểm cuối (`api/deps.py`): USER — xem, nạp và xác nhận chứng từ, báo cáo;
  MANAGER — tạo/duyệt/chạy/huỷ nhân viên AI; ADMIN — người dùng, cấu hình, thử kết nối mô hình.
  Quản trị viên không thể tự khoá hoặc tự bỏ quyền ADMIN của chính mình.
- `COOKIE_SECURE=true` bắt buộc khi chạy sau HTTPS (`deploy/nginx.conf`, profile `https`).

## File access
- Công cụ trong quy trình chỉ đọc tệp dưới `WATCH_PATH` và `FS_ALLOWED_ROOTS` (chặn cấu hình quy trình trỏ ra
  `/etc`, `..`); thư mục quét gắn CHỈ ĐỌC vào container.
- Không bao giờ ghi đè tệp gốc của người dùng — kết quả là tệp mới trong kho (`STORAGE_PATH`).
- Tải lên giới hạn `MAX_UPLOAD_MB`, kiểm loại nội dung (image/*, application/pdf), kho tệp đặt tên theo sha256
  (không dùng tên tệp người dùng làm đường dẫn). Tên tệp tải về được lọc ký tự trước khi đặt vào `Content-Disposition`.

## Database / Backup
- SQLite WAL; mọi truy vấn qua ORM/tham số hoá (không nối chuỗi SQL với dữ liệu người dùng).
- Thay đổi lược đồ chỉ qua migration Alembic (`backend/alembic/versions`); API tự `upgrade head` khi khởi động.
- Nhật ký kiểm toán (`audit_logs`, `run_logs`, `human_reviews`) không có API sửa/xoá.
- Sao lưu: CHƯA tự động hoá (`BACKUP_PATH` mới là cấu hình) — xem mục Còn thiếu trong `IMPLEMENTATION_PLAN.md`.

## Error handling
- Lỗi trả về dạng `{error:{code,message,details,trace_id}}`; lỗi 500 không lộ traceback, chỉ `trace_id` để tra log JSON.

## Production / Deploy
- Không deploy production khi chưa được Owner duyệt (`.claude/rules/00-safety.md`).
- Chưa có giới hạn tần suất đăng nhập (rate limit) — khuyến nghị đặt ở nginx (`limit_req`) khi mở ra ngoài mạng nội bộ.

## Dependency
- Không dùng thư viện CrewAI (ADR-004) — giảm hàng trăm gói phụ thuộc trong gói cài đặt ngoại tuyến.

## Hành động bắt buộc phải có người duyệt
Xem `.claude/rules/00-safety.md` — danh sách chung cho mọi project.
