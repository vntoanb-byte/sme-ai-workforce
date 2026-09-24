/**
 * P-04 — Chi tiết nhân viên AI.
 *
 * Dùng khuôn DetailTabs với ba tab. Tab "Lịch sử chạy" nhúng lại chính
 * RunListPage với bộ lọc employeeId — không viết lại bảng, không viết lại
 * phân trang. Đây là lợi ích cụ thể của việc chỉ có ba khuôn giao diện.
 */
import * as React from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Pause, Play, Zap } from 'lucide-react'
import { approveWorkflow, getEmployee, getWorkflow, patchEmployee } from '@/api/employees'
import { triggerRun } from '@/api/runs'
import { ApiError } from '@/api/client'
import { STALE } from '@/lib/query'
import { formatDateTime, formatRelativeDay } from '@/lib/format'
import { PageHeader } from '@/components/shared/PageHeader'
import { DetailTabs } from '@/components/shared/DetailTabs'
import { EmployeeStatusBadge } from '@/components/shared/StatusBadge'
import { ErrorState } from '@/components/shared/States'
import { Button, Callout, Card, CardTitle, Skeleton } from '@/components/ui/primitives'
import { StepParams, WorkflowGraph } from './WorkflowGraph'
import { RunListPage } from '../runs/RunListPage'

export function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const empId = Number(id)
  const qc = useQueryClient()
  const [selected, setSelected] = React.useState<string | null>(null)

  const emp = useQuery({ queryKey: ['employee', empId], queryFn: () => getEmployee(empId), staleTime: STALE.list })
  // Quy trình lấy theo workflow_id của nhân viên (bản đã duyệt, hoặc bản nháp mới nhất).
  const wfId = emp.data?.workflow_id ?? null
  const wf = useQuery({
    queryKey: ['workflow', wfId],
    queryFn: () => getWorkflow(wfId as number),
    enabled: wfId !== null,
    staleTime: STALE.static,
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['employee', empId] })
    qc.invalidateQueries({ queryKey: ['employees'] })
    qc.invalidateQueries({ queryKey: ['workflow', wfId] })
  }
  const toggle = useMutation({
    mutationFn: (status: 'active' | 'paused') => patchEmployee(empId, { status }),
    onSuccess: refresh,
  })
  const approve = useMutation({
    mutationFn: () => approveWorkflow(wfId as number, empId),
    onSuccess: refresh,
  })
  const run = useMutation({
    mutationFn: () => triggerRun(empId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['runs'] }),
  })
  const actionError = [toggle.error, approve.error, run.error].find((x) => x instanceof ApiError) as ApiError | undefined

  if (emp.isError) return <ErrorState error={emp.error} onRetry={() => emp.refetch()} />
  if (emp.isLoading || !emp.data) return <Skeleton className="h-96 w-full rounded-xl" />

  const e = emp.data
  const selectedStep = wf.data?.steps.find((s) => s.step_key === selected) ?? null

  return (
    <>
      <PageHeader
        back="/employees"
        title={e.name}
        subtitle={`${e.schedule_label ?? 'Chạy thủ công'} · Tạo ngày ${formatDateTime(e.created_at)}`}
        actions={
          <>
            <EmployeeStatusBadge status={e.status} />
            {wf.data?.status === 'pending' && (
              <Button variant="success" loading={approve.isPending} onClick={() => approve.mutate()}>
                <Check className="h-4 w-4" /> Duyệt quy trình
              </Button>
            )}
            <Button loading={run.isPending} disabled={e.status !== 'active' && e.status !== 'paused'} onClick={() => run.mutate()}>
              <Zap className="h-4 w-4" /> Chạy ngay
            </Button>
            {e.status === 'archived' || e.status === 'draft' ? null : e.status === 'active' ? (
              <Button loading={toggle.isPending} onClick={() => toggle.mutate('paused')}>
                <Pause className="h-4 w-4" /> Tạm dừng
              </Button>
            ) : (
              <Button variant="success" loading={toggle.isPending} onClick={() => toggle.mutate('active')}>
                <Play className="h-4 w-4" /> Bật
              </Button>
            )}
          </>
        }
      />

      {run.isSuccess && (
        <Callout tone="ok" className="mb-3">
          Đã đưa vào hàng đợi. Xem tiến độ ở tab <b>Lịch sử chạy</b>.
        </Callout>
      )}
      {actionError && (
        <Callout tone="error" className="mb-3">
          {actionError.message}
          {actionError.details && actionError.details.length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {(actionError.details as { message?: string }[]).map((d, i) => <li key={i}>{d.message}</li>)}
            </ul>
          )}
        </Callout>
      )}

      <DetailTabs
        tabs={[
          {
            key: 'workflow', label: 'Quy trình',
            element: (
              <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
                <Card className="bg-[#FBFCFE] p-4">
                  {wfId === null ? (
                    <p className="text-[12.5px] text-ink-mute">Nhân viên AI này chưa có quy trình.</p>
                  ) : wf.isLoading || !wf.data ? (
                    <Skeleton className="h-80 w-full" />
                  ) : (
                    <>
                      <p className="mb-3 text-[12px] text-ink-mute">
                        Phiên bản {wf.data.version}
                        {wf.data.status === 'pending' ? ' (chờ duyệt)' : ''} · {wf.data.steps.length} bước ·
                        Kích hoạt: {wf.data.trigger.label}
                      </p>
                      <WorkflowGraph workflow={wf.data} selected={selected} onSelect={setSelected} />
                    </>
                  )}
                </Card>
                <div className="flex flex-col gap-3">
                  <Card className="p-3.5">
                    <CardTitle>Tham số</CardTitle>
                    <StepParams step={selectedStep} />
                  </Card>
                  <Card className="p-3.5">
                    <CardTitle>Mô tả gốc của bạn</CardTitle>
                    <p className="text-[12.5px] italic leading-relaxed text-ink-soft">“{e.job_description}”</p>
                  </Card>
                </div>
              </div>
            ),
          },
          {
            key: 'schedule', label: 'Lịch chạy',
            element: (
              <Card className="max-w-xl p-4">
                <CardTitle>Cấu hình lịch</CardTitle>
                <Row label="Kiểu kích hoạt" value={wf.data?.trigger.label ?? '—'} />
                <Row label="Lần chạy kế tiếp" value={e.next_run_at ? formatRelativeDay(e.next_run_at) : 'Không có (đang tạm dừng)'} />
                <Row label="Lần chạy gần nhất" value={e.last_run_at ? formatDateTime(e.last_run_at) : 'Chưa chạy lần nào'} />
                <Row label="Số lần chạy 30 ngày" value={String(e.runs_30d)} last />
                <Callout tone="brand" className="mt-3.5">
                  Lịch chạy được sinh ra từ mô tả công việc của bạn. Muốn đổi giờ chạy,
                  hãy sửa mô tả và dựng lại quy trình — hệ thống sẽ tạo một phiên bản mới.
                </Callout>
              </Card>
            ),
          },
          {
            key: 'runs', label: 'Lịch sử chạy',
            element: <RunListPage employeeId={empId} embedded />,
          },
        ]}
      />
    </>
  )
}

function Row({ label, value, last }: { label: string; value: string; last?: boolean }) {
  return (
    <div className={`flex items-center justify-between py-2 text-[12.5px] ${last ? '' : 'border-b border-line-soft'}`}>
      <span className="text-ink-mute">{label}</span>
      <b className="text-ink">{value}</b>
    </div>
  )
}
