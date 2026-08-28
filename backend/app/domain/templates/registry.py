"""
Sổ đăng ký mẫu quy trình

Tập hợp các mẫu quy trình đã khai báo sẵn. Bộ biên dịch chỉ được chọn trong
tập này.

Cần hiện thực:
  1. TEMPLATES: dict[str, WorkflowTemplate] nạp từ các module cùng thư mục
  2. WorkflowTemplate gồm: code, name, description, steps cố định, danh sách
     tham số cần điền
  3. get_template(code) và list_templates() cho tầng API
  4. Thêm mẫu mới = thêm một file trong thư mục này, KHÔNG sửa compiler
"""
