import { api } from './client'
import type { ReportPreview } from './types'

export interface ReportParams {
  from: string
  to: string
  group_by: 'seller' | 'month' | 'vat_rate'
}

export const previewReport = (p: ReportParams) => api.post<ReportPreview>('/reports/preview', p)
