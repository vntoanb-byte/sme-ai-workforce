/**
 * P-07 — Danh sách lần chạy.
 *
 * NGÔN NGỮ HÌNH ẢNH: đây là "sổ nhật ký vận hành" (ledger), không phải một
 * bảng dữ liệu trung tính. Bản chất của trang: dòng thời gian các lần máy
 * đã tự chạy — ai/cái gì đã xảy ra, khi nào. Vì vậy cột đầu tiên không phải
 * "Mã", mà là một TRỤC THỜI GIAN (vạch dọc + chấm mốc màu theo trạng thái,
 * chấm "nhấp nháy" nhẹ khi lần chạy đang thực sự diễn ra ngay lúc này). Lần
 * chạy FAILED / NEEDS_REVIEW được đóng khung thành một khối cảnh báo có màu
 * ngay trong cột "Kết quả" thay vì một dòng chữ nhỏ dễ bị lướt qua — vì người
 * dùng cần nhận ra ngay lần nào cần can thiệp mà không phải đọc từng dòng.
 *
 * Vẫn dùng lại khuôn DataTable (không sửa file gốc) nên toàn bộ phần lọc,
 * phân trang, trạng thái tải/rỗng/lỗi giữ nguyên hành vi đã có — trang này
 * chỉ định nghĩa lại CÁCH TỪNG Ô HIỂN THỊ. Cũng chính thành phần này được
 * nhúng lại trong tab "Lịch sử" của trang chi tiết nhân viên AI, chỉ khác
 * một bộ lọc — xem thuộc tính employeeId.
 *
 * Bảng màu: không bịa mã màu mới — mọi màu ngữ nghĩa (đỏ lỗi, vàng cần xem,
 * xanh hoàn tất) đều lấy đúng hex đã dùng trong Badge/Callout của
 * components/ui/primitives.tsx, chỉ đổi từ "nền nhạt" sang "chấm đặc" cho
 * hợp vai trò mốc thời gian.
 */
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Clock, FileText, User, type LucideIcon } from 'lucide-react'
import { listRuns } from '@/api/runs'
import type { RunRow, RunStatus } from '@/api/types'
import { formatDuration } from '@/lib/format'
import { cn } from '@/lib/cn'
import { STALE } from '@/lib/query'
import { usePagedQuery } from '@/hooks/usePagedQuery'
import { PageHeader } from '@/components/shared/PageHeader'
import { DataTable, type Column, type FilterDef } from '@/components/shared/DataTable'
import { RunStatusBadge } from '@/components/shared/StatusBadge'

const FILTER_KEYS = ['status']

const filters: FilterDef[] = [
  {
    key: 'status', kind: 'select', label: 'Trạng thái',
    options: [
      { value: 'RUNNING', label: 'Đang chạy' },
      { value: 'SUCCEEDED', label: 'Hoàn tất' },
      { value: 'NEEDS_REVIEW', label: 'Chờ xác nhận' },
      { value: 'FAILED', label: 'Lỗi' },
    ],
  },
]

const TRIGGER: Record<RunRow['trigger_type'], { label: string; icon: LucideIcon }> = {
  manual: { label: 'Thủ công', icon: User },
  cron: { label: 'Theo lịch', icon: Clock },
  file_watch: { label: 'Có tệp mới', icon: FileText },
}

/** Dùng độc lập ở /runs, hoặc nhúng trong tab Lịch sử của một nhân viên AI. */
export function RunListPage({ employeeId, embedded }: { employeeId?: number; embedded?: boolean }) {
  const nav = useNavigate()
  const state = usePagedQuery(FILTER_KEYS)

  const q = useQuery({
    queryKey: ['runs', { ...state.filters, employeeId }, state.page],
    queryFn: () => listRuns({ ...state.filters, employee_id: employeeId, page: state.page, page_size: state.pageSize }),
    staleTime: STALE.runs,
  })

  const columns: Column<RunRow>[] = [
    {
      key: 'when', header: 'Thời điểm', width: 'w-[160px]',
      render: (r) => <WhenCell status={r.status} iso={r.started_at} />,
    },
    ...(employeeId ? [] : [{
      key: 'emp', header: 'Nhân viên AI', width: 'w-[180px]',
      render: (r: RunRow) => <span className="truncate font-semibold text-ink">{r.employee_name}</span>,
    }]),
    {
      key: 'trigger', header: 'Kích hoạt', width: 'w-[128px]',
      render: (r) => {
        const t = TRIGGER[r.trigger_type]
        const Icon = t.icon
        return (
          <span className="inline-flex items-center gap-1.5 text-ink-soft">
            <Icon className="h-3.5 w-3.5 shrink-0 text-ink-faint" aria-hidden />
            {t.label}
          </span>
        )
      },
    },
    {
      key: 'duration', header: 'Thời lượng', width: 'w-[110px]', align: 'right',
      render: (r) => r.started_at && r.finished_at
        ? <span className="font-mono text-[12px] tabular-nums text-ink-soft">{formatDuration(new Date(r.finished_at).getTime() - new Date(r.started_at).getTime())}</span>
        : <span className="text-ink-faint">—</span>,
    },
    {
      key: 'docs', header: 'Chứng từ', width: 'w-[86px]', align: 'right',
      render: (r) => r.doc_count
        ? <span className="font-mono text-[12px] tabular-nums text-ink-soft">{r.doc_count}</span>
        : <span className="text-ink-faint">—</span>,
    },
    {
      key: 'status', header: 'Kết quả', width: 'w-[240px]',
      render: (r) => (
        <div className="flex flex-col items-start gap-1">
          <RunStatusBadge status={r.status} />
          {r.error_message && <ResultNote status={r.status} message={r.error_message} />}
        </div>
      ),
    },
  ]

  const table = (
    <DataTable
      columns={columns}
      filters={filters}
      state={state}
      data={q.data}
      isLoading={q.isLoading}
      error={q.error}
      onRetry={() => q.refetch()}
      rowKey={(r) => r.id}
      onRowClick={(r) => nav(`/runs/${r.id}`)}
      emptyTitle="Chưa có lần chạy nào"
      emptyHint="Nhân viên AI sẽ tự chạy theo lịch, hoặc bạn có thể kích hoạt thủ công từ trang chi tiết."
    />
  )

  if (embedded) return table

  return (
    <>
      <PageHeader title="Lần chạy" subtitle="Dòng thời gian các lần chạy — mới nhất hiển thị trước" />
      {table}
    </>
  )
}

