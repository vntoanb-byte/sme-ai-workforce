import { api, qs } from './client'
import type { Page, RunDetail, RunRow } from './types'

export interface RunFilters {
  status?: string
  employee_id?: number
  page?: number
  page_size?: number
}

export const listRuns = (f: RunFilters) => api.get<Page<RunRow>>('/runs' + qs({ ...f }))

export const getRun = (id: number) => api.get<RunDetail>(`/runs/${id}`)

export const triggerRun = (employeeId: number) =>
  api.post<{ id: number }>('/runs', { employee_id: employeeId })

/** Đường dẫn kênh SSE truyền nhật ký thời gian thực. */
export const runLogsUrl = (id: number) => `/api/v1/runs/${id}/logs`
