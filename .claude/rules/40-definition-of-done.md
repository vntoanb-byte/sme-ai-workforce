---
description: Definition of Done dựa trên bằng chứng — Claim Gate
---

# Definition of Done

Task chỉ được coi là DONE khi TẤT CẢ đều đúng:

- [ ] Requirement satisfied
- [ ] SPEC satisfied (đối chiếu `SPEC.md`)
- [ ] Code implemented
- [ ] Tests passed — **có evidence** (exit code/log thật)
- [ ] Build passed nếu cần — có evidence
- [ ] Security checked — có evidence
- [ ] No forbidden changes (đối chiếu `.claude/rules/00-safety.md`)
- [ ] Architecture respected (đối chiếu `ARCHITECTURE.md`)
- [ ] Documentation updated

Thiếu MỘT điều → **NOT DONE**. Không có ngoại lệ "gần xong" hay "chắc là ổn".

## Claim Gate

Không được viết các câu sau nếu không kèm bằng chứng cụ thể ngay sau đó:
- "Test passed" / "đã test thành công"
- "Backup completed" / "đã backup xong"
- "Deployment completed" / "đã deploy xong"
- "Security verified" / "đã kiểm tra bảo mật"

Bằng chứng hợp lệ = output/log thật của lệnh đã chạy, không phải mô tả bằng lời. Nếu không chạy được lệnh kiểm tra tương ứng, phải nói rõ "chưa kiểm tra được" thay vì suy đoán kết quả.
