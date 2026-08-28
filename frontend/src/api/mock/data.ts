/**
 * Dữ liệu giả cho chế độ phát triển giao diện (VITE_USE_MOCK=true).
 *
 * Mục đích: giao diện chạy được và demo được NGAY, không cần backend.
 * Khi backend sẵn sàng, đặt VITE_USE_MOCK=false — không phải sửa dòng nào
 * trong thư mục features/.
 *
 * Dữ liệu ở đây mô phỏng đúng nghiệp vụ thật: hoá đơn vật tư công nghiệp,
 * có cả bản đạt lẫn bản bị tầng kiểm soát chất lượng đánh dấu.
 */
import type {
  DocumentDetail, DocumentRow, Employee, InvoiceData, LogLine, Metrics,
  QCResult, ReportPreview, RunDetail, RunRow, User, Workflow,
} from '../types'

// ─────────────────────────── Người dùng ───────────────────────────
export const MOCK_USERS: Record<string, { password: string; user: User }> = {
  ketoan: {
    password: '123456',
    user: { id: 1, username: 'ketoan', full_name: 'Nguyễn Thị Hoa', email: 'hoa@anphat.vn', roles: ['USER'], is_active: true },
  },
  quanly: {
    password: '123456',
    user: { id: 2, username: 'quanly', full_name: 'Trần Thu Hương', email: 'huong@anphat.vn', roles: ['USER', 'MANAGER'], is_active: true },
  },
  admin: {
    password: '123456',
    user: { id: 3, username: 'admin', full_name: 'Quản trị hệ thống', email: 'admin@anphat.vn', roles: ['USER', 'MANAGER', 'ADMIN'], is_active: true },
  },
}

// ─────────────────────────── Thời gian tương đối ───────────────────────────
const now = new Date()
function at(dayOffset: number, h: number, m: number, s = 0): string {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + dayOffset, h, m, s)
  return d.toISOString()
}

// ─────────────────────────── Chỉ số bảng điều khiển ───────────────────────────
export const MOCK_METRICS: Metrics = {
  period_label: `Tháng ${now.getMonth() + 1}/${now.getFullYear()}`,
  docs_processed: 412,
  docs_processed_delta: 18,
  hours_saved: 28.4,
  minutes_per_doc: 4.1,
  automation_rate: 93.4,
  automation_rate_delta: 2.1,
  needs_review_total: 27,
  needs_review_open: 3,
  llm_status: 'ok',
}

// ─────────────────────────── Nhân viên AI ───────────────────────────
export const MOCK_EMPLOYEES: Employee[] = [
  {
    id: 1, name: 'Kế toán hoá đơn',
    job_description: 'Mỗi sáng 8 giờ, đọc các hoá đơn mới trong thư mục Scan trên máy chủ, nhập dữ liệu vào tệp SoHoaDon2026.xlsx, kiểm tra xem tổng tiền có khớp không, và gửi báo cáo tổng hợp cho chị Hương vào cuối ngày.',
    status: 'active', schedule_label: 'Mỗi ngày 08:00',
    next_run_at: at(1, 8, 0), last_run_at: at(0, 8, 0), last_run_status: 'RUNNING',
    runs_30d: 30, created_at: at(-45, 10, 12),
  },
  {
    id: 2, name: 'Báo cáo cuối ngày',
    job_description: 'Cuối mỗi ngày lúc 17h30, tổng hợp toàn bộ hoá đơn đã xử lý trong ngày, lập báo cáo Excel và PDF rồi gửi cho quản lý.',
    status: 'active', schedule_label: 'Mỗi ngày 17:30',
    next_run_at: at(0, 17, 30), last_run_at: at(-1, 17, 30), last_run_status: 'SUCCEEDED',
    runs_30d: 29, created_at: at(-40, 14, 5),
  },
  {
    id: 3, name: 'Đối chiếu công nợ',
    job_description: 'Mỗi thứ Hai lúc 9 giờ, đối chiếu tệp SoHoaDon2026.xlsx với tệp CongNo.xlsx theo số hoá đơn và liệt kê các dòng lệch.',
    status: 'paused', schedule_label: 'Thứ Hai 09:00',
    next_run_at: null, last_run_at: at(-3, 9, 0), last_run_status: 'FAILED',
    runs_30d: 4, created_at: at(-30, 9, 40),
  },
]

