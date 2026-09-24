const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, LevelFormat,
  PageBreak, PageNumber, Paragraph, ShadingType, Table, TableCell, TableRow,
  TextRun, WidthType, Packer,
} = require('docx');
const fs = require('fs');
const path = require('path');

const OUT = path.resolve(__dirname, '..', 'docs', 'Bao_cao_danh_gia_SME_AI_Workforce.docx');
const BLUE = '17365D';
const SKY = 'DCEAF7';
const GREEN = 'E2F0D9';
const AMBER = 'FFF2CC';
const RED = 'FCE4D6';
const GRAY = 'F3F6F9';
const W = 9360;

function run(text, opts = {}) { return new TextRun({ text, font: 'Aptos', size: 22, ...opts }); }
function p(text, opts = {}) {
  const { bold, color, size, align, before, after, ...rest } = opts;
  return new Paragraph({
    alignment: align, spacing: { before, after: after ?? 120, line: 276 },
    children: [run(text, { bold, color, size })], ...rest,
  });
}
function bullet(text, level = 0) { return new Paragraph({ text, bullet: { level }, spacing: { after: 70, line: 276 } }); }
function cell(text, width, opts = {}) {
  const { header = false, shade, bold = header, color = header ? 'FFFFFF' : '1F2937', align } = opts;
  return new TableCell({ width: { size: width, type: WidthType.DXA }, shading: shade ? { type: ShadingType.CLEAR, color: shade } : undefined,
    verticalAlign: 'center', margins: { top: 95, bottom: 95, left: 110, right: 110 },
    children: [p(text, { bold, color, size: 18, align, after: 0 })] });
}
function table(headers, rows, widths) {
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths,
    borders: { top: { style: BorderStyle.SINGLE, color: 'B8C5D1', size: 4 }, bottom: { style: BorderStyle.SINGLE, color: 'B8C5D1', size: 4 }, left: { style: BorderStyle.SINGLE, color: 'B8C5D1', size: 4 }, right: { style: BorderStyle.SINGLE, color: 'B8C5D1', size: 4 }, insideHorizontal: { style: BorderStyle.SINGLE, color: 'D7E0E8', size: 2 }, insideVertical: { style: BorderStyle.SINGLE, color: 'D7E0E8', size: 2 } },
    rows: [new TableRow({ children: headers.map((x, i) => cell(x, widths[i], { header: true, shade: BLUE })) }), ...rows.map((row, r) => new TableRow({ children: row.map((x, i) => cell(x, widths[i], { shade: r % 2 ? GRAY : undefined })) }))] });
}
function flow(label, shade = SKY) { return new TableCell({ width: { size: W, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, color: shade }, margins: { top: 130, bottom: 130, left: 160, right: 160 }, children: [p(label, { bold: true, align: AlignmentType.CENTER, color: BLUE, after: 0 })] }); }
function arrow() { return p('↓', { bold: true, align: AlignmentType.CENTER, color: BLUE, size: 30, before: 0, after: 0 }); }
function flowRow(label, shade) { return [new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [flow(label, shade) ] })] }), arrow()]; }

