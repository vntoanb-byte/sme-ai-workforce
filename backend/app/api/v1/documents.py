"""
Điểm cuối chứng từ

Nạp tệp, liệt kê chứng từ theo trạng thái, xem và sửa kết quả trích xuất. Hàng
đợi chờ xác nhận chính là danh sách này với bộ lọc status=needs_review.

Cần hiện thực:
  1. POST /documents/presign — nhận sha256, trả về đã tồn tại hay chưa (chống
     trùng sớm)
  2. POST /documents — nhận multipart, kiểm tra chữ ký nhị phân, tạo artifact +
     document
  3. GET /documents — phân trang, lọc theo status, khoảng ngày, nhà cung cấp
  4. GET /documents/{id} — chi tiết kèm extraction mới nhất và danh sách
     qc_results
  5. GET /documents/{id}/file — trả về tệp gốc (dùng cho khung xem ảnh)
  6. PATCH /documents/{id}/extraction — lưu bản sửa của con người, ghi
     audit_log
"""
