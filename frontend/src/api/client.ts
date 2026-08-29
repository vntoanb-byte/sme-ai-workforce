/**
 * Lớp gọi API.
 *
 * Có một công tắc duy nhất: biến môi trường VITE_USE_MOCK.
 *   true  → mọi lời gọi được phục vụ bởi src/api/mock/handlers.ts (không cần backend)
 *   false → gọi thật tới /api/v1 qua proxy của Vite
 *
 * Nhờ công tắc này, toàn bộ thư mục features/ không biết backend đã tồn tại hay chưa.
 */
import { mockRequest } from './mock/handlers'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

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

// (2026-08-29, TASK-007) Backend thật MỚI CHỈ có router `documents` (8 router
// còn lại — auth, employees, workflows, runs, reviews, reports, tools, admin —
// vẫn là docstring stub, xem IMPLEMENTATION_PLAN.md). VITE_USE_MOCK=false là
// công tắc CHUNG cho toàn app, nhưng gọi thật vào route chưa tồn tại sẽ vỡ cả
// Dashboard/Employees/Runs/... — nên dùng DANH SÁCH CHO PHÉP: chỉ tiền tố nằm
// trong REAL_BACKEND_PATHS mới đi backend thật khi USE_MOCK=false, phần còn
// lại (kể cả /auth — backend thật chưa có JWT) vẫn đi mock. THÊM tiền tố vào
// đây khi router tương ứng được hiện thực xong ở backend, KHÔNG xoá cơ chế
// này cho tới khi đủ cả 8 router.
const REAL_BACKEND_PATHS = ['/documents']

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const canUseRealBackend = REAL_BACKEND_PATHS.some((p) => path === p || path.startsWith(p + '/') || path.startsWith(p + '?'))
  if (USE_MOCK || !canUseRealBackend) {
    return mockRequest<T>(method, path, body)
  }

  const res = await fetch(BASE + path, {
    method,
    headers: {
      ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    credentials: 'include',
  })

  if (res.status === 204) return undefined as T

  const text = await res.text()
  const json: unknown = text ? JSON.parse(text) : null

  if (!res.ok) {
    const e = (json as { error?: { code: string; message: string; details?: unknown[]; trace_id?: string } } | null)?.error
    throw new ApiError(
      res.status,
      e?.code ?? 'UNKNOWN',
      e?.message ?? 'Hệ thống gặp sự cố không xác định. Vui lòng thử lại.',
      e?.details,
      e?.trace_id,
    )
  }
  return json as T
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
