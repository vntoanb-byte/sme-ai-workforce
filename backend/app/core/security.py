"""
Xác thực và mã hoá

Băm mật khẩu, tạo và giải mã JWT, mã hoá thông tin đăng nhập tích hợp.

Cần hiện thực:
  1. hash_password / verify_password dùng argon2-cffi
  2. create_access_token(sub, roles, ttl) và create_refresh_token(sub)
  3. decode_token(token) -> payload, ném AppError nếu hết hạn hoặc sai chữ ký
  4. encrypt_secret / decrypt_secret dùng cryptography.fernet với
     CREDENTIAL_ENC_KEY
"""
