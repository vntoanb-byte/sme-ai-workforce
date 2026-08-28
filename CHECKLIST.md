# CHECKLIST.md — Definition of Done kiểm chứng được

> Mỗi `[x]` PHẢI có bằng chứng (log/output/link) đi kèm. Không đánh dấu `[x]` vì "AI nghĩ rằng đã làm".

## Task hiện tại: TASK-002 — `domain/compiler.py`

- [x] Requirement satisfied — luồng classify_intent → extract_params → validate_spec, retry tối đa 3 lần, đúng ADR-002
- [x] SPEC satisfied — đối chiếu docstring gốc (nguồn cụ thể hơn SPEC.md cho file này)
- [x] Code implemented — `backend/app/domain/compiler.py` (Cline viết bản đầu, Claude sửa 1 bug thật khi review)
- [x] Unit tests passed — evidence: `pytest tests/unit/test_compiler.py tests/unit/test_validators.py -v` → `31 passed in 0.39s`
- [ ] Integration tests passed — không áp dụng (domain/ thuần, chưa nối LLM thật)
- [x] Build passed — `npm typecheck`/`npm build` PASS qua `scripts/verify`
- [x] Security checked — evidence: không đọc/in secret ra output (đã tự kiểm khi đọc `providers.json` để lấy tên provider); test không gọi mạng thật
- [x] No secrets committed — evidence: `scripts/verify` mục "Secret scan (diff)" → PASS
- [x] Architecture respected — evidence: `git diff --stat` xác nhận không đụng `schemas/workflow_spec.py`/`domain/validators.py`/`domain/qc_rules.py`/`domain/state.py`; không import từ `api/`/`adapters/`/`workers/`; `mypy`/`ruff` PASS
- [x] No forbidden changes — chỉ đổi `compiler.py` + `test_compiler.py` + `IMPLEMENTATION_PLAN.md`; không đổi `SPEC.md`/`ARCHITECTURE.md`
- [x] Documentation updated — `IMPLEMENTATION_PLAN.md` cập nhật đầy đủ evidence + bug đã sửa

**Bug tìm thấy khi review (đã sửa, không phải task riêng):** `compile()` trả `(None, [])` khi cả 3 lần đều lỗi cấu trúc Pydantic — đã thêm `SpecError(rule="COMPILE-2")` + test hồi quy.

**Lưu ý còn tồn:** `scripts/verify` toàn dự án vẫn FAIL vì lint debt có sẵn (task `task_b232c26f`, chưa chạy) — không liên quan TASK-002.