const children = [];
children.push(
  new Paragraph({ spacing: { before: 1650, after: 220 }, alignment: AlignmentType.CENTER, children: [run('BÁO CÁO RÀ SOÁT ĐỒ ÁN TỐT NGHIỆP', { bold: true, color: BLUE, size: 32 })] }),
  new Paragraph({ spacing: { before: 220, after: 200 }, alignment: AlignmentType.CENTER, children: [run('SME AI WORKFORCE', { bold: true, color: '0F766E', size: 44 })] }),
  new Paragraph({ spacing: { before: 220, after: 900 }, alignment: AlignmentType.CENTER, children: [run('Nền tảng xử lý hoá đơn offline cho doanh nghiệp nhỏ và vừa', { color: '374151', size: 24 })] }),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [cell('Mục đích: Tổng hợp hiện trạng mã nguồn, kiến trúc, luồng nghiệp vụ, lựa chọn mô hình AI và các hạng mục cần hoàn thiện trước khi bảo vệ hội đồng.\n\nPhạm vi đánh giá: repository SME AI Workforce tại thời điểm rà soát. Đây là bản nháp để trao đổi với giảng viên hướng dẫn.', W, { shade: SKY, color: '1F2937' })] })] }),
  p('Ngày lập: 23/09/2026', { align: AlignmentType.CENTER, color: '6B7280', before: 850, after: 0 }),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ text: 'Mục lục', heading: HeadingLevel.HEADING_1 }),
  p('1. Tóm tắt điều hành\n2. Bài toán và phạm vi\n3. Hiện trạng hệ thống\n4. Kiến trúc và lưu đồ\n5. Lựa chọn mô hình AI\n6. Kế hoạch đánh giá thực nghiệm\n7. Đánh giá dưới góc nhìn hội đồng\n8. Lộ trình hoàn thiện\n9. Kịch bản demo và kết luận', { after: 350 }),
  p('Ghi chú về bằng chứng: kết luận “đã có” chỉ áp dụng cho phần đã hiện thực hoặc đã có test; phần giao diện mock và file stub được ghi rõ để tránh tuyên bố vượt quá hiện trạng.', { color: '7C2D12', size: 19, after: 0 }),
);

children.push(new Paragraph({ children: [new PageBreak()] }), new Paragraph({ text: '1. Tóm tắt điều hành', heading: HeadingLevel.HEADING_1 }));
children.push(p('Đề tài hướng tới tự động hoá xử lý hoá đơn cho SME Việt Nam trong bối cảnh dữ liệu kế toán nhạy cảm và doanh nghiệp không có đội ngũ hạ tầng phức tạp. Hệ thống nhận ảnh/PDF hoá đơn, trích xuất dữ liệu bằng mô hình thị giác-ngôn ngữ, áp dụng kiểm tra chất lượng tất định và chuyển trường hợp rủi ro cho người dùng xác nhận.'));
children.push(new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [cell('KẾT LUẬN CHÍNH\nĐề tài có nền tảng kiến trúc và phần xử lý chứng từ đủ tốt để phát triển thành đồ án mạnh. Để bảo vệ an toàn, cần chốt scope là “trợ lý AI xử lý hoá đơn offline có QC và human-in-the-loop”, hoàn thành một luồng end-to-end thật, và chứng minh chất lượng qua dữ liệu gán nhãn.', W, { shade: GREEN, bold: true, color: '1F5130' })] })] }));
children.push(table(['Nội dung', 'Nhận định'], [
  ['Điểm mạnh', 'Offline-first; tách lớp Ports & Adapters; dữ liệu tiền tệ Decimal; QC 8 quy tắc; cơ chế người duyệt; có Docker/vLLM.'],
  ['Trạng thái khả dụng', 'Luồng upload → trích xuất → QC đã hiện thực; backend có 94 test chạy xanh trong lần rà soát.'],
  ['Rủi ro chính', 'Workflow/scheduler/report/review/auth chưa hoàn thiện; thiếu benchmark hoá đơn thật có nhãn; nhiều màn frontend còn mock API.'],
], [2350, 7010]));

children.push(new Paragraph({ text: '2. Bài toán và phạm vi', heading: HeadingLevel.HEADING_1 }));
children.push(p('Đối tượng sử dụng là nhân viên kế toán/vận hành tại SME Việt Nam, xử lý số lượng chứng từ lặp lại nhưng thiếu nhân sự IT. Mục tiêu không phải thay thế hoàn toàn con người, mà giảm thao tác nhập liệu và tập trung con người vào hồ sơ bất thường.'));
children.push(table(['Yêu cầu', 'Cách đáp ứng trong thiết kế'], [
  ['Bảo mật dữ liệu', 'Triển khai nội bộ/offline; vLLM chạy mô hình cục bộ; file lưu local.'],
  ['Dữ liệu có cấu trúc', 'Model bắt buộc trả JSON theo InvoiceExtraction schema.'],
  ['Độ tin cậy', '8 kiểm tra QC về tổng tiền, VAT, MST, ngày, trùng số hóa đơn, trường bắt buộc và thành tiền dòng.'],
  ['Khả năng vận hành', 'SQLite WAL + hàng đợi bảng dữ liệu phù hợp tải 300–500 chứng từ/tháng.'],
], [2350, 7010]));

