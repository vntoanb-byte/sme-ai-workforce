/**
 * KHUÔN 3 — Bố cục hai cột có thanh kéo.
 *
 * Dùng ở màn hình kiểm tra kết quả (P-06) và chi tiết lần chạy (P-08).
 *
 * Với P-06, bố cục hai cột là bắt buộc chứ không phải thẩm mỹ: người kiểm tra
 * cần nhìn ảnh gốc và dữ liệu CÙNG LÚC để đối chiếu, không phải chuyển qua
 * lại giữa hai màn hình.
 *
 * Tỷ lệ người dùng chọn được ghi nhớ trong localStorage theo từng khoá.
 */
import * as React from 'react'
import { cn } from '@/lib/cn'

export function SplitView({ left, right, storageKey, defaultRatio = 0.5, minRatio = 0.25, maxRatio = 0.75 }: {
  left: React.ReactNode
  right: React.ReactNode
  storageKey: string
  defaultRatio?: number
  minRatio?: number
  maxRatio?: number
}) {
  const boxRef = React.useRef<HTMLDivElement>(null)
  const [ratio, setRatio] = React.useState<number>(() => {
    try {
      const v = localStorage.getItem(`split:${storageKey}`)
      return v ? Number(v) : defaultRatio
    } catch { return defaultRatio }
  })
  const dragging = React.useRef(false)

  React.useEffect(() => {
    try { localStorage.setItem(`split:${storageKey}`, String(ratio)) } catch { /* bỏ qua */ }
  }, [ratio, storageKey])

  React.useEffect(() => {
    const move = (e: MouseEvent) => {
      if (!dragging.current || !boxRef.current) return
      const r = boxRef.current.getBoundingClientRect()
      const next = (e.clientX - r.left) / r.width
      setRatio(Math.min(maxRatio, Math.max(minRatio, next)))
    }
    const up = () => {
      dragging.current = false
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [minRatio, maxRatio])

  return (
    <div ref={boxRef} className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row lg:gap-0">
      <div className="min-h-0 lg:pr-1.5" style={{ flexBasis: `${ratio * 100}%` }}>{left}</div>

      {/* Thanh kéo — ẩn trên màn hình hẹp vì lúc đó hai cột xếp chồng */}
      <div
        role="separator"
        aria-orientation="vertical"
        onMouseDown={() => {
          dragging.current = true
          document.body.style.userSelect = 'none'
          document.body.style.cursor = 'col-resize'
        }}
        className={cn(
          'hidden w-1.5 shrink-0 cursor-col-resize rounded-full bg-transparent',
          'hover:bg-brand/25 active:bg-brand/40 lg:block',
        )}
      />

      <div className="min-h-0 flex-1 lg:pl-1.5">{right}</div>
    </div>
  )
}
