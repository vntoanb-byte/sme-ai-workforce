import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

/** Đầu trang: nút quay lại (tuỳ chọn), tiêu đề, mô tả phụ, và vùng hành động bên phải. */
export function PageHeader({ title, subtitle, back, actions }: {
  title: string
  subtitle?: string
  back?: string
  actions?: React.ReactNode
}) {
  const nav = useNavigate()
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      {back && (
        <button
          onClick={() => nav(back)}
          className="rounded-md border border-[#CBD5E4] bg-white p-1.5 text-ink-soft hover:bg-[#F7F9FC] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
          aria-label="Quay lại"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
      )}
      <div className="min-w-0">
        <h1 className="truncate text-[17px] font-bold text-ink">{title}</h1>
        {subtitle && <p className="mt-0.5 text-[12.5px] text-ink-mute">{subtitle}</p>}
      </div>
      {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
