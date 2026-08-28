"""
Tiền xử lý ảnh

CHI TIẾT KỸ THUẬT THEN CHỐT. Qwen3-VL dùng độ phân giải động: ảnh 4000×3000 có
thể sinh hơn 8000 token thị giác, làm cạn bộ nhớ đồ hoạ và đội chi phí. Hệ
thống PHẢI tự chuẩn hoá ảnh trước khi gửi, không phó mặc nhà cung cấp.

Cần hiện thực:
  1. preprocess(img) — thứ tự: exif_transpose, deskew, resize theo cạnh dài,
     trần max_pixels
  2. deskew(img) — phát hiện góc nghiêng bằng biến đổi Hough, xoay lại
  3. Giới hạn: MAX_LONG_EDGE=1280, MAX_PIXELS=1638400
  4. Dùng Image.LANCZOS khi thu nhỏ để giữ nét chữ
  5. Trả về ảnh RGB, luôn cùng một quy trình ở mọi môi trường để kết quả đo so
     sánh được
"""