export const MOCK_WORKFLOW: Workflow = {
  id: 11, employee_id: 1, version: 3, status: 'approved',
  template_code: 'TPL_INVOICE_TO_EXCEL',
  trigger: { type: 'cron', label: 'Mỗi ngày lúc 08:00' },
  approved_at: at(-45, 10, 30),
  steps: [
    { step_key: 'scan_folder', order_index: 1, tool_code: 'fs.list_new_files', label: 'Lấy hoá đơn mới trong thư mục Scan', config: { path: '/mnt/scan', extensions: 'jpg,png,pdf' } },
    { step_key: 'read_invoice', order_index: 2, tool_code: 'vision.extract_invoice', label: 'Qwen3-VL đọc hoá đơn → dữ liệu có cấu trúc', config: { schema_version: 'invoice_v1', model: 'Qwen3-VL-8B', retry_max: 3 } },
    { step_key: 'check_data', order_index: 3, tool_code: 'qc.validate_invoice', label: 'Đối chiếu tổng tiền, thuế, mã số thuế', config: { tolerance: 1, rules: 'QC-01..QC-08' } },
    { step_key: 'write_excel', order_index: 4, tool_code: 'xlsx.append_rows', label: 'Ghi vào SoHoaDon2026.xlsx', config: { file: '/mnt/scan/SoHoaDon2026.xlsx', sheet: 'HoaDon' }, branch: 'pass' },
    { step_key: 'to_review', order_index: 4, tool_code: 'qc.escalate', label: 'Chuyển sang chờ người xác nhận', config: { assign_to: 'quanly' }, branch: 'fail' },
    { step_key: 'daily_report', order_index: 5, tool_code: 'report.build_xlsx', label: 'Lập báo cáo tổng hợp và gửi cho chị Hương', config: { at: '17:30', format: 'xlsx+pdf' } },
  ],
}

// ─────────────────────────── Hoá đơn ───────────────────────────
const INV_OK: InvoiceData = {
  invoice_no: '0004815', invoice_form: '1C26TAP', issue_date: '2026-08-20', currency: 'VND',
  seller: { name: 'Công ty TNHH Thiết bị Công nghiệp Minh Long', tax_code: '0309884172', address: '148 Lê Trọng Tấn, P. Tây Thạnh, Q. Tân Phú, TP.HCM' },
  buyer: { name: 'Công ty TNHH TM An Phát', tax_code: '0312445678' },
  line_items: [
    { line_no: 1, description: 'Vòng bi SKF 6205-2RS', unit: 'Cái', quantity: 40, unit_price: 185_000, amount: 7_400_000 },
    { line_no: 2, description: 'Dây curoa A-1250', unit: 'Sợi', quantity: 25, unit_price: 96_000, amount: 2_400_000 },
  ],
  totals: { subtotal: 9_800_000, vat_rate: 8, vat_amount: 784_000, total: 10_584_000 },
}

/** Bản ghi CÓ LỖI — dùng để trình diễn màn hình kiểm tra kết quả (P-06). */
const INV_BAD: InvoiceData = {
  invoice_no: '0004821', invoice_form: '1C26TAP', issue_date: '2026-08-22', currency: 'VND',
  seller: { name: 'Công ty TNHH Thiết bị Công nghiệp Minh Long', tax_code: '0309884I72', address: '148 Lê Trọng Tấn, P. Tây Thạnh, Q. Tân Phú, TP.HCM' },
  buyer: { name: 'Công ty TNHH TM An Phát', tax_code: '0312445678' },
  line_items: [
    { line_no: 1, description: 'Vòng bi SKF 6205-2RS', unit: 'Cái', quantity: 40, unit_price: 185_000, amount: 7_400_000 },
    { line_no: 2, description: 'Dây curoa A-1250', unit: 'Sợi', quantity: 25, unit_price: 96_000, amount: 2_400_000 },
    { line_no: 3, description: 'Mỡ bôi trơn Shell Gadus', unit: 'Hộp', quantity: 12, unit_price: 220_000, amount: 2_640_000 },
  ],
  totals: { subtotal: 12_440_000, vat_rate: 8, vat_amount: 995_200, total: 13_425_200 },
}

