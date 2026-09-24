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

## ADR-004 — Điều phối tác tử bằng vòng lặp tuần tự thuần Python, không dùng thư viện CrewAI

**Bối cảnh.** ADR-002 đã loại bỏ việc tác tử tự lập kế hoạch; điều còn lại chỉ là gọi các
công cụ theo đúng thứ tự đã kiểm chứng. CrewAI 0.80 kéo theo hàng trăm gói phụ thuộc (không
cài được trong gói ngoại tuyến — xem `backend/requirements-no-crewai.txt` có sẵn từ trước).

**Quyết định.** `agents/crew.py` giữ đúng mô hình "3 tác tử + Process.sequential + phạm vi
công cụ riêng" nhưng hiện thực bằng Python thuần; bỏ `crewai` khỏi `requirements.txt`.
Docstring gốc của `crew.py` đã cho phép phương án này.

**Đánh đổi.** Không dùng được các tính năng khác của CrewAI (bộ nhớ, uỷ quyền) — vốn cũng
bị ADR-002 loại trừ. **Cần Owner xác nhận** vì bảng công nghệ trong `PROJECT.md` còn ghi CrewAI.

---

## ADR-005 — Phiên đăng nhập: access token trong bộ nhớ + refresh token cookie HttpOnly xoay vòng

**Quyết định.** Access token JWT 15 phút giữ trong bộ nhớ trình duyệt (không localStorage);
refresh token 7 ngày nằm trong cookie `HttpOnly; SameSite=Strict; Path=/api/v1/auth`, lưu
`jti` ở bảng `refresh_tokens` (migration 0002) để đăng xuất thu hồi được; mỗi lần làm mới
cấp token mới và thu hồi token cũ. Một cookie `access_token` (HttpOnly, Path=/api/v1) chỉ
được chấp nhận cho GET/HEAD — phục vụ thẻ `<img>`, EventSource (SSE) và tải tệp, những
request trình duyệt không gắn được header.

**Lý do.** Chống XSS đánh cắp token dài hạn; F5 không mất phiên; không mở CSRF (thao tác ghi
bắt buộc header `Authorization`).

---

## ADR-006 — Chạy tiếp lần chạy sau khi xác nhận thủ công

**Quyết định.** Khi bước QC tách được chứng từ không đạt: nhánh ĐẠT vẫn chạy cho chứng từ
tốt, nhánh KHÔNG ĐẠT đưa chứng từ vào hàng chờ, lần chạy dừng ở `NEEDS_REVIEW`. Khi chứng
từ cuối cùng của lần chạy được xử lý: còn chứng từ được chấp nhận → lần chạy quay lại hàng
đợi (`NEEDS_REVIEW → RETRYING → PENDING`) và CHỈ chạy các bước của nhánh đạt cho đúng các
chứng từ vừa duyệt; tất cả bị từ chối → `SUCCEEDED` ngay.

**Lý do.** Chứng từ tốt không phải chờ chứng từ lỗi; không đọc lại hoá đơn (tốn mô hình);
mọi chuyển trạng thái vẫn đi qua `domain/state.py`.

---

## ADR-007 — Lưu trigger của từng phiên bản quy trình ở bảng `schedules`; mã mẫu đổi ở biên API

**Quyết định.** Bảng `workflows` không có cột trigger → mỗi phiên bản có 1 dòng `schedules`
(tạo ngay khi lưu, `is_enabled=False` tới khi được duyệt và nhân viên đang active). Bộ lập
lịch (tiến trình worker) đọc lại `schedules` mỗi phút — bật/tắt từ API có hiệu lực ≤ 1 phút
mà không cần gọi chéo tiến trình. Mã mẫu lưu dạng `invoice_to_excel` (WorkflowSpec), trả
ra giao diện dạng `TPL_INVOICE_TO_EXCEL`; chuyển đổi duy nhất ở `services/workflow_service.py`.

**Lý do.** Không đổi lược đồ; giải quyết mâu thuẫn tên mã mẫu (ghi trong `memory.md`) mà
không sửa hợp đồng của bên nào.

---

## ADR-008 — Giữ khoá ghi SQLite ngắn: commit trước mỗi lời gọi mô hình

**Bối cảnh.** SQLite chỉ có một người ghi. Lời gọi mô hình mất 10–25 giây/hoá đơn; nếu giữ
transaction ghi trong lúc chờ, mọi thao tác ghi khác (tải lên, huỷ, xác nhận) chờ quá
`busy_timeout` 10 giây và báo "database is locked" (đã tái hiện bằng kiểm thử).

**Quyết định.** Luồng tải lên và công cụ `vision.extract_invoice` commit bản ghi chứng từ
(trạng thái `processing`) TRƯỚC lời gọi mô hình; nhật ký lần chạy commit từng dòng. Mọi công
cụ bất biến khi lặp (khử trùng theo sha256, QC ghi đè kết quả cũ) nên thử lại an toàn.

---

## ADR-0xx — (mẫu để điền tiếp)

**Bối cảnh.** ...
**Quyết định.** ...
**Lý do.** ...
**Đánh đổi.** ...
