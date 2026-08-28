---
description: Giao thức phối hợp giữa Claude Code (Architect/Manager/Reviewer) và Implementer (Cline hoặc subagent)
---

# Collaboration Rules

## Claude Code (Architect/Manager/Reviewer)
```
PLAN → ASSIGN → REVIEW
```
Không tự code hết rồi tự review — mất tác dụng kiểm soát chéo.

## Implementer — Cline hoặc subagent (Worker)
```
IMPLEMENT → TEST → REPORT
```
Không tự đoán yêu cầu rồi code rồi tự tuyên bố DONE.

## Mẫu giao task cho Implementer

```
TASK-<id>

Goal:
<mục tiêu cụ thể, 1-2 câu>

Allowed files:
<danh sách file/thư mục được phép sửa>

Requirements:
- <yêu cầu 1>
- <yêu cầu 2>

Must pass:
- <lệnh test/verify phải pass>

Do not:
- Thay đổi kiến trúc/database schema
- Sửa module không liên quan
- Thêm dependency lớn
- Đổi SPEC
- Deploy production
```

## Gọi Cline CLI trực tiếp từ Claude Code (xác nhận thật 2026-08-28)

Cline có CLI headless thật (`npm install -g cline`, gói `cline@3.0.60` lúc kiểm chứng, chạy được trên Windows qua Bash). Claude Code có thể tự gọi, không cần Owner copy/dán tay:

```bash
cline -P <provider-id> -c "<đường dẫn project>" "<prompt task>"
```

- `-P <provider-id>`: provider đã cấu hình sẵn trong `~/.cline/data/settings/providers.json` (vd. `cline`, `openai-compatible`, hoặc provider Owner tự thêm). Xem provider nào đang có bằng cách đọc **tên field** trong file đó — **KHÔNG BAO GIỜ in giá trị `apiKey`/`accessToken`/`refreshToken` ra output/log/chat**, kể cả khi Owner là chủ tài khoản; chỉ xác nhận sự tồn tại và tên provider.
- `-c <path>`: bắt buộc chỉ định đúng thư mục project — không để Cline chạy ở thư mục mặc định.
- Mặc định `--auto-approve true` — Cline sẽ tự làm không cần duyệt từng bước (không có TTY để duyệt tương tác trong pipeline này). **Vì vậy prompt phải scoped chặt** (dùng đúng mẫu "Khối giao task" bên dưới: Allowed files/Requirements/Do not) — đây là hàng rào an toàn duy nhất khi không có người duyệt từng thao tác.
- `cline config`/`cline auth` cần TTY thật (tương tác) — Claude Code **không** tự chạy được 2 lệnh này (Bash không có TTY). Nếu provider chưa cấu hình, phải nhờ Owner tự chạy `cline auth` một lần.
- Trước khi giao việc thật, nên **test kết nối bằng 1 prompt vô hại** trước (không đụng file, vd. "trả lời 1 câu, không đọc/sửa file nào") để chắc provider hoạt động, tránh phí lượt gọi vào việc thật nếu auth/API lỗi.
- Sau khi Cline chạy xong: **Claude Code vẫn phải tự review** — đọc diff file thật (`git diff` nếu project đã là git repo — nên `git init` trước khi giao việc ghi file cho Cline, để có safety net revert được), chạy lại `scripts/verify` thật. Không tin lời Cline tự báo "đã xong" (Claim Gate áp dụng y hệt như với Implementer là người).
- Chi phí: nếu provider dùng API key trả phí, mỗi lần gọi tốn tiền thật — đây là quyết định Owner (Owner Gate "Chi phí"), không tự ý chọn provider trả phí nếu chưa được xác nhận.

## ⚠️ Giới hạn thật đã kiểm chứng (không phải giả định)

- **Cline hooks không chạy trên Windows** (v3.36+, docs Cline chính thức xác nhận macOS/Linux only). Trên Windows, không dựa vào Cline hook để cưỡng chế — dùng Git pre-commit hook (cross-platform) + Claude Code tự chạy `scripts/verify` khi review.
- **Cline đọc `.clinerules/`, không đọc `.claude/rules/`** — 2 thư mục khác nhau. Muốn dùng chung luật: symlink `.clinerules` → `.claude/rules` (chạy `scripts/init-project.sh --link-cline`).
- Chưa xác nhận Cline có tự đọc `CLAUDE.md`/`AGENTS.md` không — tự kiểm tra trên project thật trước khi tin tưởng.
- **(Đã sửa 2026-08-28)** Dòng cũ ở đây từng nói "không có API tự động Claude giao việc cho Cline" — sai, đã kiểm chứng lại và thay bằng mục "Gọi Cline CLI trực tiếp" phía trên. `cline config`/`cline auth` vẫn cần TTY (đúng như giới hạn cũ), nhưng gọi task thật (`cline -P ... "prompt"`) thì không cần.
