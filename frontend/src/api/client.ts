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

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  if (USE_MOCK) return mockRequest<T>(method, path, body)

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
