"""
Kiểm thử tiền xử lý ảnh

Xác nhận ảnh sau xử lý luôn nằm trong giới hạn đã đặt.
"""

from __future__ import annotations

import io

from PIL import Image

from app.core.config import settings
from app.utils.images import preprocess


def test_large_image_is_bounded() -> None:
    out = preprocess(Image.new("RGB", (4000, 3000), "white"))
    assert max(out.size) <= settings.IMAGE_MAX_LONG_EDGE
    assert out.width * out.height <= settings.IMAGE_MAX_PIXELS
    # giữ tỉ lệ khung hình
    assert abs(out.width / out.height - 4 / 3) < 0.01


def test_small_image_untouched_and_rgb() -> None:
    out = preprocess(Image.new("L", (300, 200), 128))
    assert out.size == (300, 200)
    assert out.mode == "RGB"


def test_exif_rotation_is_applied() -> None:
    # Ảnh chụp ngang 200x100 kèm thẻ EXIF Orientation=6 (xoay 90°) phải được
    # dựng lại thành ảnh dọc 100x200.
    img = Image.new("RGB", (200, 100), "white")
    exif = img.getexif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    out = preprocess(Image.open(io.BytesIO(buf.getvalue())))
    assert out.size == (100, 200)
