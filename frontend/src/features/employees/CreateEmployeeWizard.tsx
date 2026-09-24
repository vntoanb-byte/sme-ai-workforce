/**
 * M-01 — Cửa sổ tạo nhân viên AI.
 *
 * Wizard hai bước trong MỘT cửa sổ, không chiếm tuyến đường nào. Đây là màn
 * hình thể hiện rõ nhất ý tưởng của đề tài: người dùng không cấu hình gì cả,
 * chỉ gõ mô tả công việc như đang giao việc cho một nhân viên mới.
 *
 * Chi tiết quan trọng: trong lúc chờ biên dịch, hiển thị TỪNG GIAI ĐOẠN đang
 * chạy chứ không dùng biểu tượng quay tròn — quá trình mất 10 đến 30 giây,
 * quá lâu để người dùng nhìn một vòng tròn quay.
 */
import * as React from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Sparkles } from 'lucide-react'
import { approveWorkflow, createEmployee } from '@/api/employees'
import { ApiError } from '@/api/client'
import type { Workflow, WorkflowStep } from '@/api/types'
import { Dialog } from '@/components/ui/overlay'
import { Button, Callout, Input, Label, Spinner, Textarea } from '@/components/ui/primitives'
import { StepParams, WorkflowGraph } from './WorkflowGraph'
import { cn } from '@/lib/cn'

const PLACEHOLDER =
  'Mỗi sáng 8 giờ, đọc các hoá đơn mới trong thư mục Scan trên máy chủ, ' +
  'nhập dữ liệu vào tệp SoHoaDon2026.xlsx, kiểm tra xem tổng tiền có khớp không, ' +
  'và gửi báo cáo tổng hợp cho chị Hương vào cuối ngày.'

/** Gợi ý dẫn người dùng vào đúng vùng khả năng của hệ thống mà không cần giải thích khái niệm mẫu. */
const SUGGESTIONS: { label: string; text: string }[] = [
  { label: '📄 Đọc hoá đơn → nhập Excel', text: 'Mỗi sáng 8 giờ, đọc các hoá đơn mới trong thư mục Scan và nhập vào tệp SoHoaDon2026.xlsx.' },
  { label: '📊 Đọc hoá đơn → lập báo cáo', text: 'Cuối mỗi ngày, tổng hợp các hoá đơn đã xử lý và lập báo cáo Excel gửi cho quản lý.' },
  { label: '🧹 Làm sạch bảng tính', text: 'Làm sạch tệp DanhSachKhachHang.xlsx: chuẩn hoá định dạng ngày và số, xoá các dòng trùng theo mã số thuế.' },
  { label: '⇄ Đối chiếu hai tệp', text: 'Mỗi thứ Hai lúc 9 giờ, đối chiếu tệp SoHoaDon2026.xlsx với CongNo.xlsx theo số hoá đơn và liệt kê các dòng lệch.' },
]

const STAGES = [
  'Đang hiểu yêu cầu của bạn',
  'Đang xác định lịch chạy',
  'Đang dựng các bước xử lý',
  'Đang kiểm tra tính hợp lệ của quy trình',
]

