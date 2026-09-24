/**
 * Sơ đồ quy trình.
 *
 * Bản này dùng bố cục dọc bằng flexbox — ĐỦ DÙNG cho quy trình tuần tự có
 * nhánh rẽ đơn giản, và tránh được một thư viện nặng. Chỉ nâng cấp lên React
 * Flow nếu về sau cần kéo thả đổi cấu trúc; đó là điểm rất dễ sa đà, nên để
 * cuối lộ trình.
 *
 * Người dùng CHỈ được sửa tham số và xoá bước, KHÔNG được tự thêm bước hay nối
 * lại cạnh — cấu trúc đồ thị do mẫu quy trình quyết định. Giới hạn này giữ cho
 * kết quả luôn nằm trong tập quy trình đã được kiểm chứng.
 */
import * as React from 'react'
import type { Workflow, WorkflowStep } from '@/api/types'
import { cn } from '@/lib/cn'

const TONE: Record<string, { box: string; tag: string }> = {
  vision: { box: 'bg-[#FFF9EC] border-[#E8C97E]', tag: 'text-[#A07B1A]' },
  qc:     { box: 'bg-[#EEFAF3] border-[#92CFAE]', tag: 'text-[#137A47]' },
  fail:   { box: 'bg-[#FDF1EE] border-[#E5A08D]', tag: 'text-[#B33520]' },
  plain:  { box: 'bg-white border-[#C6D2E6]', tag: 'text-ink-mute' },
}

function toneOf(s: WorkflowStep): keyof typeof TONE {
  if (s.branch === 'fail') return 'fail'
  if (s.tool_code.startsWith('vision.')) return 'vision'
  if (s.tool_code.startsWith('qc.')) return 'qc'
  return 'plain'
}

function tagOf(s: WorkflowStep, idx: number): string {
  if (s.branch === 'pass') return `BƯỚC ${idx} · ĐẠT`
  if (s.branch === 'fail') return `BƯỚC ${idx} · KHÔNG ĐẠT`
  if (s.tool_code.startsWith('vision.')) return `BƯỚC ${idx} · ĐỌC BẰNG AI`
  if (s.tool_code.startsWith('qc.')) return `BƯỚC ${idx} · KIỂM TRA`
  if (s.tool_code.startsWith('fs.')) return `BƯỚC ${idx} · ĐỌC THƯ MỤC`
  if (s.tool_code.startsWith('report.')) return `BƯỚC ${idx} · BÁO CÁO`
  return `BƯỚC ${idx}`
}

export function WorkflowGraph({ workflow, selected, onSelect }: {
  workflow: Workflow
  selected?: string | null
  onSelect?: (stepKey: string) => void
}) {
  // Gom các bước cùng order_index thành một hàng (nhánh rẽ đạt / không đạt)
  const rows = React.useMemo(() => {
    const map = new Map<number, WorkflowStep[]>()
    for (const s of workflow.steps) {
      const arr = map.get(s.order_index) ?? []
      arr.push(s)
      map.set(s.order_index, arr)
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0])
  }, [workflow.steps])

  return (
    <div className="flex flex-col items-center py-1">
      {rows.map(([order, steps], ri) => (
        <React.Fragment key={order}>
          <div className={cn('flex gap-6', steps.length > 1 && 'flex-wrap justify-center')}>
            {steps.map((s) => {
              const t = TONE[toneOf(s)]
              const isSel = selected === s.step_key
              return (
                <button
                  key={s.step_key}
                  type="button"
                  onClick={() => onSelect?.(s.step_key)}
                  className={cn(
                    'rounded-lg border-[1.5px] px-3.5 py-2.5 text-left transition-shadow',
                    'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/45',
                    steps.length > 1 ? 'w-[210px]' : 'w-[340px]',
                    t.box,
                    isSel ? 'ring-2 ring-brand/45' : 'hover:shadow-md',
                  )}
                >
                  <p className={cn('text-[10px] font-bold tracking-wide', t.tag)}>{tagOf(s, order)}</p>
                  <p className="mt-0.5 text-[13px] font-semibold leading-snug text-ink">{s.label}</p>
                </button>
              )
            })}
          </div>
          {ri < rows.length - 1 && <div className="h-4 w-0.5 bg-[#C6D2E6]" />}
        </React.Fragment>
      ))}
    </div>
  )
}

/** Bảng tham số của bước đang chọn — hiển thị bên phải sơ đồ. */
export function StepParams({ step }: { step: WorkflowStep | null }) {
  if (!step) {
    return (
      <p className="text-[12px] leading-relaxed text-ink-mute">
        Bấm vào một bước trong sơ đồ để xem và sửa tham số của bước đó.
      </p>
    )
  }
  const entries = Object.entries(step.config)
  return (
    <div>
      <p className="mb-2 text-[12px] text-ink-mute">Công cụ</p>
      <p className="mb-3 font-mono text-[12px] font-semibold text-ink">{step.tool_code}</p>
      {entries.length === 0 && <p className="text-[12px] text-ink-faint">Bước này không có tham số.</p>}
      {entries.map(([k, v]) => (
        <div key={k} className="mb-2.5">
          <p className="text-[11px] uppercase tracking-wide text-ink-mute">{LABELS[k] ?? k}</p>
          <p className="mt-0.5 break-words text-[12.5px] font-semibold text-ink">{String(v)}</p>
        </div>
      ))}
    </div>
  )
}

const LABELS: Record<string, string> = {
  path: 'Thư mục nguồn',
  extensions: 'Định dạng nhận',
  schema_version: 'Phiên bản lược đồ',
  model: 'Mô hình sử dụng',
  retry_max: 'Số lần thử lại nếu lỗi',
  tolerance: 'Sai số cho phép (đồng)',
  rules: 'Tập quy tắc áp dụng',
  file: 'Tệp đích',
  sheet: 'Trang tính',
  assign_to: 'Giao cho',
  at: 'Thời điểm chạy',
  format: 'Định dạng kết xuất',
}
