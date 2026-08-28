import { QueryClient } from '@tanstack/react-query'

/**
 * Chu kỳ coi là còn mới, đặt theo mức độ biến động của từng loại dữ liệu.
 * Xem mục 6.6 của tài liệu thiết kế.
 */
export const STALE = {
  static: 30 * 60_000,   // danh mục công cụ, cấu hình hệ thống
  list: 60_000,          // danh sách nhân viên AI
  runs: 15_000,          // lịch sử chạy
  live: 0,               // lần chạy đang thực thi — dữ liệu đến qua SSE
} as const

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: STALE.list,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})
