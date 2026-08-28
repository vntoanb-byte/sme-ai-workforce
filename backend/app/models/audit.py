"""
Mô hình nhật ký và cấu hình

Định nghĩa bảng: audit_logs, llm_calls, settings. Xem Phụ lục A của tài liệu
thiết kế để lấy DDL đầy đủ.

Cần hiện thực:
  1. Khai báo class kế thừa Base với __tablename__ đúng tên bảng
  2. Mọi khoá ngoại phải có ondelete rõ ràng (CASCADE hoặc RESTRICT)
  3. Cột lưu JSON dùng kiểu Text, đọc ghi qua json.dumps/loads ở tầng service
  4. Khai báo Index và UniqueConstraint trong __table_args__
  5. Thêm relationship hai chiều với back_populates
"""
