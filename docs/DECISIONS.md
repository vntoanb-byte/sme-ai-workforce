# Nhật ký quyết định kiến trúc

Mỗi quyết định quan trọng ghi lại theo mẫu dưới. Mục đích: sáu tháng sau vẫn nhớ được
vì sao đã chọn như vậy, và khi bảo vệ có sẵn lập luận.

---

## ADR-001 — Dùng bảng trong cơ sở dữ liệu làm hàng đợi, không dùng Redis

**Bối cảnh.** Hệ thống cần chạy quy trình nền theo lịch. Lựa chọn phổ biến là Celery + Redis.

**Quyết định.** Dùng một bảng `job_queue` trong chính SQLite, cùng một tiến trình xử lý.

**Lý do.**
- Doanh nghiệp đích không có nhân sự công nghệ thông tin; mỗi thành phần thêm vào là một
  thứ nữa có thể hỏng và không ai biết sửa.
- Bản ghi `runs` và bản ghi `job_queue` được ghi trong **cùng một transaction**, nên
  không bao giờ xảy ra tình trạng có run mà thiếu job hoặc ngược lại. Redis không làm được
  điều này vì là hai kho dữ liệu tách biệt.
- Khối lượng thực tế (300–500 chứng từ mỗi tháng) nằm xa dưới giới hạn của một tiến trình.

**Đánh đổi.** Không mở rộng theo chiều ngang được. Chấp nhận, vì kịch bản triển khai công
khai đã có đường chuyển sang PostgreSQL + Celery qua cùng một giao diện `JobQueue`.

**Bẫy kỹ thuật.** SQLite **không có** `SELECT ... FOR UPDATE SKIP LOCKED`. Giao thức giành
việc phải dùng `BEGIN IMMEDIATE` + `UPDATE ... WHERE id=? AND status='pending'` rồi kiểm
tra `rowcount`. Xem `app/adapters/queue_sqlite.py`.

---

## ADR-002 — Không dùng vòng lặp tác tử tự chủ cho việc lập kế hoạch

**Bối cảnh.** Xu hướng phổ biến là để tác tử tự quyết định gọi công cụ nào theo vòng lặp
suy nghĩ — hành động.

**Quyết định.** Quy giản thành hai bước: phân loại ý định vào một tập mẫu có sẵn, rồi điền
tham số bằng một lời gọi có ràng buộc lược đồ.

**Lý do.** Mô hình cỡ vừa có tỷ lệ gọi công cụ nhiều bước thành công thấp. Ngoài ra vòng
lặp tự chủ không lặp lại được và không kiểm chứng trước được — hai tính chất bắt buộc với
dữ liệu kế toán.

**Đánh đổi.** Chỉ hỗ trợ được các quy trình nằm trong tập mẫu. Chấp nhận: thêm mẫu mới là
thêm một tệp trong `domain/templates/`.

---

## ADR-003 — Hàng đợi chờ xác nhận không phải một màn hình riêng

**Quyết định.** Bỏ màn hình "Hàng đợi chờ xác nhận"; dùng chính danh sách chứng từ với bộ
lọc `status=needs_review`.

**Lý do.** Cùng một đối tượng dữ liệu, cùng một khuôn hiển thị. Tách thành hai màn hình
nghĩa là bảo trì hai bộ mã cho một việc.

---

## ADR-0xx — (mẫu để điền tiếp)

**Bối cảnh.** ...
**Quyết định.** ...
**Lý do.** ...
**Đánh đổi.** ...
