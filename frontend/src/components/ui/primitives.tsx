/**
 * Bộ thành phần giao diện cơ bản.
 *
 * Viết tay thay vì dùng CLI của shadcn/ui — lý do: không cần mạng lúc cài,
 * không thêm phụ thuộc, và toàn bộ mã nằm trong dự án nên sửa được tuỳ ý.
 * Nếu về sau cần thành phần phức tạp hơn (combobox, date picker), lúc đó
 * hãy chạy `npx shadcn@latest add ...` — hai cách dùng chung quy ước Tailwind
 * nên ghép được với nhau.
 */
import * as React from 'react'
import { cn } from '@/lib/cn'

// ─────────────────────────── Button ───────────────────────────
type BtnVariant = 'primary' | 'default' | 'ghost' | 'danger' | 'success'
type BtnSize = 'sm' | 'md'

const BTN_VARIANT: Record<BtnVariant, string> = {
  primary: 'bg-brand text-white border-brand hover:bg-brand-dark',
  default: 'bg-white text-[#33445F] border-[#CBD5E4] hover:bg-[#F7F9FC]',
  ghost:   'bg-transparent text-ink-soft border-transparent hover:bg-black/5',
  danger:  'bg-white text-[#B33520] border-[#E0AFA3] hover:bg-[#FEF6F3]',
  success: 'bg-[#128A52] text-white border-[#128A52] hover:bg-[#0E6E41]',
}
const BTN_SIZE: Record<BtnSize, string> = {
  sm: 'h-8 px-3 text-[12.5px] gap-1.5',
  md: 'h-9 px-4 text-[13px] gap-2',
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: BtnVariant
  size?: BtnSize
  loading?: boolean
}

export function Button({ variant = 'default', size = 'md', loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md border font-semibold whitespace-nowrap',
        'transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        BTN_VARIANT[variant], BTN_SIZE[size], className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner className="h-3.5 w-3.5" />}
      {children}
    </button>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn('inline-block animate-spin rounded-full border-2 border-current border-t-transparent', className ?? 'h-4 w-4')}
      aria-hidden
    />
  )
}

// ─────────────────────────── Input / Textarea / Select ───────────────────────────
const FIELD =
  'w-full rounded-md border bg-white px-2.5 py-1.5 text-[13px] text-ink placeholder:text-ink-faint ' +
  'focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand/50 disabled:bg-[#F7F9FC]'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(
  function Input({ className, invalid, ...rest }, ref) {
    return <input ref={ref} className={cn(FIELD, invalid ? 'border-[#E0A08D] bg-[#FEF6F3]' : 'border-[#D7DFEC]', className)} {...rest} />
  },
)

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={cn(FIELD, 'border-[#D7DFEC] leading-relaxed', className)} {...rest} />
  },
)

export function Select({ className, children, ...rest }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(FIELD, 'border-[#D7DFEC] pr-7 cursor-pointer', className)} {...rest}>
      {children}
    </select>
  )
}

export function Label({ className, children, ...rest }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn('block text-[11px] font-semibold uppercase tracking-wide text-ink-mute mb-1', className)} {...rest}>
      {children}
    </label>
  )
}

// ─────────────────────────── Badge ───────────────────────────
export type Tone = 'ok' | 'warn' | 'error' | 'running' | 'neutral' | 'brand'

const TONE: Record<Tone, string> = {
  ok:      'bg-[#E4F6EC] text-[#137A47]',
  warn:    'bg-[#FEF2DC] text-[#9A6206]',
  error:   'bg-[#FDE8E4] text-[#B33520]',
  running: 'bg-[#E4EDFD] text-[#2A56B8]',
  neutral: 'bg-[#EFF2F7] text-[#63728A]',
  brand:   'bg-brand-light text-brand-dark',
}

export function Badge({ tone = 'neutral', dot, children, className }: {
  tone?: Tone; dot?: boolean; children: React.ReactNode; className?: string
}) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold', TONE[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}

// ─────────────────────────── Card ───────────────────────────
export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('rounded-xl border border-line bg-white', className)}>{children}</div>
}

export function CardTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <h3 className="text-[13.5px] font-bold text-ink">{children}</h3>
      {action && <div className="ml-auto">{action}</div>}
    </div>
  )
}

// ─────────────────────────── Skeleton ───────────────────────────
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded bg-black/[0.07]', className)} />
}

// ─────────────────────────── Callout ───────────────────────────
export function Callout({ tone = 'brand', title, children, className }: {
  tone?: Exclude<Tone, 'neutral' | 'running'>; title?: string; children: React.ReactNode; className?: string
}) {
  const map = {
    ok:    'bg-[#F0FDF4] border-[#B9DEC9] text-[#2F5A45]',
    warn:  'bg-[#FFFAF0] border-[#EBD5A6] text-[#6B5220]',
    error: 'bg-[#FEF6F3] border-[#E5BFB2] text-[#7A4433]',
    brand: 'bg-brand-light border-[#C7D6F5] text-[#28407A]',
  } as const
  const titleColor = { ok: 'text-[#0F6E42]', warn: 'text-[#8A5D06]', error: 'text-[#A93318]', brand: 'text-brand-dark' } as const
  return (
    <div className={cn('rounded-lg border px-3.5 py-3 text-[12px] leading-relaxed', map[tone], className)}>
      {title && <div className={cn('mb-1 font-bold', titleColor[tone])}>{title}</div>}
      {children}
    </div>
  )
}
