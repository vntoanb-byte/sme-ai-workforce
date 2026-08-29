import { api, qs } from './client'
import type { DocumentDetail, DocumentRow, InvoiceData, Page } from './types'

export interface DocFilters {
  status?: string
  q?: string
  page?: number
  page_size?: number
}

export const listDocuments = (f: DocFilters) => {
  // Backend (TASK-006, xem IMPLEMENTATION_PLAN.md) dùng limit/offset, KHÔNG
  // dùng page/page_size — quy đổi ở đây để features/ không cần biết chi tiết
  // API thật. `q` (tìm theo số hoá đơn/nhà cung cấp) CHƯA được backend hỗ trợ
  // — bỏ qua, không lỗi, chỉ chưa lọc được theo từ khoá.
  const pageSize = f.page_size ?? 20
  const page = f.page ?? 1
  return api.get<Page<DocumentRow>>(
    '/documents' + qs({ status: f.status, limit: pageSize, offset: (page - 1) * pageSize }),
  )
}

export const getDocument = (id: number) => api.get<DocumentDetail>(`/documents/${id}`)

/**
 * Lưu bản đã được người dùng sửa. Backend ghi kèm giá trị trước và sau vào nhật ký kiểm toán.
 *
 * CHƯA HIỆN THỰC ở backend (TASK-006 cắt phạm vi có chủ đích, xem
 * IMPLEMENTATION_PLAN.md) — gọi hàm này hiện sẽ nhận lỗi 404. Làm ở task riêng
 * sau khi có models/user.py + JWT (Xác nhận thủ công cần biết ai xác nhận).
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
