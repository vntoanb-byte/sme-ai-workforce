"""
Điểm cuối quản trị

Quản lý người dùng, phân quyền, cấu hình hệ thống và xem chỉ số vận hành.

Cần hiện thực:
  1. GET/POST/PATCH /admin/users — quản lý tài khoản
  2. GET/PUT /admin/settings — cấu hình dạng khoá-giá trị
  3. GET /admin/metrics — số lần chạy, độ trễ, tỷ lệ xác nhận thủ công, token
     đã dùng
  4. POST /admin/llm/test — thử kết nối tới máy chủ mô hình
"""
