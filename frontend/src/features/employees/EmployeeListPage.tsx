/**
 * P-03 — Danh sách nhân viên AI.
 *
 * Nút "Tạo mới" mở CreateEmployeeWizard dưới dạng cửa sổ, không chuyển trang.
 * Tham số ?new=1 trên đường dẫn cũng mở cửa sổ này — nhờ vậy nút trên bảng
 * điều khiển liên kết thẳng sang được.
 *
 * NGÔN NGỮ HÌNH ẢNH: đây không phải một bảng dữ liệu — đây là một BẢNG TỔ
 * CHỨC. Mỗi nhân viên AI hiện thành một "thẻ vị trí" (giống thẻ nhân sự ghim
 * trên sơ đồ tổ chức), có tên riêng, vai trò riêng, đang trực hay đang nghỉ.
 * Vì vậy trang này KHÔNG dùng lại <DataTable/> dùng chung cho 3 màn hình
 * danh sách còn lại (chứng từ, lần chạy, người dùng) — những dữ liệu đó là
 * "bản ghi", còn đây là "người". Toàn bộ state/khoá truy vấn (usePagedQuery,
 * useQuery, listEmployees) giữ nguyên 100% so với bản trước; chỉ phần trình
 * bày được viết lại.
 */
import * as React from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Plus, Search, X } from 'lucide-react'
import { listEmployees } from '@/api/employees'
import type { Employee, EmployeeStatus } from '@/api/types'
import { formatRelativeDay } from '@/lib/format'
import { STALE } from '@/lib/query'
import { cn } from '@/lib/cn'
import { usePagedQuery } from '@/hooks/usePagedQuery'
import { PageHeader } from '@/components/shared/PageHeader'
import { EmptyState, ErrorState } from '@/components/shared/States'
import { EmployeeStatusBadge, RunStatusBadge } from '@/components/shared/StatusBadge'
import { Button, Input, Select, Skeleton } from '@/components/ui/primitives'
import { CreateEmployeeWizard } from './CreateEmployeeWizard'

const FILTER_KEYS = ['status', 'q']

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'active', label: 'Đang bật' },
  { value: 'paused', label: 'Tạm dừng' },
  { value: 'draft', label: 'Bản nháp' },
]

export function EmployeeListPage() {
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const state = usePagedQuery(FILTER_KEYS)
  const wizardOpen = sp.get('new') === '1'

  const setWizard = (open: boolean) => {
    const next = new URLSearchParams(sp)
    if (open) next.set('new', '1')
    else next.delete('new')
    setSp(next, { replace: true })
  }

  const q = useQuery({
    queryKey: ['employees', state.filters, state.page],
    queryFn: () => listEmployees({ ...state.filters, page: state.page, page_size: state.pageSize }),
    staleTime: STALE.list,
  })

  const data = q.data
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader
        title="Nhân viên AI"
        subtitle="Mỗi nhân viên AI là một quy trình xử lý tự động do bạn mô tả bằng tiếng Việt"
        actions={
          <Button variant="primary" onClick={() => setWizard(true)}>
            <Plus className="h-4 w-4" /> Tạo nhân viên AI
          </Button>
        }
      />

      <div className="flex flex-col gap-3">
        {/* ── Thanh lọc — tìm theo vị trí, lọc theo trạng thái trực ── */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
            <Input
              className="pl-8"
              placeholder="Tìm theo tên nhân viên AI…"
              defaultValue={state.filters.q}
              onKeyDown={(e) => {
                if (e.key === 'Enter') state.setFilter('q', (e.target as HTMLInputElement).value)
              }}
              onBlur={(e) => state.setFilter('q', e.target.value)}
            />
          </div>
          <Select
            className="w-auto min-w-[168px]"
            value={state.filters.status}
            onChange={(e) => state.setFilter('status', e.target.value)}
          >
            <option value="">Trạng thái: tất cả</option>
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
          {state.hasFilters && (
            <Button variant="ghost" size="sm" onClick={state.clearFilters}>
              <X className="h-3.5 w-3.5" /> Bỏ lọc
            </Button>
          )}
          {data && (
            <span className="ml-auto font-mono text-[11px] uppercase tracking-wide text-ink-faint">
              {data.total.toLocaleString('vi-VN')} vị trí
            </span>
          )}
        </div>

        {/* ── Bảng tổ chức ── */}
        {q.isLoading && <RosterSkeleton />}

        {!q.isLoading && !!q.error && (
          <div className="rounded-xl border border-line bg-white">
            <ErrorState error={q.error} onRetry={() => q.refetch()} />
          </div>
        )}

        {!q.isLoading && !q.error && data && data.items.length === 0 && (
          <div className="rounded-xl border border-line bg-white">
            <EmptyState
              title="Chưa có nhân viên AI nào"
              hint="Bấm Tạo nhân viên AI và mô tả công việc bạn muốn giao — hệ thống sẽ tự dựng quy trình."
            />
          </div>
        )}

        {!q.isLoading && !q.error && data && data.items.length > 0 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((e) => (
              <EmployeeCard key={e.id} employee={e} onOpen={() => nav(`/employees/${e.id}`)} />
            ))}
          </div>
        )}

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

      <CreateEmployeeWizard open={wizardOpen} onClose={() => setWizard(false)} />
    </>
  )
}

