/**
 * Cửa sổ (Dialog) và ngăn kéo (Drawer).
 *
 * Đây là hai thành phần thực thi nguyên tắc chống phình số 2 trong kế hoạch:
 * "không phải cái gì cũng cần một tuyến đường". Wizard tạo nhân viên AI và
 * ngăn nạp chứng từ đều dùng ở đây, nên không chiếm route nào.
 */
import * as React from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cn } from '@/lib/cn'

function useEscape(open: boolean, onClose: () => void) {
  React.useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    // Khoá cuộn nền khi lớp phủ đang mở
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', h)
      document.body.style.overflow = prev
    }
  }, [open, onClose])
}

interface OverlayProps {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: string
  children: React.ReactNode
  footer?: React.ReactNode
  /** Chiều rộng tối đa của cửa sổ. */
  width?: string
}

export function Dialog({ open, onClose, title, subtitle, children, footer, width = 'max-w-3xl' }: OverlayProps) {
  useEscape(open, onClose)
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/35 p-4 sm:p-8">
      <div className={cn('w-full rounded-xl border border-line bg-white shadow-2xl', width)} role="dialog" aria-modal="true">
        <header className="flex items-start gap-3 border-b border-line px-5 py-3.5">
          <div>
            <h2 className="text-[15px] font-bold text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 text-[12px] text-ink-mute">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="ml-auto rounded p-1 text-ink-faint hover:bg-black/5 hover:text-ink" aria-label="Đóng">
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="px-5 py-4">{children}</div>
        {footer && <footer className="flex items-center gap-2 border-t border-line px-5 py-3">{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}

export function Drawer({ open, onClose, title, subtitle, children, footer, width = 'max-w-lg' }: OverlayProps) {
  useEscape(open, onClose)
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end bg-black/35">
      <aside className={cn('flex h-full w-full flex-col border-l border-line bg-white shadow-2xl', width)} role="dialog" aria-modal="true">
        <header className="flex items-start gap-3 border-b border-line px-5 py-3.5">
          <div>
            <h2 className="text-[15px] font-bold text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 text-[12px] text-ink-mute">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="ml-auto rounded p-1 text-ink-faint hover:bg-black/5 hover:text-ink" aria-label="Đóng">
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="thin-scroll flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="flex items-center gap-2 border-t border-line px-5 py-3">{footer}</footer>}
      </aside>
    </div>,
    document.body,
  )
}
