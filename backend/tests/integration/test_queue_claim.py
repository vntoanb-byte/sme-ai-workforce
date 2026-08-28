"""
Kiểm thử giao thức giành việc

BÀI KIỂM THỬ QUAN TRỌNG NHẤT. Xác nhận không bao giờ có hai worker cùng nhận
một job.

Cần hiện thực:
  1. Chạy 10 luồng cùng gọi claim() trên 5 job, xác nhận tổng số job giành được
     đúng bằng 5
  2. Xác nhận job quá hạn lease được reap() đưa về pending và attempts tăng
  3. Xác nhận job đạt max_attempts thì chuyển sang failed, không quay lại
     pending
"""
