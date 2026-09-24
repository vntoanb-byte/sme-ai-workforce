/**
 * Bộ định tuyến giả — mô phỏng backend cho chế độ VITE_USE_MOCK=true.
 *
 * Mỗi nhánh ở đây tương ứng một điểm cuối trong tài liệu thiết kế (mục 4.9).
 * Khi hiện thực backend thật, đối chiếu tệp này để bảo đảm đường dẫn và
 * hình dạng dữ liệu trả về khớp nhau — làm vậy thì việc chuyển sang backend
 * thật chỉ là đổi một biến môi trường.
 */
import type {
  CompileResult, DocumentDetail, DocumentRow, Employee, Page, ReportPreview,
  RunDetail, RunRow, TokenPair, Workflow,
} from '../types'
import {
  MOCK_DOCS, MOCK_EMPLOYEES, MOCK_METRICS, MOCK_REPORT, MOCK_RUNS, MOCK_USERS,
  MOCK_WORKFLOW, mockDocDetail, mockRunDetail,
} from './data'

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** Bản sao có thể sửa — để thao tác của người dùng có tác dụng thật trong phiên. */
const docs: DocumentRow[] = [...MOCK_DOCS]
const employees: Employee[] = [...MOCK_EMPLOYEES]
const edited = new Map<number, DocumentDetail>()
const mockWorkflows = new Map<number, Workflow>()

function parse(path: string): { pathname: string; q: URLSearchParams } {
  const [pathname, search = ''] = path.split('?')
  return { pathname, q: new URLSearchParams(search) }
}

function paginate<T>(items: T[], q: URLSearchParams): Page<T> {
  const page = Number(q.get('page') ?? 1)
  const size = Number(q.get('page_size') ?? 20)
  return { items: items.slice((page - 1) * size, page * size), total: items.length, page, page_size: size }
}

