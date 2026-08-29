"""
Tiền xử lý ảnh

CHI TIẾT KỸ THUẬT THEN CHỐT. Qwen3-VL dùng độ phân giải động: ảnh 4000×3000 có
thể sinh hơn 8000 token thị giác, làm cạn bộ nhớ đồ hoạ và đội chi phí. Hệ
thống PHẢI tự chuẩn hoá ảnh trước khi gửi, không phó mặc nhà cung cấp.
"""

from __future__ import annotations

from PIL import Image, ImageOps

from app.core.config import settings


def deskew(img: Image.Image) -> Image.Image:
    """Làm thẳng ảnh nghiêng bằng biến đổi Hough.

    TODO (TASK-006): chưa hiện thực biến đổi Hough — trả nguyên ảnh không đổi
    (no-op CÓ CHỦ ĐÍCH theo quyết định cắt phạm vi của Claude trong
    IMPLEMENTATION_PLAN.md, KHÔNG âm thầm bỏ qua yêu cầu gốc; làm sau nếu ảnh
    nghiêng thật gây sai kết quả).
    """
    return img


def preprocess(img: Image.Image) -> Image.Image:
    """Chuẩn hoá ảnh trước khi gửi tới mô hình.

    Thứ tự cố định (luôn cùng một quy trình ở mọi môi trường để kết quả đo so
    sánh được):
      1. ImageOps.exif_transpose — dựng lại hướng ảnh theo thẻ EXIF.
      2. deskew — hiện tại là no-op (xem docstring deskew).
      3. resize theo cạnh dài xuống settings.IMAGE_MAX_LONG_EDGE bằng
         Image.Resampling.LANCZOS (giữ nét chữ).
      4. trần tổng điểm ảnh settings.IMAGE_MAX_PIXELS.
      5. convert("RGB").
    """
    img = ImageOps.exif_transpose(img)
    img = deskew(img)

    long_edge = max(img.size)
    if long_edge > settings.IMAGE_MAX_LONG_EDGE:
        ratio = settings.IMAGE_MAX_LONG_EDGE / long_edge
        new_size = (round(img.width * ratio), round(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    if img.width * img.height > settings.IMAGE_MAX_PIXELS:
        ratio = (settings.IMAGE_MAX_PIXELS / (img.width * img.height)) ** 0.5
        new_size = (round(img.width * ratio), round(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    return img.convert("RGB")
