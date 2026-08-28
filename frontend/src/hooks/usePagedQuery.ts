/**
 * Đồng bộ bộ lọc và số trang với query string trên đường dẫn.
 *
 * Nhờ hook này, người dùng chia sẻ được đường dẫn kèm bộ lọc — và đó chính là
 * cơ chế biến "Hàng đợi chờ xác nhận" từ một MÀN HÌNH thành một BỘ LỌC:
 *   /documents?status=needs_review
 */
import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

export interface PagedState {
  page: number
  pageSize: number
  filters: Record<string, string>
  setFilter: (key: string, value: string) => void
  setPage: (page: number) => void
  clearFilters: () => void
  hasFilters: boolean
}

export function usePagedQuery(filterKeys: string[], pageSize = 20): PagedState {
  const [sp, setSp] = useSearchParams()

  const page = Math.max(1, Number(sp.get('page') ?? 1))

  const filters = useMemo(() => {
    const o: Record<string, string> = {}
    for (const k of filterKeys) o[k] = sp.get(k) ?? ''
    return o
  }, [sp, filterKeys.join(',')])

  const setFilter = useCallback((key: string, value: string) => {
    const next = new URLSearchParams(sp)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('page') // đổi bộ lọc thì quay về trang 1
    setSp(next, { replace: true })
  }, [sp, setSp])

  const setPage = useCallback((p: number) => {
    const next = new URLSearchParams(sp)
    if (p <= 1) next.delete('page')
    else next.set('page', String(p))
    setSp(next, { replace: true })
  }, [sp, setSp])

  const clearFilters = useCallback(() => {
    const next = new URLSearchParams(sp)
    for (const k of filterKeys) next.delete(k)
    next.delete('page')
    setSp(next, { replace: true })
  }, [sp, setSp, filterKeys.join(',')])

  const hasFilters = filterKeys.some((k) => !!sp.get(k))

  return { page, pageSize, filters, setFilter, setPage, clearFilters, hasFilters }
}
