---
description: Luật an toàn — không được vi phạm bất kể ngữ cảnh
---

# Safety Rules

- Không xóa dữ liệu quan trọng.
- Không sửa `raw/` (nguồn gốc dữ liệu, bất biến).
- Không commit secret (API key, password, token, private key).
- Không đọc/ghi credential không cần thiết cho task hiện tại.
- Không deploy production nếu chưa được duyệt.
- Không chạy destructive command trên database (DROP, DELETE thiếu WHERE, TRUNCATE) nếu chưa được duyệt.
- Không tự ý thay đổi scope của task/project.
- Không tự ý refactor lớn ngoài phạm vi task.
- Không giả định kết quả test — phải chạy thật và đọc output thật.
- Không tuyên bố hoàn thành khi chưa có evidence (xem Claim Gate trong `controlled-ai-dev` SKILL.md Mục 4).
- Không xoá hoặc sửa test chỉ để làm test pass.
- Không thực hiện Git nguy hiểm (`reset --hard`, `push --force`, `clean -fd`) nếu chưa được duyệt.

Vi phạm bất kỳ điều nào ở trên → DỪNG → GIẢI THÍCH → ĐỀ XUẤT → CHỜ XÁC NHẬN của Owner.
