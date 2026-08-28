# CHECKLIST.md — Definition of Done kiểm chứng được

> Mỗi `[x]` PHẢI có bằng chứng (log/output/link) đi kèm. Không đánh dấu `[x]` vì "AI nghĩ rằng đã làm".

## Task hiện tại: TASK-001 — `domain/validators.py` (V-1 → V-5)

- [x] Requirement satisfied — 5 phép V-1..V-5 đủ, đúng docstring gốc (không tự đổi thiết kế)
- [x] SPEC satisfied — SPEC.md chưa có acceptance criteria riêng cho validators; đối chiếu docstring gốc (nguồn sự thật cụ thể hơn cho file này)
- [x] Code implemented — `backend/app/domain/validators.py`
- [x] Unit tests passed — evidence: `pytest tests/unit/test_validators.py -v` → `17 passed in 0.27s` (dán đầy đủ trong `IMPLEMENTATION_PLAN.md` mục Completed)
- [ ] Integration tests passed — không áp dụng (domain/ thuần, không có integration test cho module này)
- [x] Build passed — evidence: `npm typecheck`/`npm build` (frontend) đều PASS qua `scripts/verify`; không có bước build riêng cho `validators.py`
- [x] Security checked — evidence: file không xử lý input người dùng chưa qua Pydantic validate, không I/O ngoài `os.path.isdir()` (đọc, không ghi); không phát hiện vấn đề
- [x] No secrets committed — evidence: không file `.env`/credential nào bị đổi trong task này
- [x] Architecture respected — evidence: không import từ `api/`/`adapters/`/`workers/` (kiểm tra bằng đọc lại import block của `validators.py`); `mypy`/`ruff` PASS
- [x] No forbidden changes — evidence: chỉ đổi 3 file (`validators.py`, `test_validators.py`, `pyproject.toml` — thêm 1 dòng `pythonpath`), không đổi `SPEC.md`/`ARCHITECTURE.md`/scope
- [x] Documentation updated — `IMPLEMENTATION_PLAN.md` cập nhật; docstring `validators.py` đã bỏ phần "Cần hiện thực" theo `AGENTS.md` Mục 5

**Lưu ý:** `scripts/verify` toàn dự án hiện FAIL vì lint debt có sẵn ở 6 file khác (không thuộc TASK-001) — xem `IMPLEMENTATION_PLAN.md`. Task riêng đã được tách (`task_b232c26f`).
