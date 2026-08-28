"""
Dịch vụ nhân viên AI

Tạo, cập nhật, bật tắt nhân viên AI và đăng ký lịch chạy.

Cần hiện thực:
  1. create(name, job_description) — gọi compiler_service rồi lưu workflow nháp
  2. activate(id) — chỉ cho phép khi workflow ở trạng thái approved
  3. Khi bật/tắt phải đồng bộ với APScheduler
"""
