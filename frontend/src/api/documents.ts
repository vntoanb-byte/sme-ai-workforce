import { api, qs } from './client'
import type { DocumentDetail, DocumentRow, InvoiceData, Page } from './types'

export interface DocFilters {
  status?: string
  q?: string
  page?: number
  page_size?: number
}

export const listDocuments = (f: DocFilters) =>
  api.get<Page<DocumentRow>>('/documents' + qs({ ...f }))

export const getDocument = (id: number) => api.get<DocumentDetail>(`/documents/${id}`)

/** Lưu bản đã được người dùng sửa. Backend ghi kèm giá trị trước và sau vào nhật ký kiểm toán. */
export const patchExtraction = (id: number, data: InvoiceData) =>
  api.patch<DocumentDetail>(`/documents/${id}`, { data })

export const uploadDocument = (filename: string) =>
  api.post<DocumentRow>('/documents', { filename })
