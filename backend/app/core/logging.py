"""
Nhật ký có cấu trúc

Cấu hình structlog xuất JSON, mọi dòng log luôn kèm trace_id, run_id,
step_key.

Cần hiện thực:
  1. setup_logging() gọi một lần lúc khởi động
  2. Processor bổ sung trace_id lấy từ contextvars
  3. Hàm get_logger(__name__) dùng ở mọi module
"""
