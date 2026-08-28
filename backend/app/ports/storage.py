"""
Cổng kho tệp

Giao diện trừu tượng cho việc lưu và đọc tệp.

Cần hiện thực:
  1. save(data: bytes, filename: str) -> ArtifactRef (trả về sha256 và đường
     dẫn)
  2. open(ref) -> BinaryIO, exists(sha256) -> bool, delete(ref) -> None
  3. url_for(ref) -> str dùng cho việc hiển thị tệp trên giao diện
"""
