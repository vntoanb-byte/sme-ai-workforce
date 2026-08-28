# AGENTS.md

> Nguyên tắc chung cho MỌI AI agent làm việc trên project này (Claude Code, Cline, hoặc AI khác) — để không AI nào tự có một bộ luật riêng.

## Nguyên tắc chung

## Không được tự ý (áp dụng cho mọi AI)
- Xoá dữ liệu quan trọng.
- Sửa `raw/` hoặc dữ liệu nguồn.
- Commit secret.
- Deploy production chưa được duyệt.
- Thao tác Git nguy hiểm (`reset --hard`, `push --force`, `clean -fd`) chưa được duyệt.
- Thay đổi scope/architecture/SPEC chưa được duyệt.
- Xoá test để làm test pass.
- Tuyên bố hoàn thành khi chưa có bằng chứng.

## Cline (Implementer) — phạm vi riêng
Xem mẫu giao task trong `.claude/rules/20-collaboration.md`.
