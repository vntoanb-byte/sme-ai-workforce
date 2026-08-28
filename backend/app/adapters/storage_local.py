"""
Bộ chuyển đổi kho tệp cục bộ

Lưu tệp trên hệ thống tệp, đặt tên theo mã băm SHA-256 của nội dung.

Cần hiện thực:
  1. Đường dẫn dạng artifacts/<2 ký tự đầu>/<2 ký tự tiếp>/<sha256><ext>
  2. save() tính hash trước, nếu tệp đã tồn tại thì trả về ref cũ (khử trùng tự
     nhiên)
  3. Ghi qua tệp tạm rồi os.replace để bảo đảm tính nguyên tử
"""
