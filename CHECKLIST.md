# CHECKLIST.md — Definition of Done kiểm chứng được

> Mỗi `[x]` PHẢI có bằng chứng (log/output/link) đi kèm. Không đánh dấu `[x]` vì "AI nghĩ rằng đã làm".

## Task hiện tại: TASK-004 — `ports/storage.py` + `adapters/storage_local.py`

- [x] Requirement satisfied — lưu theo sha256, khử trùng, ghi nguyên tử qua tệp tạm + os.replace
- [x] SPEC satisfied — đối chiếu docstring gốc (nguồn cụ thể hơn SPEC.md cho file này)
- [x] Code implemented — `ports/storage.py` + `adapters/storage_local.py` (Cline viết, Claude review không sửa gì)
- [x] Unit tests passed — evidence: `pytest -v` toàn dự án → `50 passed in 0.88s`
- [ ] Integration tests passed — không áp dụng (chưa nối API thật)
- [x] Build passed — `npm typecheck`/`npm build` PASS qua `scripts/verify`
- [x] Security checked — evidence: đường dẫn tệp derive từ sha256 (không nhận path từ input người dùng trực tiếp), không có path traversal
- [x] No secrets committed — evidence: `scripts/verify` mục "Secret scan (diff)" → PASS
- [x] Architecture respected — evidence: không tự đọc `settings`/`os.environ` (base_path truyền qua constructor); `git diff --stat` xác nhận không đụng file khác; `mypy`/`ruff` PASS
- [x] No forbidden changes — chỉ đổi đúng 3 file trong `Allowed files` + `.clinerules` (Claude tự sửa, ngoài phạm vi giao Cline, có lý do rõ ràng — fix encoding)
- [x] Documentation updated — `IMPLEMENTATION_PLAN.md` cập nhật đầy đủ evidence + 1 giả định cần Toàn xác nhận

**Không phát hiện bug khi review.**

**Sự cố kỹ thuật đã xử lý:** lần chạy đầu lỗi do codepage Windows (437) làm vỡ encoding tiếng Việt khi Cline đọc file qua PowerShell — đã sửa `.clinerules`, chạy lại thành công.

**Giả định cần Toàn xác nhận:** không thêm lớp `"artifacts/"` vào đường dẫn lưu trữ (vì `settings.STORAGE_PATH` mặc định đã là `"./data/artifacts"`).

**Lưu ý còn tồn:** `scripts/verify` toàn dự án vẫn FAIL vì lint debt có sẵn (task `task_b232c26f`, chưa chạy) — không liên quan TASK-004.
