"""
Điểm cuối báo cáo

Sinh báo cáo tổng hợp theo kỳ dưới dạng Excel hoặc PDF.

Cần hiện thực:
  1. POST /reports/preview — nhận {from, to, group_by}, trả về dữ liệu tổng hợp
     dạng JSON
  2. POST /reports/export — sinh tệp, trả về artifact_id
  3. GET /reports/{artifact_id}/download — tải tệp về
"""
