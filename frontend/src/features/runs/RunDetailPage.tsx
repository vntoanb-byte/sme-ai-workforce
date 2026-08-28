/**
 * P-08 — Chi tiết một lần chạy.
 *
 * Bố cục hai cột: tiến độ từng bước bên trái, nhật ký thời gian thực bên phải.
 *
 * Việc phơi bày nhật ký ở mức chi tiết này phục vụ hai mục đích: cho người
 * dùng thấy hệ thống thật sự đang làm gì thay vì một hộp đen, và cho phép truy
 * vết nguyên nhân khi có sự cố mà không cần lập trình viên can thiệp.
 */
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Check, CircleDashed, X } from 'lucide-react'
import { getRun } from '@/api/runs'
import type { RunStep } from '@/api/types'
import { STALE } from '@/lib/query'
import { formatDuration, formatMoney, formatRelativeDay } from '@/lib/format'
import { useRunLogs } from '@/hooks/useSSE'
import { PageHeader } from '@/components/shared/PageHeader'
import { SplitView } from '@/components/shared/SplitView'
import { RunStatusBadge } from '@/components/shared/StatusBadge'
import { ErrorState } from '@/components/shared/States'
import { Card, CardTitle, Skeleton, Spinner } from '@/components/ui/primitives'
import { LogStream } from './LogStream'
import { cn } from '@/lib/cn'

const TRIGGER = { manual: 'Kích hoạt thủ công', cron: 'Tự động theo lịch', file_watch: 'Kích hoạt khi có tệp mới' }

export function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const runId = Number(id)

  const q = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId),
    staleTime: STALE.live,
    // Lần chạy đang thực thi thì hỏi lại mỗi 5 giây; đã kết thúc thì thôi
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'RUNNING' || s === 'CLAIMED' || s === 'RETRYING' ? 5000 : false
    },
  })

  const running = q.data?.status === 'RUNNING' || q.data?.status === 'CLAIMED'
  const { logs, connected } = useRunLogs(runId, !!running)

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />

  const run = q.data

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader
        back="/runs"
        title={`Lần chạy #${runId}`}
        subtitle={
          run
            ? `${run.employee_name} · ${formatRelativeDay(run.started_at)} · ${TRIGGER[run.trigger_type]}`
            : undefined
        }
        actions={run && <RunStatusBadge status={run.status} />}
      />

      {q.isLoading || !run ? (
        <Skeleton className="h-[480px] w-full rounded-xl" />
      ) : (
        <SplitView
          storageKey="run-detail"
          defaultRatio={0.36}
          minRatio={0.28}
          maxRatio={0.55}
          left={
            <div className="flex h-full flex-col gap-3">
              <Card className="p-4">
                <CardTitle>Tiến độ các bước</CardTitle>
                <ol className="flex flex-col">
                  {run.steps.map((s, i) => (
                    <StepItem key={s.step_key} step={s} last={i === run.steps.length - 1} />
                  ))}
                </ol>
              </Card>

              <Card className="p-4">
                <CardTitle>{running ? 'Kết quả tạm tính' : 'Kết quả'}</CardTitle>
                <Stat label="Đã đọc xong" value={`${run.stats.read} hoá đơn`} />
                <Stat label="Kiểm tra đạt" value={String(run.stats.passed)} valueClass="text-[#137A47]" />
                <Stat label="Cần xác nhận" value={String(run.stats.needs_review)} valueClass="text-[#B4700B]" />
                <Stat label="Tổng giá trị" value={`${formatMoney(run.stats.total_amount)} đ`} mono last />
              </Card>

              {run.error_message && (
                <Card className="border-[#E5BFB2] bg-[#FEF6F3] p-3.5">
                  <p className="mb-1 text-[12.5px] font-bold text-[#A93318]">Lần chạy dừng vì lỗi</p>
                  <p className="text-[12px] leading-relaxed text-[#7A4433]">{run.error_message}</p>
                </Card>
              )}
            </div>
          }
          right={<LogStream logs={logs} live={connected} />}
        />
      )}
    </div>
  )
}

function StepItem({ step, last }: { step: RunStep; last: boolean }) {
  return (
    <li className="flex gap-3">
      <div className="flex flex-col items-center">
        <span
          className={cn(
            'flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px]',
            step.status === 'SUCCEEDED' && 'bg-[#137A47] text-white',
            step.status === 'RUNNING' && 'text-[#2A56B8]',
            step.status === 'FAILED' && 'bg-[#B33520] text-white',
            (step.status === 'PENDING' || step.status === 'SKIPPED') && 'border-2 border-[#CBD5E4]',
          )}
        >
          {step.status === 'SUCCEEDED' && <Check className="h-3 w-3" />}
          {step.status === 'FAILED' && <X className="h-3 w-3" />}
          {step.status === 'RUNNING' && <Spinner className="h-4 w-4" />}
          {step.status === 'SKIPPED' && <CircleDashed className="h-3 w-3 text-ink-faint" />}
        </span>
        {!last && (
          <span className={cn('w-0.5 flex-1', step.status === 'SUCCEEDED' ? 'bg-[#137A47]' : 'bg-[#DCE3EE]')} />
        )}
      </div>
      <div className={cn('pb-4', last && 'pb-0')}>
        <p
          className={cn(
            'text-[12.5px] font-semibold',
            step.status === 'RUNNING' ? 'text-[#2A56B8]'
              : step.status === 'PENDING' ? 'text-ink-faint' : 'text-ink',
          )}
        >
          {step.label}
        </p>
        {(step.detail || step.duration_ms !== null) && (
          <p className="mt-0.5 text-[11px] text-ink-mute">
            {step.detail}
            {step.detail && step.duration_ms !== null && ' · '}
            {step.duration_ms !== null && formatDuration(step.duration_ms)}
          </p>
        )}
      </div>
    </li>
  )
}

function Stat({ label, value, valueClass, mono, last }: {
  label: string; value: string; valueClass?: string; mono?: boolean; last?: boolean
}) {
  return (
    <div className={cn('flex items-center justify-between py-1.5 text-[12.5px]', !last && 'border-b border-line-soft')}>
      <span className="text-ink-mute">{label}</span>
      <b className={cn('text-ink', mono && 'font-mono tabular-nums', valueClass)}>{value}</b>
    </div>
  )
}
