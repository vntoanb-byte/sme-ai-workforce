"""
Dịch vụ xác nhận thủ công

Xử lý quyết định của người duyệt và cho quy trình chạy tiếp.

Cần hiện thực:
  1. resolve(review_id, action, corrected_data, user) — ghi audit_log kèm giá
     trị trước và sau
  2. Sau khi duyệt: đưa run trở lại hàng đợi để chạy các bước còn lại
"""
