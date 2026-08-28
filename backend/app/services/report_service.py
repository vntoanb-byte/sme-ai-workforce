"""
Dịch vụ báo cáo

Tổng hợp dữ liệu theo kỳ và kết xuất tệp.

Cần hiện thực:
  1. aggregate(from, to, group_by) -> dict — truy vấn SQL, không nạp hết vào bộ
     nhớ
  2. export(data, fmt) -> artifact_id
"""
