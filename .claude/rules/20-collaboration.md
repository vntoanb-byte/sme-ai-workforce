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

### Luôn mở trực tiếp cho Owner xem — KHÔNG chạy nền âm thầm (bắt buộc, 2026-08-28)

Owner yêu cầu rõ: mọi lần gọi `cline` cho việc thật (không phải câu test vô hại) phải cho Owner **nhìn thấy trực tiếp**, không được chỉ chạy ngầm rồi báo kết quả sau. Trước khi (hoặc ngay sau khi) chạy lệnh `cline` ở chế độ nền, luôn mở thêm 2 cửa sổ:

```bash
# 1. Mở VS Code vào đúng thư mục project — Owner thấy file thay đổi trực tiếp
code "<đường dẫn project>"
```

```powershell
# 2. Mở một cửa sổ terminal MỚI, tail trực tiếp output của tiến trình cline đang chạy nền.
# <output-file-path> lấy từ chính kết quả trả về của lệnh chạy nền (Bash/PowerShell tool
# báo đường dẫn file log khi chạy với run_in_background) — không đoán đường dẫn, đọc từ
# kết quả thật của lệnh.
Start-Process powershell -ArgumentList @('-NoExit','-Command',"Get-Content -Path '<output-file-path>' -Wait -Tail 80")
```

Cửa sổ PowerShell này chỉ **đọc** log (`Get-Content -Wait`), không điều khiển hay can thiệp gì vào tiến trình — an toàn, Owner đóng lúc nào cũng được, không ảnh hưởng `cline` đang chạy. Đây là cách hợp lệ duy nhất để "cho Owner xem trực tiếp" mà không cần điều khiển chuột/bàn phím GUI (thứ Claude Code không có khả năng làm — xem Mục 6 SKILL.md).

### Bẫy codepage Windows — làm vỡ nội dung tiếng Việt (xác nhận thật 2026-08-28)

Trên máy Windows có codepage console mặc định KHÔNG phải UTF-8 (kiểm bằng lệnh
`chcp` — nếu không thấy `Active code page: 65001` thì đang bị bẫy này), khi
Cline đọc file có dấu tiếng Việt bằng lệnh shell (`Get-Content`/`cat`/`type`
qua tool chạy lệnh của nó thay vì tool đọc file gốc), nội dung bị vỡ encoding
(mojibake). Nếu Cline sau đó đưa nội dung vỡ vào request gửi lên model, có thể
gây lỗi thật dạng "request body rejected... malformed messages" từ provider.

**Bắt buộc khi task/project có nội dung tiếng Việt (hoặc ngôn ngữ có dấu
khác):** thêm vào `.clinerules` của project và/hoặc đầu mỗi prompt giao task —
*"Luôn dùng tool đọc file gốc (read_files) để đọc file .md/.py/text — KHÔNG
dùng Get-Content/cat/type qua run_commands cho việc đọc nội dung file. Chỉ
dùng run_commands cho lệnh thật sự cần chạy (test/lint/liệt kê thư mục)."*
Đã verify: sau khi thêm dòng này, task chạy lại thành công không còn lỗi.

### Task lớn/phức tạp: ghi khối task vào IMPLEMENTATION_PLAN.md TRƯỚC khi gọi cline (bài học 2026-08-28)

Với task đơn giản, truyền thẳng nội dung khối task làm đối số dòng lệnh
(`cline -P ... "TASK-<id>\n\nGoal:...`) là đủ. Nhưng với task LỚN/phức tạp
(nhiều file, cần đặc tả dài như lược đồ CSDL) — đã tự gặp lỗi thật: Cline
không tìm thấy khối task trong `IMPLEMENTATION_PLAN.md` (vì Claude chỉ truyền
qua prompt, không ghi vào file), tự lục lọi tìm kiếm, tốn phần lớn ngân sách
thời gian trước khi bắt đầu code thật, dẫn tới timeout.

**Với task lớn:** ghi khối task đầy đủ vào `IMPLEMENTATION_PLAN.md` (mục
`Status: ASSIGNED`, đúng mẫu ở trên) TRƯỚC, rồi mới gọi `cline` với prompt
NGẮN dạng "Đọc IMPLEMENTATION_PLAN.md, làm task đang ASSIGNED" — khớp đúng
hành vi `.clinerules` Mục 1 đã mô tả sẵn, tránh Cline phải tự đoán chỗ tìm.

## ⚠️ Giới hạn thật đã kiểm chứng (không phải giả định)

- **Cline hooks không chạy trên Windows** (v3.36+, docs Cline chính thức xác nhận macOS/Linux only). Trên Windows, không dựa vào Cline hook để cưỡng chế — dùng Git pre-commit hook (cross-platform) + Claude Code tự chạy `scripts/verify` khi review.
- **Cline đọc `.clinerules/`, không đọc `.claude/rules/`** — 2 thư mục khác nhau. Muốn dùng chung luật: symlink `.clinerules` → `.claude/rules` (chạy `scripts/init-project.sh --link-cline`).
- Chưa xác nhận Cline có tự đọc `CLAUDE.md`/`AGENTS.md` không — tự kiểm tra trên project thật trước khi tin tưởng.
- **(Đã sửa 2026-08-28)** Dòng cũ ở đây từng nói "không có API tự động Claude giao việc cho Cline" — sai, đã kiểm chứng lại và thay bằng mục "Gọi Cline CLI trực tiếp" phía trên. `cline config`/`cline auth` vẫn cần TTY (đúng như giới hạn cũ), nhưng gọi task thật (`cline -P ... "prompt"`) thì không cần.
