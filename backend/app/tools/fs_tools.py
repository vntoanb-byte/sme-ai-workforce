"""
Công cụ hệ thống tệp

Duyệt thư mục theo dõi và lấy danh sách tệp mới.

Cần hiện thực:
  1. fs.list_new_files — so với mốc thời gian lần chạy trước, lọc theo phần mở
     rộng
  2. Bỏ qua tệp đang được ghi dở (kiểm tra kích thước ổn định qua 2 lần đọc)
"""
