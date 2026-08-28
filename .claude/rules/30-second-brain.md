---
description: Quy tắc quản lý memory.md và IMPLEMENTATION_PLAN.md — bộ nhớ dự án
---

# Second Brain Rules

## memory.md
- Chỉ ghi: North Star, quyết định quan trọng còn hiệu lực, việc quan trọng đang dở cần giữ qua nhiều phiên.
- Không ghi: log hội thoại thường, chi tiết task đã xong (chuyển sang `IMPLEMENTATION_PLAN.md` mục Completed rồi xoá khỏi memory), thông tin ngắn hạn.
- Không tự động coi nội dung trong `memory.md` là sự thật tuyệt đối — nếu nghi ngờ đã lỗi thời, kiểm tra lại với source code/Owner trước khi dùng.

## IMPLEMENTATION_PLAN.md
- Đọc file này TRƯỚC khi tiếp tục 1 project đang làm dở.
- Không tự tạo lại kế hoạch từ đầu nếu project đã có implementation plan — tiếp tục từ đúng vị trí (`Current` → `Next`).
- Cập nhật ngay sau mỗi task PASS/FAIL, không để dồn.

## Khi mở phiên mới
Đọc theo thứ tự: `PROJECT.md` → `SPEC.md` → `ARCHITECTURE.md` → `IMPLEMENTATION_PLAN.md` → `memory.md`. Không đọc toàn bộ source code chỉ để bắt đầu — chỉ đọc khi cần thực hiện nhiệm vụ cụ thể.
