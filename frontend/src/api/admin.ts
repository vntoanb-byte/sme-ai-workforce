import { api } from './client'
import type { Metrics } from './types'

export const getMetrics = () => api.get<Metrics>('/admin/metrics')
