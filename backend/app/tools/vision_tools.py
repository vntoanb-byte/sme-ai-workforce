"""
Công cụ thị giác

Gọi mô hình để đọc chứng từ và phân loại tài liệu.

Cần hiện thực:
  1. vision.extract_invoice — nạp schema, dựng prompt, gọi
     llm.complete(schema=...)
  2. vision.classify_document — phân loại vào tập nhãn cho trước
  3. Luôn ghi model_name và prompt_version vào bản ghi extraction
"""