// ─────────────────────────── Trục thời gian ───────────────────────────

// Tái dùng đúng các mã màu ngữ nghĩa đã có trong Badge (primitives.tsx: TONE.ok/warn/error)
// — chỉ đổi vai trò từ "nền nhạt của huy hiệu" sang "chấm đặc trên trục thời gian".
const DOT_COLOR: Record<RunStatus, string> = {
  PENDING: 'bg-ink-faint',
  CLAIMED: 'bg-brand',
  RUNNING: 'bg-brand',
  RETRYING: 'bg-[#9A6206]',
  NEEDS_REVIEW: 'bg-[#9A6206]',
  SUCCEEDED: 'bg-[#137A47]',
  FAILED: 'bg-[#B33520]',
  CANCELLED: 'bg-ink-faint',
}

// Trạng thái "đang diễn ra ngay lúc này" — chấm mốc nhấp nháy nhẹ để phân biệt
// với các mốc đã khép lại (thành công/lỗi/huỷ), đúng cảm giác một cuốn sổ đang
// được viết tiếp chứ không phải một danh sách tĩnh.
const LIVE_STATUSES = new Set<RunStatus>(['RUNNING', 'CLAIMED', 'RETRYING'])

function WhenCell({ status, iso }: { status: RunStatus; iso: string | null }) {
  const live = LIVE_STATUSES.has(status)
  return (
    <div className="flex items-stretch gap-2.5">
      <div className="relative w-3 shrink-0">
        <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-line" aria-hidden />
        <span className="absolute left-1/2 top-1/2 flex h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 items-center justify-center">
          {live && (
            <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-40', DOT_COLOR[status])} aria-hidden />
          )}
          <span className={cn('relative h-2 w-2 rounded-full ring-2 ring-white', DOT_COLOR[status])} aria-hidden />
        </span>
      </div>
      <div className="min-w-0 leading-tight">
        {iso ? (
          <>
            <div className="font-mono text-[10px] uppercase tracking-wide text-ink-faint">{dayLabel(iso)}</div>
            <div className="font-mono text-[13px] font-semibold tabular-nums text-ink">{timeLabel(iso)}</div>
          </>
        ) : (
          <span className="text-[12.5px] text-ink-faint">Chưa bắt đầu</span>
        )}
      </div>
    </div>
  )
}

/** "2026-08-27T08:00" → "Hôm nay" · "Hôm qua" · "27/08" — nhãn ngày rút gọn cho mốc thời gian. */
function dayLabel(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const today = new Date()
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diffDays = Math.round((startOf(today) - startOf(d)) / 86_400_000)
  if (diffDays === 0) return 'Hôm nay'
  if (diffDays === 1) return 'Hôm qua'
  if (diffDays === -1) return 'Ngày mai'
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`
}

/** "2026-08-27T08:00" → "08:00" */
function timeLabel(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

// ─────────────────────────── Ghi chú kết quả ───────────────────────────

/**
 * Khối cảnh báo có màu, ghim ngay dưới huy hiệu trạng thái — thay cho một
 * dòng chữ nhỏ dễ bị lướt qua khi cuộn sổ. FAILED dùng đúng tông "error",
 * NEEDS_REVIEW/RETRYING dùng đúng tông "warn" — cả hai đều lấy nguyên hex
 * đã có ở Badge (primitives.tsx), không phát sinh màu mới.
 */
function ResultNote({ status, message }: { status: RunStatus; message: string }) {
  const isError = status === 'FAILED'
  return (
    <div
      className={cn(
        'flex max-w-[220px] items-start gap-1.5 rounded-md border px-2 py-1 text-[11px] leading-snug',
        isError ? 'border-[#F3C6BA] bg-[#FDE8E4] text-[#B33520]' : 'border-[#F5DFAE] bg-[#FEF2DC] text-[#9A6206]',
      )}
    >
      <AlertTriangle className="mt-[1px] h-3 w-3 shrink-0" aria-hidden />
      <span className="line-clamp-2">{message}</span>
    </div>
  )
}