const QC_BAD: QCResult[] = [
  {
    rule_code: 'QC-04', severity: 'critical', passed: false, field: 'seller.tax_code',
    message: 'Mã số thuế phải gồm 10 chữ số. Ký tự thứ 9 đọc được là chữ I — nhiều khả năng là số 1.',
  },
  {
    rule_code: 'QC-02', severity: 'critical', passed: false, field: 'totals.total',
    message: '12.440.000 + 995.200 = 13.435.200, nhưng đọc được 13.425.200. Chênh lệch 10.000 đ.',
  },
  { rule_code: 'QC-01', severity: 'critical', passed: true, field: null, message: 'Tổng các dòng hàng khớp tiền trước thuế.' },
  { rule_code: 'QC-03', severity: 'critical', passed: true, field: null, message: 'Thuế suất 8% hợp lệ.' },
  { rule_code: 'QC-05', severity: 'warning', passed: true, field: null, message: 'Ngày lập nằm trong khoảng hợp lý.' },
  { rule_code: 'QC-08', severity: 'critical', passed: true, field: null, message: 'Đơn giá × số lượng khớp thành tiền ở cả 3 dòng.' },
]

const QC_OK: QCResult[] = [
  { rule_code: 'QC-01', severity: 'critical', passed: true, field: null, message: 'Tổng các dòng hàng khớp tiền trước thuế.' },
  { rule_code: 'QC-02', severity: 'critical', passed: true, field: null, message: 'Tiền trước thuế cộng thuế khớp tổng thanh toán.' },
  { rule_code: 'QC-03', severity: 'critical', passed: true, field: null, message: 'Thuế suất hợp lệ.' },
  { rule_code: 'QC-04', severity: 'critical', passed: true, field: null, message: 'Mã số thuế hợp lệ.' },
]

const SELLERS = [
  'Công ty TNHH Thiết bị Công nghiệp Minh Long',
  'Công ty CP Vật tư Kỹ thuật Đông Á',
  'Công ty TNHH TM DV Hoàng Gia',
  'Công ty CP Thiết bị Điện Tân Tiến',
  'Công ty TNHH Cơ khí Phú Thịnh',
]

function makeDocs(): DocumentRow[] {
  const rows: DocumentRow[] = []
  // Ba bản ghi đang chờ xác nhận — luôn nằm đầu danh sách
  rows.push({
    id: 1001, filename: 'IMG_20260824_0912.jpg', source_kind: 'image', status: 'needs_review',
    invoice_no: '0004821', issue_date: '2026-08-22', seller_name: SELLERS[0],
    total: 13_425_200, qc_failed: 2, created_at: at(0, 8, 2),
  })
  rows.push({
    id: 1002, filename: 'scan_0472.pdf', source_kind: 'pdf', status: 'needs_review',
    invoice_no: '0001188', issue_date: '2026-08-21', seller_name: SELLERS[1],
    total: 4_180_000, qc_failed: 1, created_at: at(0, 8, 5),
  })
  rows.push({
    id: 1003, filename: 'IMG_20260823_1740.jpg', source_kind: 'image', status: 'needs_review',
    invoice_no: null, issue_date: '2026-08-19', seller_name: SELLERS[2],
    total: null, qc_failed: 3, created_at: at(-1, 17, 41),
  })
  // Phần còn lại đã xử lý xong
  for (let i = 0; i < 37; i++) {
    const day = -Math.floor(i / 6)
    rows.push({
      id: 1100 + i,
      filename: i % 3 === 0 ? `scan_0${400 + i}.pdf` : `IMG_2026082${(i % 5) + 1}_${1000 + i}.jpg`,
      source_kind: i % 3 === 0 ? 'pdf' : 'image',
      status: 'ok',
      invoice_no: String(4800 - i).padStart(7, '0'),
      issue_date: `2026-08-${String(22 - (i % 12)).padStart(2, '0')}`,
      seller_name: SELLERS[i % SELLERS.length],
      total: 2_400_000 + ((i * 917_300) % 18_000_000),
      qc_failed: 0,
      created_at: at(day, 8, 10 + (i % 40)),
    })
  }
  return rows
}

export const MOCK_DOCS: DocumentRow[] = makeDocs()