children.push(new Paragraph({ text: '3. Hiện trạng hệ thống', heading: HeadingLevel.HEADING_1 }));
children.push(table(['Thành phần', 'Hiện trạng', 'Ghi chú'], [
  ['Frontend React', 'Có UI đầy đủ', 'Documents đã nối API thật; nhiều module còn mock.'],
  ['Document pipeline', 'Đã hiện thực', 'Ảnh/PDF trang đầu → VLM → schema → QC → DB.'],
  ['CSDL & storage', 'Đã hiện thực', 'SQLite, ORM models, local file storage, dedup SHA-256.'],
  ['LLM adapter', 'Đã hiện thực', 'OpenAI-compatible/vLLM, JSON schema, circuit breaker.'],
  ['Workflow compiler', 'Lõi có, chưa tích hợp hoàn chỉnh', 'Thiết kế chọn template thay vì agent tự do.'],
  ['Scheduler/worker', 'Stub', 'Chưa vận hành luồng tự động thực tế.'],
  ['Review/export/report', 'Chưa hoàn thiện', 'Model dữ liệu có nhưng service/API cần hoàn tất.'],
  ['Đánh giá AI', 'Chưa đủ', 'Có script, nhưng ground truth chưa có dữ liệu.'],
], [1900, 2300, 5160]));

children.push(new Paragraph({ text: '4. Kiến trúc và lưu đồ', heading: HeadingLevel.HEADING_1 }));
children.push(p('Kiến trúc được tổ chức theo Ports & Adapters. Lõi nghiệp vụ không phụ thuộc trực tiếp vào vLLM, SQLite hay local filesystem; các adapter có thể thay thế khi triển khai quy mô lớn hơn. Đây là lập luận kỹ thuật quan trọng khi bảo vệ.'));
for (const [label, shade] of [
  ['Người dùng SME  →  React Web UI  →  FastAPI API', SKY],
  ['Document Service  →  Local File Storage + SQLite', GREEN],
  ['Document Service  →  Qwen3-VL qua vLLM  →  Invoice JSON', SKY],
  ['Invoice JSON  →  QC-01…QC-08  →  OK hoặc Needs Review', AMBER],
  ['Needs Review  →  Người dùng đối chiếu/xác nhận  →  Audit trail', RED],
]) children.push(...flowRow(label, shade));
children.push(p('Lưu đồ xử lý nghiệp vụ', { bold: true, color: BLUE, before: 150 }));
for (const [label, shade] of [
  ['1. Nạp ảnh/PDF hoá đơn và kiểm tra loại tệp', SKY],
  ['2. Lưu tệp, tạo mã SHA-256, chống nạp trùng', GREEN],
  ['3. Tiền xử lý ảnh / render trang đầu PDF', SKY],
  ['4. Qwen3-VL trích xuất JSON có ràng buộc schema', SKY],
  ['5. Kiểm tra dữ liệu bằng 8 quy tắc QC', AMBER],
  ['6a. Không có lỗi nghiêm trọng: lưu trạng thái OK', GREEN],
  ['6b. Có lỗi nghiêm trọng: Needs Review → người dùng quyết định', RED],
]) children.push(...flowRow(label, shade));

