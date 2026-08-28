# SPEC.md

> Hợp đồng của sản phẩm. **Nếu yêu cầu chưa đủ rõ để xác định acceptance criteria thì không được bắt đầu code ngay** — hỏi Owner trước.
>
> **DRAFT 2026-08-28** — soạn từ `docs/`, docstring các file `api/v1/*.py`, `domain/qc_rules.py` (đã hiện thực) và context OS Brain. Các mục đánh dấu "(giả định — cần Toàn xác nhận)" là suy luận từ code stub, KHÔNG phải yêu cầu đã chốt với Owner theo đúng nghĩa AGENTS.md Mục 3 ("không giả định, hỏi trước") — Toàn cần xác nhận lại từng mục trước khi coi là spec cứng.

## Persona

Nhân viên kế toán/vận hành tại SME Việt Nam, không có nền tảng kỹ thuật sâu, không có đội IT hỗ trợ. Thao tác qua giao diện web (frontend), không chạm vào backend/CLI.

## User flow

1. **Tạo nhân viên AI** — người dùng mô tả công việc bằng tiếng Việt (vd. "đọc hoá đơn mua vào, kiểm tra rồi ghi vào Excel") → hệ thống biên dịch (`compiler_service` gọi LLM có ràng buộc schema) thành `WorkflowSpec` nháp, khớp với một trong các mẫu có sẵn (`domain/templates/`) → người dùng xem/sửa sơ đồ quy trình → phê duyệt (`approve`) → đăng ký lịch chạy.
2. **Nạp chứng từ** — người dùng tải ảnh/PDF hoá đơn lên (`POST /documents`, có chống trùng qua sha256 ở `/documents/presign`) → hệ thống trích xuất qua Qwen3-VL → chạy 8 quy tắc QC tự động → nếu tất cả pass: trạng thái xử lý xong; nếu có cảnh báo/nghiêm trọng: trạng thái `needs_review`.
3. **Xác nhận thủ công** — người dùng mở danh sách chứng từ lọc `status=needs_review` (không có màn hình riêng — ADR-003), xem chi tiết kèm kết quả QC, chọn `approve | correct | reject`.
4. **Chạy tự động theo lịch** — `workers/scheduler.py` (APScheduler) kích hoạt run theo lịch đã đăng ký; cũng có thể kích hoạt thủ công (`POST /runs`); xem tiến độ real-time qua SSE (`GET /runs/{id}/logs`).
5. **Xem báo cáo** — người dùng yêu cầu tổng hợp theo kỳ (`POST /reports/preview` xem trước, `POST /reports/export` xuất Excel/PDF, tải về qua `artifact_id`).

## Input

- Tệp ảnh/PDF hoá đơn (multipart upload), kiểm tra chữ ký nhị phân trước khi chấp nhận.
- Mô tả công việc bằng tiếng Việt (văn bản tự do) khi tạo nhân viên AI.
- Sửa tay trên `WorkflowSpec` (JSON có schema) khi người dùng chỉnh quy trình.
- Quyết định xác nhận thủ công: `{action: approve|correct|reject, data?}`.

## Output

- `InvoiceExtraction` (JSON theo `schemas/invoice.py`): `invoice_no, invoice_form, issue_date, currency, seller{name, tax_code, address}, buyer{name, tax_code}, line_items[{line_no, description, unit, quantity, unit_price, amount}], totals{subtotal, vat_rate, vat_amount, total}`.
- Danh sách `QCResult` cho mỗi chứng từ: `{rule_code, severity: warning|critical, passed, field, message}`.
- Báo cáo tổng hợp dạng Excel/PDF theo kỳ.
- Nhật ký thực thi (`run_logs`) — audit trail, không cho sửa/xoá.

## Business rules

**8 quy tắc QC** (`domain/qc_rules.py`, đã hiện thực và đối chiếu với `frontend/src/api/mock/data.ts`):

