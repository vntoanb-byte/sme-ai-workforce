"""
Điểm cuối quy trình

Xem, sửa và phê duyệt đặc tả quy trình.

Cần hiện thực:
  1. GET /workflows/{id} — trả về đồ thị {steps, edges} để giao diện vẽ sơ đồ
  2. PUT /workflows/{id} — nhận WorkflowSpec đã sửa, chạy lại validators, tạo
     phiên bản MỚI
  3. POST /workflows/{id}/approve — chuyển sang approved, đăng ký lịch với
     scheduler
  4. POST /workflows/{id}/validate — chỉ kiểm chứng, không lưu (dùng khi người
     dùng đang sửa)
"""