export function mockDocDetail(id: number): DocumentDetail {
  const row = MOCK_DOCS.find((d) => d.id === id) ?? MOCK_DOCS[0]
  const bad = row.status === 'needs_review'
  const data = bad ? INV_BAD : { ...INV_OK, invoice_no: row.invoice_no ?? INV_OK.invoice_no }
  return {
    ...row,
    file_url: '',
    schema_version: 'invoice_v1',
    model_name: 'Qwen3-VL-8B',
    confidence: bad ? 0.71 : 0.97,
    latency_ms: 15_400 + (id % 7) * 800,
    data,
    qc: bad ? QC_BAD : QC_OK,
  }
}

// ─────────────────────────── Lần chạy ───────────────────────────
export const MOCK_RUNS: RunRow[] = [
  { id: 1284, employee_id: 1, employee_name: 'Kế toán hoá đơn', trigger_type: 'cron', status: 'RUNNING', doc_count: 23, started_at: at(0, 8, 0), finished_at: null, error_message: null },
  { id: 1283, employee_id: 1, employee_name: 'Kế toán hoá đơn', trigger_type: 'manual', status: 'NEEDS_REVIEW', doc_count: 1, started_at: at(0, 7, 14), finished_at: at(0, 7, 14, 38), error_message: null },
  { id: 1282, employee_id: 2, employee_name: 'Báo cáo cuối ngày', trigger_type: 'cron', status: 'SUCCEEDED', doc_count: 0, started_at: at(-1, 17, 30), finished_at: at(-1, 17, 31), error_message: null },
  { id: 1281, employee_id: 1, employee_name: 'Kế toán hoá đơn', trigger_type: 'cron', status: 'SUCCEEDED', doc_count: 19, started_at: at(-1, 8, 0), finished_at: at(-1, 8, 6), error_message: null },
  { id: 1280, employee_id: 3, employee_name: 'Đối chiếu công nợ', trigger_type: 'cron', status: 'FAILED', doc_count: 142, started_at: at(-3, 9, 0), finished_at: at(-3, 9, 2), error_message: 'Tệp CongNo.xlsx đang bị mở bởi người dùng khác' },
  { id: 1279, employee_id: 1, employee_name: 'Kế toán hoá đơn', trigger_type: 'cron', status: 'SUCCEEDED', doc_count: 26, started_at: at(-2, 8, 0), finished_at: at(-2, 8, 8), error_message: null },
  { id: 1278, employee_id: 2, employee_name: 'Báo cáo cuối ngày', trigger_type: 'cron', status: 'SUCCEEDED', doc_count: 0, started_at: at(-2, 17, 30), finished_at: at(-2, 17, 31), error_message: null },
  { id: 1277, employee_id: 1, employee_name: 'Kế toán hoá đơn', trigger_type: 'cron', status: 'SUCCEEDED', doc_count: 21, started_at: at(-3, 8, 0), finished_at: at(-3, 8, 7), error_message: null },
]

export function mockRunDetail(id: number): RunDetail {
  const row = MOCK_RUNS.find((r) => r.id === id) ?? MOCK_RUNS[0]
  const running = row.status === 'RUNNING'
  return {
    ...row,
    steps: [
      { step_key: 'scan_folder', label: 'Đọc thư mục Scan', status: 'SUCCEEDED', detail: `Tìm thấy ${row.doc_count} tệp mới`, duration_ms: 1200 },
      { step_key: 'read_invoice', label: 'AI đọc hoá đơn', status: running ? 'RUNNING' : 'SUCCEEDED', detail: running ? `Đang xử lý 14 / ${row.doc_count}` : `Đã đọc ${row.doc_count} hoá đơn`, duration_ms: running ? null : 248_000 },
      { step_key: 'check_data', label: 'Kiểm tra số liệu', status: running ? 'PENDING' : 'SUCCEEDED', detail: null, duration_ms: running ? null : 900 },
      { step_key: 'write_excel', label: 'Ghi vào SoHoaDon2026.xlsx', status: running ? 'PENDING' : 'SUCCEEDED', detail: null, duration_ms: running ? null : 2100 },
      { step_key: 'daily_report', label: 'Lập báo cáo cuối ngày', status: 'PENDING', detail: 'Đặt lịch 17:30', duration_ms: null },
    ],
    stats: running
      ? { read: 14, passed: 13, needs_review: 1, total_amount: 168_420_500 }
      : { read: row.doc_count, passed: row.doc_count, needs_review: 0, total_amount: 214_800_000 },
  }
}

