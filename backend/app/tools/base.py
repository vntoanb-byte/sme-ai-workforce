"""
Lớp cơ sở và sổ đăng ký công cụ

Mọi công cụ kế thừa lớp này và tự đăng ký vào registry khi được import.

Cần hiện thực:
  1. class ToolBase: code, name, category, input_schema, output_schema, run()
  2. Decorator @register_tool đưa lớp vào TOOL_REGISTRY
  3. sync_tools_to_db(session) — đồng bộ registry với bảng tools lúc khởi động
  4. Mỗi công cụ phải bất biến khi lặp: chạy lại trên cùng đầu vào cho cùng kết
     quả
"""
