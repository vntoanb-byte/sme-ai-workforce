"""
Kiểm thử luồng thực thi

Chạy trọn một quy trình với mô hình giả.

Cần hiện thực:
  1. Kịch bản đạt: chạy hết các bước, trạng thái SUCCEEDED
  2. Kịch bản QC không đạt: dừng ở NEEDS_REVIEW, có bản ghi human_reviews
  3. Kịch bản lỗi tạm thời: thử lại đúng số lần rồi mới FAILED
"""
