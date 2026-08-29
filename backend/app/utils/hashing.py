"""
Băm nội dung

Tính mã băm SHA-256 của tệp phục vụ khử trùng và kiểm tra toàn vẹn.
"""

from __future__ import annotations

import hashlib
from typing import BinaryIO

_DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KB


def sha256_bytes(data: bytes) -> str:
    """Tính SHA-256 (hexdigest) của toàn bộ nội dung trong bộ nhớ."""
    return hashlib.sha256(data).hexdigest()


def sha256_stream(fileobj: BinaryIO, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> str:
    """Tính SHA-256 bằng cách đọc theo khối (mặc định 64KB).

    Không load hết file vào RAM — phù hợp tệp lớn. Caller chịu trách nhiệm mở
    và đóng fileobj.
    """
    digest = hashlib.sha256()
    while chunk := fileobj.read(chunk_size):
        digest.update(chunk)
    return digest.hexdigest()
