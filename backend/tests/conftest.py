"""
Cấu hình chung cho pytest

Các fixture dùng lại ở mọi bài kiểm thử.

Cần hiện thực:
  1. fixture db — tạo CSDL SQLite tạm trong bộ nhớ, chạy migration, dọn sau mỗi
     test
  2. fixture client — TestClient của FastAPI với dependency get_db bị ghi đè
  3. fixture fake_llm — LLMProvider giả trả về phản hồi ghi sẵn từ
     tests/fixtures
  4. fixture auth_headers — token của người dùng thử nghiệm theo từng vai trò
"""
