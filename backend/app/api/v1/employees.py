"""
Điểm cuối quản lý nhân viên AI

Tạo, liệt kê, xem, bật/tắt nhân viên AI. Việc tạo sẽ gọi bộ biên dịch quy
trình.

Cần hiện thực:
  1. GET /employees — phân trang, lọc theo trạng thái
  2. POST /employees — nhận {name, job_description}, gọi compiler_service, trả
     về workflow nháp
  3. GET /employees/{id} — chi tiết kèm quy trình hiện hành và lịch chạy
  4. PATCH /employees/{id} — đổi tên, bật, tắt, lưu trữ
  5. DELETE /employees/{id} — chỉ đánh dấu archived, không xoá thật
"""
