/**
 * KHUÔN 1 — Bảng danh sách.
 *
 * Đây là biện pháp chống phình quan trọng nhất của tầng giao diện: bốn màn
 * hình danh sách (chứng từ, lần chạy, nhân viên AI, người dùng) đều dùng
 * chung thành phần này. Mỗi màn hình chỉ khai báo cột và bộ lọc, không viết
 * lại phần phân trang, trạng thái tải, trạng thái rỗng hay xử lý lỗi.
 *
 * Ghi chú kỹ thuật: bản này tự viết thay vì dựng trên TanStack Table. Lý do:
 * ít khái niệm phải học, ít mã hơn, và đủ dùng cho mọi màn hình hiện tại.
 * Nếu về sau cần kéo giãn cột, gộp nhóm hay ghim cột, hãy chuyển sang
 * TanStack Table — giao diện props bên ngoài giữ nguyên nên không ảnh hưởng
 * các màn hình đang dùng.
 */
import * as React from 'react'
import { ChevronLeft, ChevronRight, Search, X } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { Page } from '@/api/types'
import { Button, Input, Select, Skeleton } from '@/components/ui/primitives'
import { EmptyState, ErrorState } from './States'
import type { PagedState } from '@/hooks/usePagedQuery'

export interface Column<T> {
  key: string
  header: string
  /** Lớp Tailwind quy định độ rộng, ví dụ 'w-[140px]'. */
  width?: string
  align?: 'left' | 'center' | 'right'
  render: (row: T) => React.ReactNode
}

export type FilterDef =
  | { key: string; kind: 'search'; placeholder: string }
  | { key: string; kind: 'select'; label: string; options: { value: string; label: string }[] }

interface Props<T> {
  columns: Column<T>[]
  filters?: FilterDef[]
  state: PagedState
  data: Page<T> | undefined
  isLoading: boolean
  error: unknown
  onRetry: () => void
  rowKey: (row: T) => string | number
  onRowClick?: (row: T) => void
  emptyTitle?: string
  emptyHint?: string
}

export function DataTable<T>({
  columns, filters = [], state, data, isLoading, error, onRetry,
  rowKey, onRowClick, emptyTitle = 'Chưa có dữ liệu', emptyHint,
}: Props<T>) {
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const alignCls = (a?: Column<T>['align']) =>
    a === 'right' ? 'text-right' : a === 'center' ? 'text-center' : 'text-left'

  return (
    <div className="flex flex-col gap-3">
      {filters.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {filters.map((f) =>
            f.kind === 'search' ? (
              <div key={f.key} className="relative w-full sm:w-72">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
                <Input
                  className="pl-8"
                  placeholder={f.placeholder}
                  defaultValue={state.filters[f.key]}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') state.setFilter(f.key, (e.target as HTMLInputElement).value)
                  }}
                  onBlur={(e) => state.setFilter(f.key, e.target.value)}
                />
              </div>
            ) : (
              <Select
                key={f.key}
                className="w-auto min-w-[168px]"
                value={state.filters[f.key]}
                onChange={(e) => state.setFilter(f.key, e.target.value)}
              >
                <option value="">{f.label}: tất cả</option>
                {f.options.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </Select>
            ),
          )}
          {state.hasFilters && (
            <Button variant="ghost" size="sm" onClick={state.clearFilters}>
              <X className="h-3.5 w-3.5" /> Bỏ lọc
            </Button>
          )}
          {data && (
            <span className="ml-auto text-[12px] text-ink-mute">
              {data.total.toLocaleString('vi-VN')} bản ghi
            </span>
          )}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-line bg-white">
        <div className="thin-scroll overflow-x-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b border-line bg-[#FAFBFD]">
                {columns.map((c) => (
                  <th
                    key={c.key}
                    className={cn(
                      'px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-ink-mute',
                      alignCls(c.align), c.width,
                    )}
                  >
                    {c.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b border-line-soft">
                    {columns.map((c) => (
                      <td key={c.key} className="px-3 py-3"><Skeleton className="h-4 w-full" /></td>
                    ))}
                  </tr>
                ))}

              {!isLoading && data?.items.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(
                    'border-b border-line-soft last:border-0',
                    onRowClick && 'cursor-pointer hover:bg-brand-light/60',
                  )}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={cn('px-3 py-2.5 text-ink', alignCls(c.align))}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!isLoading && !error && data && data.items.length === 0 && (
          <EmptyState title={emptyTitle} hint={emptyHint} />
        )}
        {!isLoading && !!error && <ErrorState error={error} onRetry={onRetry} />}
      </div>

      {data && totalPages > 1 && (
        <div className="flex items-center justify-between text-[12px] text-ink-mute">
          <span>Trang {data.page} / {totalPages}</span>
          <div className="flex gap-2">
            <Button size="sm" disabled={state.page <= 1} onClick={() => state.setPage(state.page - 1)}>
              <ChevronLeft className="h-3.5 w-3.5" /> Trước
            </Button>
            <Button size="sm" disabled={state.page >= totalPages} onClick={() => state.setPage(state.page + 1)}>
              Sau <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
