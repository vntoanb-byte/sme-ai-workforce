import { api } from './client'
import type { LlmTestResult, Metrics, User } from './types'

export const getMetrics = () => api.get<Metrics>('/admin/metrics')

export const listUsers = () => api.get<User[]>('/admin/users')

export const testLlm = () => api.post<LlmTestResult>('/admin/llm/test')
