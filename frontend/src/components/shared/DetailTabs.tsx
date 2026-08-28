/**
 * KHUÔN 2 — Trang chi tiết có tab.
 *
 * Tab đang chọn được đồng bộ với query string (?tab=...), nên người dùng tải
 * lại trang không bị mất chỗ và chia sẻ được đường dẫn tới đúng tab.
 *
 * Dùng ở: chi tiết nhân viên AI (P-04) và cấu hình (P-10).
 */
import { useSearchParams } from 'react-router-dom'
import { cn } from '@/lib/cn'

export interface TabDef {
  key: string
  label: string
  badge?: number
  element: React.ReactNode
}

export function DetailTabs({ tabs, defaultTab }: { tabs: TabDef[]; defaultTab?: string }) {
  const [sp, setSp] = useSearchParams()
  const active = sp.get('tab') ?? defaultTab ?? tabs[0]?.key
  const current = tabs.find((t) => t.key === active) ?? tabs[0]

  const select = (key: string) => {
    const next = new URLSearchParams(sp)
    next.set('tab', key)
    setSp(next, { replace: true })
  }

  return (
    <div>
      <div className="mb-4 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => select(t.key)}
            className={cn(
              'relative -mb-px flex items-center gap-2 border-b-2 px-3.5 py-2 text-[13px] font-semibold transition-colors',
              t.key === current.key
                ? 'border-brand text-brand-dark'
                : 'border-transparent text-ink-mute hover:text-ink',
            )}
          >
            {t.label}
            {t.badge !== undefined && t.badge > 0 && (
              <span className="rounded-full bg-[#E0533B] px-1.5 py-px text-[10.5px] font-bold text-white">
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>
      {current?.element}
    </div>
  )
}
