"""
Bộ lập lịch

Dùng APScheduler với job store lưu trong chính CSDL SQLite.

Cần hiện thực:
  1. Khởi tạo BackgroundScheduler với SQLAlchemyJobStore trỏ vào DATABASE_URL
  2. Với mỗi schedule đang bật: đăng ký một CronTrigger tạo bản ghi run
  3. Theo dõi thư mục: một job chạy mỗi phút quét WATCH_PATH tìm tệp mới
  4. Đăng ký job định kỳ gọi reaper.reap() mỗi phút
  5. Múi giờ mặc định Asia/Ho_Chi_Minh
"""
