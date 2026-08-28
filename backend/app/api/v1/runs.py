"""
Điểm cuối lần chạy

Kích hoạt thủ công, xem lịch sử, xem chi tiết và truyền nhật ký thời gian
thực.

Cần hiện thực:
  1. POST /runs — kích hoạt thủ công một nhân viên AI, trả về run_id
  2. GET /runs — phân trang, lọc theo employee_id, status, khoảng thời gian
  3. GET /runs/{id} — chi tiết kèm danh sách run_steps và thống kê
  4. GET /runs/{id}/logs — StreamingResponse kiểu text/event-stream (SSE)
  5. POST /runs/{id}/cancel — huỷ một lần chạy đang chờ hoặc đang chạy
"""