export function CreateEmployeeWizard({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = React.useState('')
  const [desc, setDesc] = React.useState('')
  const [stage, setStage] = React.useState(-1)
  const [workflow, setWorkflow] = React.useState<Workflow | null>(null)
  const [errors, setErrors] = React.useState<{ rule: string; message: string }[]>([])
  const [selected, setSelected] = React.useState<string | null>(null)

  const reset = () => {
    setName(''); setDesc(''); setStage(-1); setWorkflow(null); setErrors([]); setSelected(null)
  }

  const compile = useMutation({
    mutationFn: () => createEmployee(name.trim() || 'Nhân viên AI mới', desc.trim()),
    onSuccess: (res) => {
      setStage(-1)
      if (res.ok && res.workflow) { setWorkflow(res.workflow); setErrors([]) }
      else setErrors(res.errors ?? [{ rule: 'UNKNOWN', message: 'Không dựng được quy trình.' }])
    },
    onError: () => {
      setStage(-1)
      setErrors([{ rule: 'NETWORK', message: 'Không kết nối được tới máy chủ. Vui lòng thử lại.' }])
    },
  })

  // Chạy hoạt ảnh từng giai đoạn trong lúc chờ mô hình trả lời
  React.useEffect(() => {
    if (!compile.isPending) return
    setStage(0)
    const t = setInterval(() => setStage((s) => Math.min(STAGES.length - 1, s + 1)), 520)
    return () => clearInterval(t)
  }, [compile.isPending])

  const start = () => { setErrors([]); setWorkflow(null); compile.mutate() }

  // Duyệt quy trình ở backend: chuyển approved, bật nhân viên AI, đăng ký lịch chạy.
  const approve = useMutation({
    mutationFn: (wf: Workflow) => approveWorkflow(wf.id, wf.employee_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['employees'] })
      onClose()
      reset()
    },
  })
  const approveError = approve.error instanceof ApiError ? approve.error : null

  const finish = () => { if (workflow) approve.mutate(workflow) }


  const selectedStep: WorkflowStep | null =
    workflow?.steps.find((s) => s.step_key === selected) ?? null

  const step2 = !!workflow

  return (
    <Dialog
      open={open}
      onClose={() => { if (workflow) qc.invalidateQueries({ queryKey: ['employees'] }); onClose(); reset() }}
      title={step2 ? 'Xem lại quy trình' : 'Tạo nhân viên AI'}
      subtitle={step2 ? 'Bước 2 / 2 — Kiểm tra trước khi kích hoạt' : 'Bước 1 / 2 — Mô tả công việc'}
      width={step2 ? 'max-w-5xl' : 'max-w-2xl'}
      footer={
        step2 ? (
          <>
            <Button onClick={() => { setWorkflow(null); setSelected(null); approve.reset() }}>Sửa lại mô tả</Button>
            <Button variant="success" className="ml-auto" loading={approve.isPending} onClick={finish}>
              <Check className="h-4 w-4" /> Duyệt và kích hoạt
            </Button>
          </>
        ) : (
          <>
            <Button onClick={() => { onClose(); reset() }}>Huỷ</Button>
            <Button
              variant="primary"
              className="ml-auto"
              loading={compile.isPending}
              disabled={desc.trim().length < 15}
              onClick={start}
            >
              <Sparkles className="h-4 w-4" /> Dựng quy trình
            </Button>
          </>
        )
      }
    >
      {!step2 ? (
        <>
          <div className="mb-3.5">
            <Label htmlFor="emp-name">Tên nhân viên AI</Label>
            <Input id="emp-name" placeholder="Ví dụ: Kế toán hoá đơn" value={name} onChange={(e) => setName(e.target.value)} />
          </div>

          <p className="mb-2 text-[13px] leading-relaxed text-ink-soft">
            Mô tả công việc bạn muốn giao, bằng tiếng Việt bình thường —{' '}
            <b className="text-ink">giống như đang giao việc cho một nhân viên mới</b>.
          </p>

          <Textarea
            rows={5}
            placeholder={PLACEHOLDER}
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            maxLength={2000}
            className="text-[14px] leading-relaxed"
          />
          <p className="mt-1 text-right text-[11px] text-ink-faint">{desc.length} / 2000 ký tự</p>

          <p className="mb-2 mt-3.5 text-[11px] font-semibold uppercase tracking-wide text-ink-mute">
            Hoặc chọn một mẫu có sẵn
          </p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => setDesc(s.text)}
                className="rounded-md border border-[#CBD5E4] bg-white px-2.5 py-1.5 text-[11.5px] font-semibold text-[#33445F] hover:border-brand/50 hover:bg-brand-light"
              >
                {s.label}
              </button>
            ))}
          </div>

          {compile.isPending && (
            <div className="mt-4 rounded-lg border border-[#DCE5F2] bg-[#F7F9FD] px-4 py-3.5">
              <p className="mb-3 text-[12.5px] font-bold text-[#2A3D5C]">Hệ thống đang xử lý yêu cầu của bạn…</p>
              <div className="flex flex-col gap-2.5 text-[13px]">
                {STAGES.map((s, i) => (
                  <div
                    key={s}
                    className={cn(
                      'flex items-center gap-2.5',
                      i < stage ? 'text-[#137A47]' : i === stage ? 'text-[#2A56B8]' : 'text-ink-faint',
                    )}
                  >
                    {i < stage ? (
                      <span className="flex h-[19px] w-[19px] items-center justify-center rounded-full bg-[#137A47] text-[11px] text-white">✓</span>
                    ) : i === stage ? (
                      <Spinner className="h-[19px] w-[19px]" />
                    ) : (
                      <span className="h-[19px] w-[19px] rounded-full border-2 border-[#CBD5E4]" />
                    )}
                    {s}
                  </div>
                ))}
              </div>
            </div>
          )}

          {errors.length > 0 && (
            <Callout tone="error" title="Chưa dựng được quy trình" className="mt-4">
              {errors.map((e, i) => (
                <p key={i} className={i > 0 ? 'mt-1.5' : ''}>{e.message}</p>
              ))}
            </Callout>
          )}
        </>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
          <div className="rounded-lg border border-line bg-[#FBFCFE] p-4">
            <p className="mb-3 text-[12px] text-ink-mute">
              Hệ thống sẽ thực hiện <b className="text-ink">{workflow!.steps.length} bước</b> theo thứ tự sau.
              Bấm vào một bước để xem tham số.
            </p>
            <WorkflowGraph workflow={workflow!} selected={selected} onSelect={setSelected} />
          </div>

          <div className="flex flex-col gap-3">
            <div className="rounded-lg border border-line bg-white p-3.5">
              <p className="mb-2.5 text-[13px] font-bold text-ink">
                {selectedStep ? 'Tham số của bước' : 'Tham số'}
              </p>
              <StepParams step={selectedStep} />
            </div>

            <Callout tone="ok" title="✓ Quy trình hợp lệ">
              Đã kiểm tra: các công cụ đều tồn tại, không có vòng lặp, dữ liệu giữa các bước
              khớp nhau, đường dẫn thư mục có thật.
            </Callout>

            {approveError ? (
              <Callout tone="error" title="Chưa duyệt được">
                {approveError.message}
              </Callout>
            ) : (
              <Callout tone="warn" title="Lưu ý">
                Quy trình chỉ bắt đầu chạy sau khi bạn bấm <b>Duyệt và kích hoạt</b>.
                Đóng cửa sổ lúc này thì nhân viên AI được lưu ở trạng thái nháp.
              </Callout>
            )}
          </div>
        </div>
      )}
    </Dialog>
  )
}
