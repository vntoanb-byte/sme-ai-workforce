"""
DTO dùng chung

Page[T] phân trang, ErrorResponse, IdResponse. Chỉ chứa mô hình Pydantic,
không có logic.

Cần hiện thực:
  1. Tách rõ mô hình Create, Update và Out — không dùng chung một lớp
  2. Mô hình Out phải có model_config = ConfigDict(from_attributes=True)
"""