/** Nhật ký mẫu — hook useSSE ở chế độ giả sẽ nhả dần từng dòng. */
export function mockLogLines(): LogLine[] {
  const L = (h: number, m: number, s: number, level: LogLine['level'], message: string): LogLine =>
    ({ ts: at(0, h, m, s), level, message })
  return [
    L(8, 0, 1, 'INFO', 'Bắt đầu lần chạy #1284 — nhân viên "Kế toán hoá đơn"'),
    L(8, 0, 2, 'INFO', '[bước 1] Quét thư mục /mnt/scan — tìm thấy 23 tệp mới'),
    L(8, 0, 3, 'INFO', '[bước 2] Bắt đầu đọc hoá đơn bằng Qwen3-VL 8B'),
    L(8, 0, 19, 'INFO', '[1/23] HD-0004815 · đọc xong 14,8s · 9 trường · kiểm tra ĐẠT'),
    L(8, 0, 35, 'INFO', '[2/23] HD-0004816 · đọc xong 15,2s · 9 trường · kiểm tra ĐẠT'),
    L(8, 0, 51, 'INFO', '[3/23] HD-0004817 · đọc xong 14,1s · 9 trường · kiểm tra ĐẠT'),
    L(8, 1, 8, 'INFO', '[4/23] HD-0004818 · đọc xong 16,3s · 9 trường · kiểm tra ĐẠT'),
    L(8, 1, 24, 'WARN', '[5/23] HD-0004819 · ảnh nghiêng 6,2° — đã tự động chỉnh'),
    L(8, 1, 41, 'INFO', '[5/23] HD-0004819 · đọc xong 17,0s · kiểm tra ĐẠT'),
    L(8, 1, 57, 'INFO', '[6/23] HD-0004820 · đọc xong 15,6s · kiểm tra ĐẠT'),
    L(8, 2, 14, 'WARN', '[7/23] HD-0004821 · QC-02 KHÔNG ĐẠT: tổng thanh toán lệch 10.000 đ'),
    L(8, 2, 14, 'WARN', '[7/23] HD-0004821 · QC-04 KHÔNG ĐẠT: mã số thuế chứa ký tự lạ'),
    L(8, 2, 15, 'INFO', '[7/23] Chuyển sang hàng đợi CHỜ XÁC NHẬN — đã báo chị Hương'),
    L(8, 2, 31, 'INFO', '[8/23] HD-0004822 · đọc xong 15,9s · kiểm tra ĐẠT'),
    L(8, 2, 47, 'INFO', '[9/23] HD-0004823 · đọc xong 14,7s · kiểm tra ĐẠT'),
    L(8, 3, 4, 'INFO', '[10/23] HD-0004824 · đọc xong 16,1s · kiểm tra ĐẠT'),
    L(8, 3, 20, 'INFO', '[11/23] HD-0004825 · đọc xong 15,3s · kiểm tra ĐẠT'),
    L(8, 3, 37, 'INFO', '[12/23] HD-0004826 · đọc xong 16,8s · kiểm tra ĐẠT'),
    L(8, 3, 54, 'INFO', '[13/23] HD-0004827 · đọc xong 15,1s · kiểm tra ĐẠT'),
    L(8, 4, 12, 'INFO', '[14/23] HD-0004828 · đọc xong 15,4s · kiểm tra ĐẠT'),
    L(8, 4, 28, 'INFO', '[15/23] HD-0004829 · đang xử lý…'),
  ]
}

// ─────────────────────────── Báo cáo ───────────────────────────
export const MOCK_REPORT: ReportPreview = {
  from: `2026-08-01`, to: `2026-08-31`, group_by: 'seller',
  rows: SELLERS.map((s, i) => {
    const subtotal = 18_400_000 + i * 7_310_000
    const vat = Math.round(subtotal * 0.08)
    return { group: s, doc_count: 12 + i * 7, subtotal, vat_amount: vat, total: subtotal + vat }
  }),
  grand_total: 0,
}
MOCK_REPORT.grand_total = MOCK_REPORT.rows.reduce((a, r) => a + r.total, 0)
