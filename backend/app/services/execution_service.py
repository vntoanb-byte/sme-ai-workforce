"""
Dịch vụ thực thi một lần chạy

Điều phối toàn bộ vòng đời của một lần chạy: đọc quy trình, chạy từng bước,
ghi trạng thái và nhật ký, xử lý lỗi và quyết định có thử lại hay không.

Cần hiện thực:
  1. execute(run_id) — hàm public duy nhất, được worker gọi
  2. Nạp workflow, dựng danh sách bước theo thứ tự tô-pô
  3. Với mỗi bước: tạo run_step, gọi công cụ, lưu artifact đầu ra, cập nhật
     trạng thái
  4. Bắt ngoại lệ, phân loại tạm thời hay vĩnh viễn, chỉ thử lại nhóm tạm thời
  5. Sau bước kiểm soát chất lượng: nếu needs_review thì dừng và chuyển trạng
     thái NEEDS_REVIEW
  6. Ghi run_logs ở mọi bước và đẩy vào hàng đợi SSE nếu có người đang theo dõi
"""