| Mã | Quy tắc |
|---|---|
| QC-01 | Tổng các dòng khớp `subtotal` |
| QC-02 | `subtotal + VAT = total` |
| QC-03 | Thuế suất VAT hợp lệ — chỉ nhận `{0, 5, 8, 10}%` |
| QC-04 | Mã số thuế bên bán hợp lệ theo chữ số kiểm tra (modulus-11, trọng số `[31,29,23,19,17,13,7,5,3]` trên 9 số đầu) |
| QC-05 | Ngày lập hợp lý — không quá `24` tháng trước hiện tại, không ở tương lai |
| QC-06 | Số hoá đơn không trùng với hoá đơn đã có trong hệ thống (`existing_invoice_numbers`) |
| QC-07 | Đủ trường bắt buộc: `invoice_no, issue_date, currency, seller.name, seller.tax_code` |
| QC-08 | Thành tiền mỗi dòng khớp `quantity × unit_price` |

Dung sai làm tròn tiền tệ: `1 đồng` (`TOLERANCE = Decimal("1")`).

**Quy tắc kiến trúc bắt buộc** (từ `AGENTS.md`/`README.md` — không được vi phạm):
1. `domain/` không import từ `api/`, `adapters/`, `workers/`.
2. Chỉ `core/config.py` đọc biến môi trường; nơi khác import `settings`.
3. Mọi thay đổi trạng thái đi qua `domain/state.py`, không gán trực tiếp cột DB.
4. Tiền tệ luôn `Decimal`, không bao giờ `float`.
5. Không sửa lược đồ DB tại chỗ — tăng `SCHEMA_VERSION`, tạo migration Alembic mới.
6. Frontend không chứa logic nghiệp vụ.

**Trạng thái run** (`domain/state.py`): `SUCCEEDED/FAILED/CANCELLED` là terminal — không transition tiếp; muốn chạy lại run đã FAILED phải tạo run mới (PENDING), không transition ngược.

**Agent:** CrewAI chỉ chạy `Process.sequential`, không tự suy luận lại kế hoạch (ADR-002); mỗi tác tử (Tài liệu/Dữ liệu/Kiểm soát) giới hạn phạm vi tool riêng.

## Acceptance criteria

(Theo `02 - Projects/sme-ai-workforce/PROJECT.md` Mục 6 — "Tiêu chí hoàn thành (QC Standard)")

- Tỷ lệ tự động: **≥ 90%** trường dữ liệu hoá đơn trích xuất đúng.
- Thời gian xử lý: **≤ 25 giây / hoá đơn**.
- 8/8 quy tắc QC chạy được và cho kết quả đúng trên dữ liệu kiểm thử.
- `GET /health` trả `{"ok": true}` với cả 3 check (database, storage, LLM connection) — **đã xác minh thật 2026-08-27**.

*(Chưa có acceptance criteria chi tiết cho từng user flow ở trên — vd. tỷ lệ đúng của bước biên dịch quy trình tiếng Việt, ngưỡng thời gian cho báo cáo. Cần Toàn bổ sung khi bắt đầu task tương ứng.)*

## Các trường hợp lỗi

- Tải lên tệp trùng (sha256 đã tồn tại) → `POST /documents/presign` báo đã tồn tại, chống trùng sớm trước khi upload thật.
- Kết nối LLM lỗi liên tiếp → circuit breaker mở sau **5 lỗi liên tiếp**, đóng thử lại sau **60 giây** (`adapters/llm_openai_compatible.py`, đã hiện thực).
- Chứng từ có cảnh báo/nghiêm trọng từ QC → chuyển `status=needs_review`, không tự động coi là hoàn thành.
- Run thất bại (`FAILED`) → không sửa lại run cũ, phải tạo run mới.
- `LLM_API_KEY` chưa cấu hình thật (còn placeholder) → lỗi `401` khi gọi model (đã xác minh thật khi test `test_llm.py`).
- *(Các trường hợp lỗi khác — vd. tệp không phải hoá đơn, ảnh quá mờ để trích xuất, hết dung lượng lưu trữ — chưa được đặc tả, cần Toàn bổ sung.)*
