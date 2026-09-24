/**
 * Kiểu dữ liệu dùng chung giữa giao diện và backend.
 *
 * Viết tay, đối chiếu với lược đồ backend (backend/app/schemas/*, OpenAPI tại
 * /api/v1/openapi.json). Có thể sinh tự động bằng `npm run gen:api` nhưng khi
 * đó phải giữ nguyên tên kiểu để không phải sửa chỗ khác.
 */

// ─────────────────────────── Chung ───────────────────────────
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown[]; trace_id?: string }
}

// ─────────────────────────── Người dùng ───────────────────────────
export type RoleCode = 'USER' | 'MANAGER' | 'ADMIN'

export interface User {
  id: number
  username: string
  full_name: string
  email: string
  roles: RoleCode[]
  is_active: boolean
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  user: User
}

// ─────────────────────────── Nhân viên AI ───────────────────────────
export type EmployeeStatus = 'draft' | 'active' | 'paused' | 'archived'

export interface Employee {
  id: number
  name: string
  job_description: string
  status: EmployeeStatus
  schedule_label: string | null
  next_run_at: string | null
  last_run_at: string | null
  last_run_status: RunStatus | null
  runs_30d: number
  created_at: string
  /** Quy trình hiện hành (đã duyệt) hoặc bản nháp mới nhất — null nếu chưa có. */
  workflow_id: number | null
}

export type TemplateCode =
  | 'TPL_INVOICE_TO_EXCEL'
  | 'TPL_INVOICE_REPORT'
  | 'TPL_EXCEL_CLEAN'
  | 'TPL_EXCEL_RECONCILE'
  | 'TPL_DOC_CLASSIFY'

export interface WorkflowStep {
  step_key: string
  order_index: number
  tool_code: string
  label: string
  config: Record<string, string | number | boolean>
  branch?: 'pass' | 'fail'
  on_error?: 'stop' | 'skip' | 'retry'
  retry_max?: number
}

export interface Workflow {
  id: number
  employee_id: number
  version: number
  status: 'pending' | 'approved' | 'archived'
  template_code: TemplateCode
  name?: string
  description?: string | null
  trigger: {
    type: 'manual' | 'cron' | 'file_watch'
    label: string
    cron_expr?: string | null
    watch_path?: string | null
    timezone?: string | null
  }
  steps: WorkflowStep[]
  edges?: { from_key: string; to_key: string; condition: string | null }[]
  approved_at: string | null
}

/** Kết quả biên dịch mô tả công việc — có thể thành công hoặc kèm danh sách lỗi. */
export interface CompileResult {
  ok: boolean
  workflow?: Workflow
  errors?: { rule: string; step_key: string | null; message: string }[]
}

// ─────────────────────────── Chứng từ ───────────────────────────
export type DocStatus = 'processing' | 'ok' | 'needs_review' | 'rejected' | 'failed'

export interface DocumentRow {
  id: number
  filename: string
  source_kind: 'image' | 'pdf'
  status: DocStatus
  invoice_no: string | null
  issue_date: string | null
  seller_name: string | null
  total: number | null
  qc_failed: number
  created_at: string
}

export interface LineItem {
  line_no: number
  description: string
  unit: string
  quantity: number
  unit_price: number
  amount: number
}

export interface InvoiceData {
  invoice_no: string
  invoice_form: string | null
  issue_date: string
  currency: string
  seller: { name: string; tax_code: string; address: string | null }
  buyer: { name: string | null; tax_code: string | null }
  line_items: LineItem[]
  totals: { subtotal: number; vat_rate: number; vat_amount: number; total: number }
}

export interface QCResult {
  rule_code: string
  severity: 'warning' | 'critical'
  passed: boolean
  /** Trường nào bị ảnh hưởng — dùng để tô nền cảnh báo đúng ô trên biểu mẫu. */
  field: string | null
  message: string
}

export interface DocumentDetail extends DocumentRow {
  file_url: string
  schema_version: string
  model_name: string
  confidence: number | null
  latency_ms: number
  data: InvoiceData
  qc: QCResult[]
}

// ─────────────────────────── Lần chạy ───────────────────────────
export type RunStatus =
  | 'PENDING' | 'CLAIMED' | 'RUNNING' | 'RETRYING'
  | 'NEEDS_REVIEW' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'

export interface RunRow {
  id: number
  employee_id: number
  employee_name: string
  trigger_type: 'manual' | 'cron' | 'file_watch'
  status: RunStatus
  doc_count: number
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

export type StepStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'SKIPPED'

export interface RunStep {
  step_key: string
  label: string
  status: StepStatus
  detail: string | null
  duration_ms: number | null
}

export interface RunOutput {
  artifact_id: number
  filename: string | null
  step_key: string | null
  download_url: string
}

export interface RunDetail extends RunRow {
  steps: RunStep[]
  stats: { read: number; passed: number; needs_review: number; total_amount: number }
  /** Tệp kết quả (Excel, báo cáo...) các bước đã tạo ra trong lần chạy. */
  outputs?: RunOutput[]
}

export interface LogLine {
  id?: number
  ts: string
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR'
  message: string
}

// ─────────────────────────── Bảng điều khiển ───────────────────────────
export interface Metrics {
  period_label: string
  docs_processed: number
  docs_processed_delta: number
  hours_saved: number
  minutes_per_doc: number
  automation_rate: number
  automation_rate_delta: number
  needs_review_total: number
  needs_review_open: number
  llm_status: 'ok' | 'degraded' | 'down'
  runs_this_month?: number
  avg_llm_latency_ms?: number | null
  tokens_this_month?: number
}

export interface LlmTestResult {
  ok: boolean
  model: string
  base_url: string
  latency_ms: number
  error: string | null
}

// ─────────────────────────── Báo cáo ───────────────────────────
export interface ReportRow {
  group: string
  doc_count: number
  subtotal: number
  vat_amount: number
  total: number
}

export interface ReportPreview {
  from: string
  to: string
  group_by: 'seller' | 'month' | 'vat_rate'
  rows: ReportRow[]
  grand_total: number
}

export interface ExportResult {
  artifact_id: number
  filename: string
  download_url: string
}
