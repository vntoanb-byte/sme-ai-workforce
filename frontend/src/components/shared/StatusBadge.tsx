/**
 * Ánh xạ mã trạng thái sang màu và nhãn tiếng Việt.
 *
 * Đây là nơi DUY NHẤT quy định màu và chữ cho từng trạng thái. Mọi màn hình
 * đều gọi qua đây, nên đổi một chỗ là đổi toàn hệ thống.
 *
 * Khả năng tiếp cận: màu luôn đi kèm nhãn chữ, không dùng màu làm phương tiện
 * truyền đạt duy nhất.
 */
import { Badge, type Tone } from '@/components/ui/primitives'
import type { DocStatus, EmployeeStatus, RunStatus, StepStatus } from '@/api/types'

const RUN: Record<RunStatus, { label: string; tone: Tone }> = {
  PENDING:      { label: 'Chờ xử lý',      tone: 'neutral' },
  CLAIMED:      { label: 'Đã nhận',        tone: 'running' },
  RUNNING:      { label: 'Đang chạy',      tone: 'running' },
  RETRYING:     { label: 'Đang thử lại',   tone: 'warn' },
  NEEDS_REVIEW: { label: 'Chờ xác nhận',   tone: 'warn' },
  SUCCEEDED:    { label: 'Hoàn tất',       tone: 'ok' },
  FAILED:       { label: 'Lỗi',            tone: 'error' },
  CANCELLED:    { label: 'Đã huỷ',         tone: 'neutral' },
}

const DOC: Record<DocStatus, { label: string; tone: Tone }> = {
  processing:   { label: 'Đang xử lý',   tone: 'running' },
  ok:           { label: 'Đạt',          tone: 'ok' },
  needs_review: { label: 'Chờ xác nhận', tone: 'warn' },
  rejected:     { label: 'Đã từ chối',   tone: 'neutral' },
  failed:       { label: 'Lỗi',          tone: 'error' },
}

const EMP: Record<EmployeeStatus, { label: string; tone: Tone }> = {
  draft:    { label: 'Bản nháp',  tone: 'neutral' },
  active:   { label: 'Bật',       tone: 'ok' },
  paused:   { label: 'Tạm dừng',  tone: 'neutral' },
  archived: { label: 'Lưu trữ',   tone: 'neutral' },
}

const STEP: Record<StepStatus, { label: string; tone: Tone }> = {
  PENDING:   { label: 'Chờ',      tone: 'neutral' },
  RUNNING:   { label: 'Đang chạy', tone: 'running' },
  SUCCEEDED: { label: 'Xong',     tone: 'ok' },
  FAILED:    { label: 'Lỗi',      tone: 'error' },
  SKIPPED:   { label: 'Bỏ qua',   tone: 'neutral' },
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const s = RUN[status]
  return <Badge tone={s.tone} dot>{s.label}</Badge>
}

export function DocStatusBadge({ status }: { status: DocStatus }) {
  const s = DOC[status]
  return <Badge tone={s.tone} dot>{s.label}</Badge>
}

export function EmployeeStatusBadge({ status }: { status: EmployeeStatus }) {
  const s = EMP[status]
  return <Badge tone={s.tone} dot>{s.label}</Badge>
}

export const stepTone = (s: StepStatus) => STEP[s].tone
export const stepLabel = (s: StepStatus) => STEP[s].label
