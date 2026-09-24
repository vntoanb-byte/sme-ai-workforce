/**
 * Lớp gọi API.
 *
 * Có một công tắc duy nhất: biến môi trường VITE_USE_MOCK.
 *   true  → mọi lời gọi được phục vụ bởi src/api/mock/handlers.ts (không cần backend)
 *   false → gọi thật tới /api/v1 (dev: qua proxy của Vite)
 * Không đặt: `npm run dev` dùng dữ liệu giả, còn bản build (`npm run build`, ảnh
 * Docker) LUÔN gọi backend thật — trước đây bản build cũng mặc định dữ liệu giả,
 * khiến bản triển khai không bao giờ chạm tới backend (lỗi thật phát hiện khi E2E).
 *
 * Nhờ công tắc này, toàn bộ thư mục features/ không biết backend đã tồn tại hay chưa.
 */
import { mockRequest } from './mock/handlers'

const MOCK_FLAG = import.meta.env.VITE_USE_MOCK
export const USE_MOCK = MOCK_FLAG === 'true' || (import.meta.env.DEV && MOCK_FLAG !== 'false')

const BASE = '/api/v1'

/** Lỗi chuẩn hoá — mọi màn hình bắt kiểu này. */
export class ApiError extends Error {
  code: string
  details?: unknown[]
  traceId?: string
  status: number

  constructor(status: number, code: string, message: string, details?: unknown[], traceId?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.traceId = traceId
  }
}

// ─── Lưu token trong bộ nhớ phiên, KHÔNG dùng localStorage ───
let accessToken: string | null = null
export function setAccessToken(t: string | null) { accessToken = t }
export function getAccessToken() { return accessToken }

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

async function send(method: Method, path: string, body?: unknown): Promise<Response> {
  return fetch(BASE + path, {
    method,
    headers: {
      ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    credentials: 'include',
  })
}

/**
 * Mã truy cập sống ngắn (15 phút). Hết hạn giữa phiên thì đổi cookie làm mới
 * (HttpOnly) lấy mã mới rồi gửi lại yêu cầu — người dùng không bị đăng xuất.
 * Dùng chung một lời gọi làm mới cho các yêu cầu đồng thời.
 */
let refreshing: Promise<boolean> | null = null
function refreshAccessToken(): Promise<boolean> {
  refreshing ??= fetch(BASE + '/auth/refresh', { method: 'POST', credentials: 'include' })
    .then(async (res) => {
      if (!res.ok) return false
      const json = (await res.json()) as { access_token: string }
      setAccessToken(json.access_token)
      return true
    })
    .catch(() => false)
    .finally(() => { refreshing = null })
  return refreshing
}

async function toError(res: Response): Promise<ApiError> {
  const text = await res.text()
  let json: unknown = null
  try { json = text ? JSON.parse(text) : null } catch { json = null }
  const e = (json as { error?: { code: string; message: string; details?: unknown[]; trace_id?: string } } | null)?.error
  return new ApiError(
    res.status,
    e?.code ?? 'UNKNOWN',
    e?.message ?? 'Hệ thống gặp sự cố không xác định. Vui lòng thử lại.',
    e?.details,
    e?.trace_id,
  )
}

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  if (USE_MOCK) {
    return mockRequest<T>(method, path, body)
  }

  let res = await send(method, path, body)
  if (res.status === 401 && !path.startsWith('/auth/') && (await refreshAccessToken())) {
    res = await send(method, path, body)
  }

  if (res.status === 204) return undefined as T
  if (!res.ok) throw await toError(res)
  const text = await res.text()
  return (text ? JSON.parse(text) : null) as T
}

/**
 * Tải tệp có xác thực (báo cáo, tệp kết quả lần chạy) rồi mở hộp thoại lưu.
 * Không dùng <a href> trực tiếp để luôn kèm mã truy cập mới nhất.
 */
export async function downloadFile(url: string, filename: string): Promise<void> {
  if (USE_MOCK) {
    throw new ApiError(501, 'MOCK', 'Chế độ dữ liệu giả không có tệp để tải về.')
  }
  const path = url.startsWith(BASE) ? url.slice(BASE.length) : url
  let res = await send('GET', path)
  if (res.status === 401 && (await refreshAccessToken())) res = await send('GET', path)
  if (!res.ok) throw await toError(res)
  const blobUrl = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
}

export const api = {
  get:   <T>(p: string) => request<T>('GET', p),
  post:  <T>(p: string, b?: unknown) => request<T>('POST', p, b),
  put:   <T>(p: string, b?: unknown) => request<T>('PUT', p, b),
  patch: <T>(p: string, b?: unknown) => request<T>('PATCH', p, b),
  del:   <T>(p: string) => request<T>('DELETE', p),
}

/** Ghép query string, bỏ qua giá trị rỗng. */
export function qs(params: Record<string, string | number | undefined | null>): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}
