/**
 * P-02 — Bảng điều khiển.
 *
 * Nguyên tắc: giao diện KHÔNG tính toán gì. Backend trả về mọi con số đã tính
 * sẵn qua một điểm cuối duy nhất /admin/metrics — không gọi bốn điểm cuối rời.
 *
 * NGÔN NGỮ HÌNH ẢNH: đây là trang "buồng lái" — chủ SME liếc một lần để biết
 * hệ thống có ổn không. Dải bốn chỉ số trên cùng dựng thành một "bảng đồng hồ"
 * liền khối, màu nav tối giống thanh điều hướng bên trái (cùng token `nav`),
 * để cảm giác đó là phần "khung máy" chứ không phải nội dung rời rạc. Chỉ số
 * duy nhất cần hành động — "Cần người xác nhận" — được tách khỏi tông trung
 * tính bằng một khối màu hổ phách + chấm nhấp nháy khi có việc tồn đọng, đúng
 * nguyên tắc: cái bất thường phải nổi hơn cái bình thường, không phải mọi ô
 * đều to bằng nhau. Bên dưới, các dòng "lần chạy" có sự cố được tô nền nhạt
 * cùng gam màu với badge lỗi/cảnh báo sẵn có để mắt lướt bảng vẫn bắt được
 * ngay dòng bất thường mà không cần đọc từng chữ.
 */
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, Plus } from 'lucide-react'
import { getMetrics } from '@/api/admin'
import { listRuns } from '@/api/runs'
import { listEmployees } from '@/api/employees'
import type { RunStatus } from '@/api/types'
import { STALE } from '@/lib/query'
import { cn } from '@/lib/cn'
import { formatMoney, formatRelativeDay } from '@/lib/format'
import { Button, Card, Skeleton } from '@/components/ui/primitives'
import { PageHeader } from '@/components/shared/PageHeader'
import { EmployeeStatusBadge, RunStatusBadge } from '@/components/shared/StatusBadge'
import { ErrorState } from '@/components/shared/States'

