"""
Kiểm thử tiền xử lý ảnh

Xác nhận ảnh sau xử lý luôn nằm trong giới hạn đã đặt.

Cần hiện thực:
  1. Ảnh 4000x3000 sau xử lý phải có cạnh dài <= 1280 và tổng điểm ảnh <=
     MAX_PIXELS
  2. Ảnh có EXIF xoay 90 độ phải được dựng lại đúng hướng
"""
