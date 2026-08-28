"""
Điểm cuối xác thực

Đăng nhập, làm mới mã truy cập, đăng xuất.

Cần hiện thực:
  1. POST /login — nhận username+password, trả access_token và refresh_token
  2. POST /refresh — đổi refresh_token lấy access_token mới
  3. POST /logout — thu hồi refresh_token
  4. GET /me — thông tin người dùng hiện tại kèm vai trò
"""