export function DashboardPage() {
  const nav = useNavigate()
  const m = useQuery({ queryKey: ['metrics'], queryFn: getMetrics, staleTime: STALE.runs })
  const runs = useQuery({ queryKey: ['runs', { page: 1 }], queryFn: () => listRuns({ page: 1, page_size: 5 }), staleTime: STALE.runs })
  const emps = useQuery({ queryKey: ['employees', 'dash'], queryFn: () => listEmployees({ page: 1, page_size: 5 }), staleTime: STALE.list })

  if (m.isError) return <ErrorState error={m.error} onRetry={() => m.refetch()} />

  const pendingReview = m.data?.needs_review_open ?? 0

  return (
    <>
      <PageHeader
        title="Bảng điều khiển"
        subtitle={m.data?.period_label}
        actions={
          <Button variant="primary" onClick={() => nav('/employees?new=1')}>
            <Plus className="h-4 w-4" /> Tạo nhân viên AI
          </Button>
        }
      />

      {/* Bảng đồng hồ — bốn chỉ số cốt lõi trong một khối liền, tông màu trùng với sidebar (`nav`) */}
      <div className="mb-4 overflow-hidden rounded-2xl border border-nav-line bg-nav">
        <div className="grid divide-y divide-nav-line sm:grid-cols-2 sm:divide-y-0 sm:divide-x xl:grid-cols-4">
          <Kpi
            loading={m.isLoading}
            label="Chứng từ đã xử lý"
            value={formatMoney(m.data?.docs_processed)}
            delta={m.data ? `▲ ${m.data.docs_processed_delta}% so với tháng trước` : undefined}
            deltaTone="up"
          />
          <Kpi
            loading={m.isLoading}
            label="Thời gian tiết kiệm"
            value={m.data ? String(m.data.hours_saved).replace('.', ',') : '—'}
            unit="giờ"
            note={m.data ? `≈ ${String(m.data.minutes_per_doc).replace('.', ',')} phút mỗi chứng từ` : undefined}
          />
          <Kpi
            loading={m.isLoading}
            label="Tự động hoàn toàn"
            value={m.data ? `${String(m.data.automation_rate).replace('.', ',')}%` : '—'}
            delta={m.data ? `▲ ${String(m.data.automation_rate_delta).replace('.', ',')} điểm` : undefined}
            deltaTone="up"
          />
          <Kpi
            loading={m.isLoading}
            label="Cần người xác nhận"
            value={formatMoney(m.data?.needs_review_total)}
            note={m.data ? `${m.data.needs_review_open} đang chờ xử lý` : undefined}
            to="/documents?status=needs_review"
            alert={pendingReview > 0}
          />
        </div>
      </div>

      <div className="grid gap-3.5 xl:grid-cols-[1.55fr_1fr]">
        <Card className="overflow-hidden p-0">
          <PanelHeader
            title="Các lần chạy gần nhất"
            action={<Link to="/runs" className="text-[11.5px] font-semibold text-brand hover:underline">Xem tất cả →</Link>}
          />
          <div className="p-4 pt-3">
            {runs.isLoading && <Skeleton className="h-40 w-full" />}
            {runs.data && (
              <table className="w-full text-[12.5px]">
                <thead>
                  <tr className="border-b border-line text-[11px] uppercase tracking-wide text-ink-mute">
                    <th className="pb-2 pr-3 text-left font-semibold">Nhân viên AI</th>
                    <th className="pb-2 pr-3 text-left font-semibold">Thời điểm</th>
                    <th className="pb-2 pr-3 text-right font-semibold">Chứng từ</th>
                    <th className="pb-2 text-left font-semibold">Kết quả</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.data.items.map((r) => (
                    <tr
                      key={r.id}
                      onClick={() => nav(`/runs/${r.id}`)}
                      className={cn(
                        'cursor-pointer border-b border-line-soft last:border-0 transition-colors hover:bg-brand-light/60',
                        RUN_ROW_TINT[r.status],
                      )}
                    >
                      <td className="py-2.5 pr-3 font-semibold text-ink">{r.employee_name}</td>
                      <td className="py-2.5 pr-3 text-ink-soft">{formatRelativeDay(r.started_at)}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums text-ink-soft">{r.doc_count || '—'}</td>
                      <td className="py-2.5"><RunStatusBadge status={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Card>

        <Card className="overflow-hidden p-0">
          <PanelHeader title="Nhân viên AI đang hoạt động" />
          <div className="flex flex-col gap-2.5 p-4 pt-3">
            {emps.isLoading && <Skeleton className="h-40 w-full" />}
            {emps.data?.items.map((e) => (
              <Link
                key={e.id}
                to={`/employees/${e.id}`}
                className={cn(
                  'rounded-lg border border-line border-l-2 px-3 py-2.5 transition-colors hover:border-brand/40 hover:bg-brand-light/40',
                  EMP_ACCENT[e.status],
                )}
              >
                <div className="flex items-center gap-2">
                  <b className="truncate text-[13px] text-ink">{e.name}</b>
                  <span className="ml-auto shrink-0"><EmployeeStatusBadge status={e.status} /></span>
                </div>
                <p className="mt-1 text-[11.5px] text-ink-mute">
                  {e.schedule_label ?? 'Chạy thủ công'}
                  {e.next_run_at && ` · Lần kế tiếp: ${formatRelativeDay(e.next_run_at)}`}
                </p>
              </Link>
            ))}
            <Button variant="primary" className="mt-1 w-full" onClick={() => nav('/employees?new=1')}>
              <Plus className="h-4 w-4" /> Tạo nhân viên AI mới
            </Button>
          </div>
        </Card>
      </div>
    </>
  )
}

/** Nền dòng "lần chạy" tô nhạt cho các trạng thái bất thường — cùng gam màu với Callout lỗi/cảnh báo
 *  đã dùng ở primitives.tsx (#FEF6F3 / #FFFAF0), giúp mắt lướt bảng bắt ngay dòng cần chú ý. */
const RUN_ROW_TINT: Partial<Record<RunStatus, string>> = {
  FAILED: 'bg-[#FEF6F3]',
  NEEDS_REVIEW: 'bg-[#FFFAF0]',
  RETRYING: 'bg-[#FFFAF0]',
}

/** Vạch trạng thái bên trái mỗi thẻ nhân viên AI — cùng màu với các tone đã có trong StatusBadge,
 *  cho cảm giác "đèn báo" trên buồng lái thay vì chỉ đọc chữ trong badge. */
const EMP_ACCENT: Record<string, string> = {
  active: 'border-l-[#137A47]',
  paused: 'border-l-line',
  draft: 'border-l-line',
  archived: 'border-l-line',
}

/** Tiêu đề khối, quy ước mono-uppercase giống nhãn thiết bị (đã dùng ở DocumentReviewPage.tsx),
 *  viết riêng tại đây thay vì CardTitle để giữ đúng "giọng" buồng lái cho toàn trang. */
function PanelHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
      <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-mute">{title}</span>
      {action && <div className="ml-auto shrink-0">{action}</div>}
    </div>
  )
}

function Kpi({ label, value, unit, delta, deltaTone, note, loading, to, alert }: {
  label: string
  value: string
  unit?: string
  delta?: string
  deltaTone?: 'up' | 'down'
  note?: string
  loading?: boolean
  to?: string
  /** Ô duy nhất cần hành động ngay — tách khỏi tông tối trung tính bằng nền hổ phách + chấm nhấp nháy. */
  alert?: boolean
}) {
  const body = (
    <div
      className={cn(
        'relative flex flex-col px-4 py-3.5 transition-colors sm:px-5',
        alert ? 'bg-[#3D2A0E] hover:bg-[#472F0F]' : 'hover:bg-white/[0.04]',
      )}
    >
      <p className="mb-1.5 flex items-center gap-1.5 font-mono text-[10.5px] uppercase tracking-[0.14em] text-nav-text">
        {alert && (
          <span className="relative flex h-1.5 w-1.5 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#F5A524] opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#F5A524]" />
          </span>
        )}
        {label}
        {to && <ArrowUpRight className="h-3 w-3 opacity-70" />}
      </p>
      {loading ? (
        <div className="h-7 w-24 animate-pulse rounded bg-white/10" />
      ) : (
        <p className={cn('text-[25px] font-bold leading-none tabular-nums', alert ? 'text-[#F5C877]' : 'text-white')}>
          {value}
          {unit && <span className="ml-1 text-[14px] font-normal text-nav-text">{unit}</span>}
        </p>
      )}
      {delta && (
        <p className={cn('mt-1.5 text-[11px] font-semibold', deltaTone === 'up' ? 'text-[#4ADE80]' : 'text-[#F87171]')}>
          {delta}
        </p>
      )}
      {note && <p className={cn('mt-1.5 text-[11px]', alert ? 'text-[#D8B37C]' : 'text-nav-text')}>{note}</p>}
    </div>
  )
  return to ? <Link to={to} className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40">{body}</Link> : body
}