/** Một "thẻ vị trí" trên bảng tổ chức — đại diện cho một nhân viên AI. */
function EmployeeCard({ employee: e, onOpen }: { employee: Employee; onOpen: () => void }) {
  const offDuty = e.status === 'paused' || e.status === 'draft' || e.status === 'archived'

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'group flex flex-col rounded-xl border bg-white p-4 text-left transition-colors',
        'hover:border-brand/40 hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40',
        e.status === 'draft' ? 'border-dashed border-line' : 'border-line',
      )}
    >
      <div className="flex items-start gap-3">
        <PositionBadge name={e.name} status={e.status} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className={cn('truncate font-semibold', offDuty ? 'text-ink-soft' : 'text-ink')}>{e.name}</p>
            <EmployeeStatusBadge status={e.status} />
          </div>
          <p className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-ink-mute">{e.job_description}</p>
        </div>
      </div>

      <div className="mt-3.5 grid grid-cols-2 gap-x-3 gap-y-2.5 border-t border-line-soft pt-3">
        <Stat label="Lịch chạy">
          {e.schedule_label ?? <span className="text-ink-faint">Thủ công</span>}
        </Stat>
        <Stat label="Lần kế tiếp">
          {e.next_run_at ? formatRelativeDay(e.next_run_at) : <span className="text-ink-faint">—</span>}
        </Stat>
        <Stat label="Lần chạy gần nhất">
          {e.last_run_at ? (
            <span className="flex flex-wrap items-center gap-1.5">
              <span>{formatRelativeDay(e.last_run_at)}</span>
              {e.last_run_status && <RunStatusBadge status={e.last_run_status} />}
            </span>
          ) : (
            <span className="text-ink-faint">Chưa chạy lần nào</span>
          )}
        </Stat>
        <Stat label="30 ngày qua">
          <span className="font-mono text-[13px] font-bold tabular-nums text-ink">{e.runs_30d}</span>
          <span className="ml-1 text-ink-faint">lượt chạy</span>
        </Stat>
      </div>
    </button>
  )
}

/** Ô chữ đầu kiểu thẻ nhân sự — đứng thay avatar vì nhân viên AI không có ảnh chân dung. */
function PositionBadge({ name, status }: { name: string; status: EmployeeStatus }) {
  const offDuty = status === 'paused' || status === 'draft' || status === 'archived'
  return (
    <div
      className={cn(
        'flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border font-mono text-[13px] font-bold',
        status === 'draft'
          ? 'border-dashed border-line text-ink-faint'
          : offDuty
            ? 'border-line bg-line-soft text-ink-mute'
            : 'border-brand/30 bg-brand-light text-brand-dark',
      )}
      aria-hidden
    >
      {initials(name)}
    </div>
  )
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-faint">{label}</p>
      <div className="mt-0.5 truncate text-[12.5px] text-ink-soft">{children}</div>
    </div>
  )
}

/** Khung chờ tải — cùng bố cục lưới thẻ để không "nhảy" giao diện khi dữ liệu về. */
function RosterSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-line bg-white p-4">
          <div className="flex items-start gap-3">
            <Skeleton className="h-11 w-11 shrink-0 rounded-lg" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-full" />
            </div>
          </div>
          <div className="mt-3.5 grid grid-cols-2 gap-x-3 gap-y-2.5 border-t border-line-soft pt-3">
            {Array.from({ length: 4 }).map((__, j) => (
              <div key={j} className="space-y-1.5">
                <Skeleton className="h-2.5 w-16" />
                <Skeleton className="h-3.5 w-20" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/** "Trợ lý xử lý hoá đơn" → "TX" — chữ đầu của tối đa hai từ đầu tiên trong tên vị trí. */
function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '—'
  return words.slice(0, 2).map((w) => w[0]).join('').toUpperCase()
}
