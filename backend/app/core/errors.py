"""
Lỗi ứng dụng

Định nghĩa cây ngoại lệ và bộ chuyển đổi sang phản hồi HTTP theo cấu trúc
thống nhất.

Cần hiện thực:
  1. class AppError(Exception) với code, message, details, http_status
  2. Các lớp con: NotFound, Forbidden, ValidationFailed, LLMUnavailable,
     StorageError
  3. app_error_handler(request, exc) trả về JSON
     {error:{code,message,details,trace_id}}
  4. Phân loại lỗi tạm thời và lỗi vĩnh viễn — worker dùng để quyết định có thử
     lại không
"""
