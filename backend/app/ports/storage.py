"""
Cổng kho tệp

Giao diện trừu tượng cho việc lưu và đọc tệp.

Cần hiện thực:
  1. save(data: bytes, filename: str) -> ArtifactRef (trả về sha256 và đường
     dẫn)
  2. open(ref) -> BinaryIO, exists(sha256) -> bool, delete(ref) -> None
  3. url_for(ref) -> str dùng cho việc hiển thị tệp trên giao diện
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class ArtifactRef:
    """Tham chiếu tới một tệp đã lưu trong kho tệp.

    Attributes:
        sha256: mã băm SHA-256 của nội dung tệp.
        path: đường dẫn TƯƠNG ĐỐI so với base_path của adapter, luôn dùng dấu
            "/" (kể cả trên Windows) để nhất quán giữa các nền tảng.
        size_bytes: kích thước tệp tính bằng byte.
        content_type: suy từ phần mở rộng tệp (không bắt buộc chính xác 100%).
    """

    sha256: str
    path: str
    size_bytes: int
    content_type: str | None


class FileStorage(Protocol):
    """Giao diện kho tệp — tầng nghiệp vụ chỉ biết tới giao diện này."""

    def save(self, data: bytes, filename: str) -> ArtifactRef:
        """Lưu nội dung vào kho, trả về ArtifactRef.

        Nếu nội dung đã tồn tại (cùng sha256, cùng kích thước) thì trả về ref
        của tệp đã có mà không ghi lại (khử trùng tự nhiên).
        """
        ...

    def open(self, ref: ArtifactRef) -> BinaryIO:
        """Mở tệp đã lưu ở chế độ nhị phân.

        Caller chịu trách nhiệm đóng (hoặc dùng context manager).
        """
        ...

    def exists(self, sha256: str) -> bool:
        """Kiểm tra tệp có sha256 đã cho có tồn tại trong kho hay không.

        sha256 được truyền KHÔNG kèm phần mở rộng.
        """
        ...

    def delete(self, ref: ArtifactRef) -> None:
        """Xoá tệp khỏi kho. Idempotent — không lỗi nếu tệp đã không còn."""
        ...

    def url_for(self, ref: ArtifactRef) -> str:
        """Trả về đường dẫn hiển thị tệp trên giao diện."""
        ...
