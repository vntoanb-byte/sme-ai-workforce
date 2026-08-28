import { api, qs } from './client'
import type { CompileResult, Employee, Page, Workflow } from './types'

export interface EmployeeFilters {
  status?: string
  q?: string
  page?: number
  page_size?: number
}

export const listEmployees = (f: EmployeeFilters) =>
  api.get<Page<Employee>>('/employees' + qs({ ...f }))

export const getEmployee = (id: number) => api.get<Employee>(`/employees/${id}`)

export const patchEmployee = (id: number, body: Partial<Employee>) =>
  api.patch<Employee>(`/employees/${id}`, body)

/** Gọi bộ biên dịch: mô tả tiếng Việt → quy trình. Có thể trả về danh sách lỗi. */
export const createEmployee = (name: string, job_description: string) =>
  api.post<CompileResult>('/employees', { name, job_description })

export const getWorkflow = (id: number) => api.get<Workflow>(`/workflows/${id}`)

export const approveWorkflow = (id: number, employeeId: number) =>
  api.post<Workflow>(`/workflows/${id}/approve` + qs({ employee_id: employeeId }))