children.push(new Paragraph({ children: [new PageBreak()] }), new Paragraph({ text: '5. Lựa chọn mô hình AI', heading: HeadingLevel.HEADING_1 }));
children.push(p('Khuyến nghị cho bản bảo vệ: giữ Qwen3-VL 8B Instruct bản lượng tử AWQ 4-bit làm mô hình chính. Đây là lựa chọn cân bằng giữa khả năng đọc chứng từ, vận hành nội bộ và chi phí hạ tầng. Model không phải “nguồn chân lý”; tính đúng đắn được tăng cường bởi schema, luật QC và người duyệt.'));
children.push(table(['Tiêu chí', 'Qwen3-VL 8B AWQ', 'Lý do phù hợp'], [
  ['Đầu vào', 'Văn bản + ảnh', 'Đọc trực tiếp ảnh hóa đơn và trang PDF đã render.'],
  ['Vận hành', 'vLLM local', 'Hỗ trợ mục tiêu offline, không gửi dữ liệu ra ngoài.'],
  ['Đầu ra', 'JSON schema', 'Phù hợp InvoiceExtraction và giảm lỗi parse.'],
  ['Tài nguyên', '8B + AWQ 4-bit', 'Thực tế hơn mô hình lớn cho SME; cần đo VRAM/thời gian trên GPU thật.'],
  ['Khả năng thay thế', 'Qua LLMProvider', 'Có thể benchmark model khác mà không đổi domain logic.'],
], [1900, 2600, 4860]));
children.push(p('Thiết kế thử nghiệm model: so sánh Qwen3-VL 8B với một baseline OCR + parser hoặc một VLM nhỏ hơn; dùng cùng tập test, cùng schema và cùng quy tắc QC. Báo cáo không nên khẳng định “model tốt nhất”, mà kết luận model được chọn phù hợp nhất với ràng buộc offline, độ trễ và độ chính xác đo được.', { color: '374151' }));

children.push(new Paragraph({ text: '6. Kế hoạch đánh giá thực nghiệm', heading: HeadingLevel.HEADING_1 }));
children.push(p('Đây là phần còn thiếu quan trọng nhất để đồ án có tính khoa học. Không sử dụng kết quả demo lẻ để kết luận chất lượng mô hình.'));
children.push(table(['Hạng mục', 'Thiết kế đề xuất', 'Chỉ số'], [
  ['Dataset', '100–200 hoá đơn đã ẩn thông tin nhạy cảm; đa dạng nhà cung cấp, chất lượng ảnh, VAT, nhiều dòng hàng.', 'Số mẫu, phân bố loại hóa đơn.'],
  ['Ground truth', 'Gán nhãn thủ công 2 vòng; bất đồng được đối chiếu và chốt bởi người có nghiệp vụ.', 'Tỷ lệ đồng thuận / số nhãn đã kiểm.'],
  ['Accuracy', 'So sánh từng trường với nhãn chuẩn.', 'Field accuracy; document exact-match.'],
  ['QC hiệu quả', 'Tạo hoặc thu thập ca sai tổng tiền, MST, VAT, trùng số.', 'Precision/recall của QC; tỷ lệ false alarm.'],
  ['Hiệu năng', 'Đo 3 lần/mẫu trên đúng GPU triển khai.', 'Latency p50/p95; lỗi timeout; throughput.'],
], [1700, 4800, 2860]));

children.push(new Paragraph({ text: '7. Đánh giá dưới góc nhìn hội đồng', heading: HeadingLevel.HEADING_1 }));
children.push(table(['Mức độ', 'Thiếu sót', 'Cách xử lý trước bảo vệ'], [
  ['P0', 'Chưa có benchmark/ground truth để chứng minh KPI AI.', 'Tạo dataset có nhãn, chạy eval, đưa bảng và phân tích lỗi vào chương thực nghiệm.'],
  ['P0', 'JWT/RBAC chưa bảo vệ endpoint chứng từ.', 'Hoàn thiện auth tối thiểu và phân quyền người dùng/administrator; demo dữ liệu giả lập.'],
  ['P0', 'Luồng review và export chưa end-to-end thật.', 'Hoàn thiện approve/correct/reject, audit log, và xuất Excel; đây là lát cắt demo quan trọng.'],
  ['P1', 'Workflow, scheduler, worker, report còn stub.', 'Hoặc hiện thực 1 template chạy thật, hoặc thu hẹp scope và ghi trung thực là hướng phát triển.'],
  ['P1', 'Alembic migration chưa dùng thật.', 'Tạo migration initial và lệnh khởi động rõ ràng; bỏ phụ thuộc create_all khi hoàn thiện.'],
  ['P2', 'Code quality còn lint/mypy debt.', 'Sửa 38 lỗi ruff và 1 lỗi mypy; chạy lại full verification.'],
], [1000, 4050, 4310]));

