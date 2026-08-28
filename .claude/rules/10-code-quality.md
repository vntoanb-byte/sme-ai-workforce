---
description: Chất lượng code — Simplicity First, không over-engineering
---

# Code Quality Rules

## Kiểm tra bắt buộc trước khi coi 1 thay đổi là xong
- Format
- Lint
- Type checking (nếu ngôn ngữ hỗ trợ)
- Unit test
- Integration test (nếu có)
- Build (nếu cần)
- Không thêm dependency mới mà chưa cần thiết rõ ràng

## Simplicity First
- Không over-engineering.
- Không tạo abstraction chỉ vì "có thể cần trong tương lai".
- Không tạo code duplicate không cần thiết — nhưng cũng không trừu tượng hoá quá sớm cho 1 lần dùng.
- Tôn trọng ranh giới module đã ghi trong `ARCHITECTURE.md` — không vượt qua vì "tiện".

## Naming & cấu trúc
- Đặt tên rõ nghĩa, nhất quán với convention đã có trong codebase.
- Không đổi convention hiện có chỉ vì cách khác "đẹp hơn" — xem `Surgical Changes` trong `20-collaboration.md`.
