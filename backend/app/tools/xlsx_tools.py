"""
Công cụ bảng tính

Đọc, ghi, gộp, làm sạch và đối chiếu tệp Excel.

Cần hiện thực:
  1. xlsx.append_rows, xlsx.merge_files, xlsx.dedupe, xlsx.normalize,
     xlsx.reconcile
  2. KHÔNG BAO GIỜ ghi đè tệp gốc — luôn tạo bản mới có đánh dấu thời gian
  3. Dùng openpyxl ở chế độ ghi bổ sung để giữ nguyên định dạng của tệp đích
"""
