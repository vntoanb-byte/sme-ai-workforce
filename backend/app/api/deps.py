"""
Các phụ thuộc dùng chung của tầng API

Cung cấp phiên CSDL, người dùng hiện tại và kiểm tra vai trò cho mọi điểm
cuối.

Cần hiện thực:
  1. get_db() -> Generator[Session] — mở phiên, đóng ở finally
  2. get_current_user(token) -> User — giải mã JWT, tra CSDL, ném 401 nếu sai
  3. require_role('MANAGER') -> Callable — factory tạo dependency kiểm tra vai
     trò
  4. get_llm() / get_storage() / get_queue() — trả về adapter theo cấu hình
"""
