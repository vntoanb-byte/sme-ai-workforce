import { api, qs } from './client'
import type { DocumentDetail, DocumentRow, InvoiceData, Page } from './types'

export interface DocFilters {
  status?: string
  q?: string
  page?: number
  page_size?: number
}

export const listDocuments = (f: DocFilters) => {
  // Backend dùng limit/offset (không phải page/page_size) — quy đổi ở đây để
  // features/ không cần biết chi tiết. `q` tìm theo số hoá đơn, đơn vị bán, tên tệp.
  const pageSize = f.page_size ?? 20
  const page = f.page ?? 1
  return api.get<Page<DocumentRow>>(
    '/documents' + qs({ status: f.status, q: f.q, limit: pageSize, offset: (page - 1) * pageSize }),
  )
}

export const getDocument = (id: number) => api.get<DocumentDetail>(`/documents/${id}`)

/**
 * Lưu bản người dùng đã kiểm tra: không đổi gì = xác nhận, có sửa = tạo bản
 * trích xuất mới. Backend ghi người xác nhận + giá trị trước/sau vào nhật ký
 * kiểm toán; chứng từ cuối cùng của một lần chạy được duyệt thì lần chạy tự
 * chạy tiếp các bước còn lại.
 */
export const patchExtraction = (id: number, data: InvoiceData) =>
  api.patch<DocumentDetail>(`/documents/${id}`, { data })

/** Kiểm tra tệp (theo sha256) đã có trong kho chưa — chống trùng sớm trước khi tải lên. */
export const presignDocument = (sha256: string) =>
  api.post<{ exists: boolean }>('/documents/presign', { sha256 })

/** Tải tệp thật lên (multipart) — backend trích xuất + chạy QC đồng bộ, trả về chi tiết đầy đủ. */
export const uploadDocument = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<DocumentDetail>('/documents', form)
}

/** Xử lý chứng từ trong hàng chờ xác nhận: chấp nhận / sửa / từ chối. */
export const resolveReview = (
  id: number,
  action: 'approve' | 'correct' | 'reject',
  data?: InvoiceData,
  note?: string,
) => api.post<{ id: number; status: string }>(`/reviews/${id}/resolve`, { action, data, note })