children.push(new Paragraph({ text: '8. Lộ trình hoàn thiện đề xuất', heading: HeadingLevel.HEADING_1 }));
children.push(p('Mốc 1 — Hoàn thiện lát cắt nghiệp vụ: đăng nhập → upload → AI → QC → review/correct → audit → xuất Excel.', { bold: true, color: BLUE }));
children.push(p('Mốc 2 — Chứng minh thực nghiệm: dataset, baseline, benchmark, phân tích lỗi và latency.', { bold: true, color: BLUE }));
children.push(p('Mốc 3 — Hoàn thiện vận hành: migration, Docker end-to-end, logging, xử lý lỗi, clean lint/typecheck.', { bold: true, color: BLUE }));
children.push(p('Mốc 4 — Mở rộng “AI Workforce”: chỉ làm sau khi mốc 1–3 ổn; triển khai một workflow template có scheduler/worker chạy thật.', { bold: true, color: BLUE }));

children.push(new Paragraph({ text: '9. Kịch bản demo và kết luận', heading: HeadingLevel.HEADING_1 }));
children.push(table(['Tình huống demo', 'Điểm cần chứng minh'], [
  ['Hoá đơn hợp lệ', 'Trích xuất JSON đúng, QC pass, hiển thị kết quả và export Excel.'],
  ['Sai tổng tiền/VAT', 'QC phát hiện bất thường và không tự động chấp nhận.'],
  ['Trùng số hóa đơn', 'QC-06 phát hiện dữ liệu lặp.'],
  ['Ảnh mờ hoặc model lỗi', 'Hệ thống báo failed/needs_review có kiểm soát, không làm dữ liệu sai thành dữ liệu chính thức.'],
  ['Người dùng sửa', 'Lưu lại quyết định/audit, chứng minh human-in-the-loop.'],
], [2900, 6460]));
children.push(p('Kết luận: đề tài có tính ứng dụng rõ ràng và lựa chọn kiến trúc phù hợp đối tượng SME. Điều kiện để thuyết phục hội đồng không nằm ở việc gắn nhãn “agent” cho hệ thống, mà ở việc chứng minh được pipeline AI có kiểm soát: dữ liệu thật có nhãn, kết quả đo được, lỗi được chặn bằng QC, và người dùng có quyền quyết định cuối cùng.', { bold: true, color: BLUE, before: 250 }));
children.push(p('Nguồn tham khảo kỹ thuật: Qwen3-VL Technical Report (Qwen Team); vLLM Supported Models; vLLM Structured Outputs. Các thông số phần cứng cụ thể phải được đo lại trên GPU triển khai thực tế.', { size: 18, color: '6B7280', before: 450, after: 0 }));

const doc = new Document({
  creator: 'Codex', title: 'Báo cáo rà soát đồ án SME AI Workforce', subject: 'Đánh giá hiện trạng và lộ trình bảo vệ',
  styles: { default: { document: { run: { font: 'Aptos', size: 22 }, paragraph: { spacing: { line: 276 } } } }, paragraphStyles: [
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Aptos Display', bold: true, color: BLUE, size: 30 }, paragraph: { spacing: { before: 360, after: 170 }, outlineLevel: 0 } },
  ] },
  sections: [{ properties: { page: { margin: { top: 1000, right: 1080, bottom: 950, left: 1080 } } }, footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [run('SME AI Workforce  |  Báo cáo rà soát đồ án  |  Trang ', { size: 17, color: '6B7280' }), new TextRun({ children: [PageNumber.CURRENT], size: 17, color: '6B7280' })] })] }) }, children }],
});

fs.mkdirSync(path.dirname(OUT), { recursive: true });
Packer.toBuffer(doc).then((buffer) => { fs.writeFileSync(OUT, buffer); console.log(OUT); });
