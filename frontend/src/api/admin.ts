import { api } from './client'
import type { LlmConfig, LlmModelsResult, LlmSettingsInput, LlmTestResult, Metrics, User } from './types'

export const getMetrics = () => api.get<Metrics>('/admin/metrics')

export const listUsers = () => api.get<User[]>('/admin/users')

/** Không truyền gì: thử cấu hình đang chạy. Truyền giá trị đang nhập: thử trước khi lưu. */
export const testLlm = (input?: LlmSettingsInput) => api.post<LlmTestResult>('/admin/llm/test', input)

export const getLlmConfig = () => api.get<LlmConfig>('/admin/llm/config')

export const saveLlmConfig = (input: LlmSettingsInput) => api.put<LlmConfig>('/admin/llm/config', input)

export const listLlmModels = (input?: LlmSettingsInput) => api.post<LlmModelsResult>('/admin/llm/models', input)
