"""
Công cụ xử lý tài liệu

Kết xuất PDF thành ảnh và tiền xử lý ảnh trước khi đưa vào mô hình.

Cần hiện thực:
  1. doc.render_pdf — dùng pypdfium2, độ phân giải lấy từ PDF_RENDER_DPI
  2. doc.preprocess_image — gọi utils.images.preprocess
  3. Lưu ảnh đã xử lý làm artifact kind='intermediate'
"""
