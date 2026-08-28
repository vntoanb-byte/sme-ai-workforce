"""
Dịch vụ chứng từ

Nạp tệp, tạo artifact và document, khử trùng theo mã băm.

Cần hiện thực:
  1. ingest(file) — tính sha256, nếu đã có thì trả về document cũ kèm cờ
     duplicate
  2. Kiểm tra chữ ký nhị phân của tệp thay vì tin vào phần mở rộng
"""