export async function mockRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  await delay(140 + Math.random() * 160)
  const { pathname, q } = parse(path)
  const seg = pathname.split('/').filter(Boolean)
  const out = (v: unknown) => v as T

  // ─────────── Xác thực ───────────
  if (method === 'POST' && pathname === '/auth/login') {
    const { username, password } = body as { username: string; password: string }
    const rec = MOCK_USERS[username]
    if (!rec || rec.password !== password) {
      throw Object.assign(new Error('Tên đăng nhập hoặc mật khẩu không đúng.'), {
        name: 'ApiError', status: 401, code: 'INVALID_CREDENTIALS',
      })
    }
    return out({ access_token: 'mock-token', refresh_token: 'mock-refresh', user: rec.user } satisfies TokenPair)
  }

  if (method === 'POST' && (pathname === '/auth/logout' || pathname === '/auth/refresh')) {
    return out(undefined)
  }

  // ─────────── Quản trị ───────────
  if (method === 'GET' && pathname === '/admin/users') {
    return out(Object.values(MOCK_USERS).map((u) => u.user))
  }
  if (method === 'POST' && pathname === '/admin/llm/test') {
    return out({ ok: true, model: 'Qwen3-VL-8B', base_url: 'http://vllm:8000/v1', latency_ms: 840, error: null })
  }
  if (method === 'POST' && pathname === '/reports/export') {
    return out({ artifact_id: 1, filename: 'BaoCao.xlsx', download_url: '/api/v1/reports/1/download' })
  }
  if (method === 'POST' && seg[0] === 'reviews' && seg[2] === 'resolve') {
    const { action } = body as { action: string }
    const row = docs.find((d) => d.id === Number(seg[1]))
    if (row) { row.status = action === 'reject' ? 'rejected' : 'ok'; row.qc_failed = 0 }
    return out({ id: Number(seg[1]), status: row?.status ?? 'ok' })
  }
  if (method === 'POST' && seg[0] === 'runs' && seg[2] === 'cancel') {
    return out({ ...MOCK_RUNS[0], status: 'CANCELLED' })
  }

  // ─────────── Chỉ số bảng điều khiển ───────────
  if (method === 'GET' && pathname === '/admin/metrics') return out(MOCK_METRICS)

  // ─────────── Nhân viên AI ───────────
  if (method === 'GET' && pathname === '/employees') {
    const status = q.get('status')
    const kw = (q.get('q') ?? '').toLowerCase()
    let rows = employees
    if (status) rows = rows.filter((e) => e.status === status)
    if (kw) rows = rows.filter((e) => e.name.toLowerCase().includes(kw))
    return out(paginate(rows, q))
  }
  if (method === 'GET' && seg[0] === 'employees' && seg[1] && !seg[2]) {
    const e = employees.find((x) => x.id === Number(seg[1]))
    if (!e) throw Object.assign(new Error('Không tìm thấy nhân viên AI.'), { name: 'ApiError', status: 404, code: 'NOT_FOUND' })
    return out(e)
  }
  if (method === 'PATCH' && seg[0] === 'employees' && seg[1]) {
    const e = employees.find((x) => x.id === Number(seg[1]))
    if (e) Object.assign(e, body as Partial<Employee>)
    return out(e)
  }

  // ─────────── Biên dịch mô tả công việc ───────────
  if (method === 'POST' && pathname === '/employees') {
    const { name, job_description } = body as { name: string; job_description: string }
    await delay(1600) // mô phỏng thời gian gọi mô hình
    const text = job_description.toLowerCase()
    // Mô phỏng bước phân loại ý định: không khớp mẫu nào thì từ chối rõ ràng
    const looksSupported = /hoá đơn|hóa đơn|excel|bảng tính|chứng từ|đối chiếu|báo cáo/.test(text)
    if (!looksSupported) {
      return out({
        ok: false,
        errors: [{
          rule: 'V-0', step_key: null,
          message: 'Hệ thống chưa hiểu được yêu cầu này. Hiện tại hệ thống xử lý được: đọc hoá đơn, nhập vào Excel, làm sạch bảng tính, đối chiếu hai tệp, và lập báo cáo định kỳ.',
        }],
      } satisfies CompileResult)
    }
    if (/email|thư điện tử|gmail/.test(text)) {
      return out({
        ok: false,
        errors: [{
          rule: 'V-1', step_key: 'read_email',
          message: 'Hệ thống chưa có công cụ đọc thư điện tử. Bạn có thể đổi thành đọc tệp trong một thư mục trên máy chủ.',
        }],
      } satisfies CompileResult)
    }
    const wf: Workflow = { ...MOCK_WORKFLOW, id: 900 + employees.length, employee_id: 900 + employees.length, status: 'pending', version: 1, approved_at: null }
    mockWorkflows.set(wf.id, wf)
    const emp: Employee = {
      id: 900 + employees.length, name, job_description, status: 'draft',
      schedule_label: 'Mỗi ngày 08:00', next_run_at: null, last_run_at: null,
      last_run_status: null, runs_30d: 0, created_at: new Date().toISOString(),
      workflow_id: wf.id,
    }
    employees.unshift(emp)
    return out({ ok: true, workflow: wf } satisfies CompileResult)
  }

  // ─────────── Quy trình ───────────
  if (method === 'GET' && seg[0] === 'workflows' && seg[1]) {
    return out(mockWorkflows.get(Number(seg[1])) ?? { ...MOCK_WORKFLOW, id: Number(seg[1]) })
  }
  if (method === 'POST' && seg[0] === 'workflows' && seg[2] === 'approve') {
    const e = employees.find((x) => x.id === Number(q.get('employee_id') ?? 0)) ?? employees[0]
    if (e) e.status = 'active'
    const approved: Workflow = { ...(mockWorkflows.get(Number(seg[1])) ?? MOCK_WORKFLOW), status: 'approved', approved_at: new Date().toISOString() }
    mockWorkflows.set(approved.id, approved)
    return out(approved)
  }

  // ─────────── Chứng từ ───────────
  if (method === 'GET' && pathname === '/documents') {
    const status = q.get('status')
    const kw = (q.get('q') ?? '').toLowerCase()
    let rows = docs
    if (status) rows = rows.filter((d) => d.status === status)
    if (kw) {
      rows = rows.filter(
        (d) => (d.invoice_no ?? '').includes(kw) || (d.seller_name ?? '').toLowerCase().includes(kw),
      )
    }
    return out(paginate(rows, q))
  }
  if (method === 'GET' && seg[0] === 'documents' && seg[1] && !seg[2]) {
    const id = Number(seg[1])
    return out(edited.get(id) ?? mockDocDetail(id))
  }
  if (method === 'PATCH' && seg[0] === 'documents' && seg[1]) {
    const id = Number(seg[1])
    const current = edited.get(id) ?? mockDocDetail(id)
    const patched: DocumentDetail = {
      ...current,
      status: 'ok',
      qc: current.qc.map((r) => ({ ...r, passed: true })),
      ...(body as Partial<DocumentDetail>),
    }
    edited.set(id, patched)
    const row = docs.find((d) => d.id === id)
    if (row) { row.status = 'ok'; row.qc_failed = 0 }
    return out(patched)
  }
  if (method === 'POST' && pathname === '/documents') {
    const f = body as { filename: string }
    const row: DocumentRow = {
      id: 2000 + docs.length, filename: f.filename,
      source_kind: f.filename.toLowerCase().endsWith('.pdf') ? 'pdf' : 'image',
      status: 'processing', invoice_no: null, issue_date: null, seller_name: null,
      total: null, qc_failed: 0, created_at: new Date().toISOString(),
    }
    docs.unshift(row)
    return out(row)
  }

  // ─────────── Lần chạy ───────────
  if (method === 'GET' && pathname === '/runs') {
    const status = q.get('status')
    const empId = q.get('employee_id')
    let rows: RunRow[] = MOCK_RUNS
    if (status) rows = rows.filter((r) => r.status === status)
    if (empId) rows = rows.filter((r) => r.employee_id === Number(empId))
    return out(paginate(rows, q))
  }
  if (method === 'GET' && seg[0] === 'runs' && seg[1] && !seg[2]) {
    return out(mockRunDetail(Number(seg[1])) satisfies RunDetail)
  }
  if (method === 'POST' && pathname === '/runs') {
    return out({ id: 1285 })
  }

  // ─────────── Báo cáo ───────────
  if (method === 'POST' && pathname === '/reports/preview') {
    return out(MOCK_REPORT satisfies ReportPreview)
  }

  throw Object.assign(new Error(`Chưa mô phỏng điểm cuối: ${method} ${pathname}`), {
    name: 'ApiError', status: 501, code: 'NOT_IMPLEMENTED',
  })
}
