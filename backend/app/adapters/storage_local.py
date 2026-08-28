"""
Bộ chuyển đổi kho tệp cục bộ

Lưu tệp trên hệ thống tệp, đặt tên theo mã băm SHA-256 của nội dung.

Cần hiện thực:
  1. Đường dẫn dạng artifacts/<2 ký tự đầu>/<2 ký tự tiếp>/<sha256><ext>
  2. save() tính hash trước, nếu tệp đã tồn tại thì trả về ref cũ (khử trùng tự
     nhiên)
  3. Ghi qua tệp tạm rồi os.replace để bảo đảm tính nguyên tử
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import uuid
from pathlib import Path
from typing import BinaryIO

from app.ports.storage import ArtifactRef


def _guess_content_type(filename: str) -> str | None:
    """Suy content_type từ phần mở rộng tệp (không bắt buộc chính xác 100%)."""
    guessed, _ = mimetypes.guess_type(filename)
    return guessed


class LocalFileStorage:
    """Hiện thực FileStorage trên hệ thống tệp cục bộ.

    NOTE (suy luận — cần Owner xác nhận lại): docstring gốc ghi cấu trúc
    "artifacts/<2>/<2>/<sha><ext>", nhưng settings.STORAGE_PATH mặc định đã là
    "./data/artifacts" (đã có sẵn "artifacts" trong đường dẫn gốc). Adapter này
    KHÔNG thêm một lớp "artifacts/" nữa để tránh trùng lặp "artifacts/artifacts/..."
    — cấu trúc đường dẫn tương đối so với base_path là <2>/<2>/<sha><ext>.
    """

    def __init__(self, base_path: str | Path) -> None:
        """Khởi tạo với base_path do NƠI GỌI truyền vào (vd. settings.STORAGE_PATH).

        File này KHÔNG tự đọc settings/os.environ — chỉ core/config.py được phép
        (quy tắc kiến trúc, xem ARCHITECTURE.md). Tự tạo base_path nếu chưa có.
        """
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _rel_path(self, sha256: str, ext: str) -> str:
        """Đường dẫn tương đối (dấu "/") từ base_path: <sha[:2]>/<sha[2:4]>/<sha><ext>."""
        return f"{sha256[:2]}/{sha256[2:4]}/{sha256}{ext}"

    def _abs_path(self, rel_path: str) -> Path:
        return self._base_path / rel_path

    def save(self, data: bytes, filename: str) -> ArtifactRef:
        """Lưu nội dung vào kho, trả về ArtifactRef (khử trùng tự nhiên).

        Tính sha256 TRƯỚC. Nếu tệp đích đã tồn tại VÀ đúng kích thước bằng
        len(data) thì coi là trùng, trả về ref của tệp đã có mà không ghi lại
        (không cần so từng byte — sha256 trùng + kích thước trùng là đủ tin cậy
        cho mục đích này, tránh đọc lại toàn bộ tệp cũ). Ngược lại ghi qua tệp
        tạm cùng thư mục đích rồi os.replace để bảo đảm tính NGUYÊN TỬ.
        """
        sha256 = hashlib.sha256(data).hexdigest()
        ext = os.path.splitext(filename)[1]  # giữ nguyên kể cả rỗng
        rel_path = self._rel_path(sha256, ext)
        dest = self._abs_path(rel_path)

        if dest.is_file() and dest.stat().st_size == len(data):
            return ArtifactRef(
                sha256=sha256,
                path=rel_path,
                size_bytes=len(data),
                content_type=_guess_content_type(filename),
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest.parent / f".tmp-{uuid.uuid4().hex}"
        try:
            with open(tmp_path, "wb") as f:
                f.write(data)
            os.replace(tmp_path, dest)
        finally:
            # Dọn tệp tạm nếu os.replace chưa chạy (vd. ghi file bị lỗi giữa chừng).
            if tmp_path.exists():
                tmp_path.unlink()

        return ArtifactRef(
            sha256=sha256,
            path=rel_path,
            size_bytes=len(data),
            content_type=_guess_content_type(filename),
        )

    def open(self, ref: ArtifactRef) -> BinaryIO:
        """Mở tệp đã lưu ở chế độ nhị phân — caller chịu trách nhiệm đóng."""
        return open(self._abs_path(ref.path), "rb")

    def exists(self, sha256: str) -> bool:
        """Kiểm tra tệp có sha256 (KHÔNG kèm phần mở rộng) tồn tại trong kho hay không.

        Tên tệp thật có thể là <sha256><ext> hoặc <sha256> (filename gốc không
        có phần mở rộng), nằm trong thư mục <sha256[:2]>/<sha256[2:4]>/ — nên
        phải tìm bằng glob f"{sha256}.*" VÀ kiểm tệp không có phần mở rộng.
        """
        leaf_dir = self._base_path / sha256[:2] / sha256[2:4]
        if not leaf_dir.is_dir():
            return False
        return (leaf_dir / sha256).is_file() or any(leaf_dir.glob(f"{sha256}.*"))

    def delete(self, ref: ArtifactRef) -> None:
        """Xoá tệp khỏi kho — idempotent, không raise lỗi nếu tệp đã không còn."""
        dest = self._abs_path(ref.path)
        if dest.is_file():
            dest.unlink()

    def url_for(self, ref: ArtifactRef) -> str:
        """Đường dẫn hiển thị tệp trên giao diện, dạng "/artifacts/{ref.path}".

        NOTE (cần Owner xác nhận): CHỈ là định dạng dữ liệu — chưa nối với route
        API thật nào (api/v1/documents.py vẫn là stub). Khi có route thật, phần
        tiền tố này có thể phải đổi theo đường dẫn API.
        """
        return f"/artifacts/{ref.path}"
