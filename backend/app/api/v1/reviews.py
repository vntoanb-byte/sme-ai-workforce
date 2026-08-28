"""
Điểm cuối xác nhận thủ công

Xử lý các bản ghi bị tầng kiểm soát chất lượng đánh dấu.

Cần hiện thực:
  1. GET /reviews — hàng đợi chờ, sắp theo mức độ nghiêm trọng rồi tới thời
     gian
  2. POST /reviews/{id}/resolve — nhận {action: approve|correct|reject, data?}
  3. GET /reviews/stats — số lượng đang chờ, phục vụ chấm đỏ trên thanh điều
     hướng
"""
