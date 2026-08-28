"""
Dịch vụ biên dịch

Bọc domain.compiler, thêm phần ghi CSDL và ghi nhật ký.

Cần hiện thực:
  1. compile_and_save(employee_id, text) -> Workflow | list[SpecError]
  2. Lưu cả mô tả gốc của người dùng để về sau phân tích và cải tiến prompt
"""
