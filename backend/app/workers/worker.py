"""
Tiến trình xử lý nền

Vòng lặp vô hạn: giành việc từ hàng đợi, gọi execution_service, báo kết quả.
Chạy như một tiến trình riêng trong cùng container.

Cần hiện thực:
  1. Vòng lặp: job = queue.claim(worker_id, lease); nếu None thì sleep
     POLL_INTERVAL
  2. Gia hạn lease định kỳ nếu công việc chạy lâu (heartbeat)
  3. Bắt MỌI ngoại lệ — worker không bao giờ được phép chết vì một job lỗi
  4. Xử lý tín hiệu SIGTERM: hoàn tất job hiện tại rồi thoát sạch
  5. Ghi worker_id gồm hostname và pid để truy vết
"""
