/**
 * Khung ứng dụng: thanh bên trái, thanh trên, vùng nội dung.
 * Mọi trang (trừ đăng nhập) đều nằm trong khung này.
 */
import * as React from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Bot, ChevronDown, FileText, Flag, LayoutGrid, ListOrdered, LogOut, Settings, Table2, Upload,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/cn'
import { useAuth } from '@/hooks/useAuth'
import { getMetrics } from '@/api/admin'
import { STALE } from '@/lib/query'
import { Badge } from '@/components/ui/primitives'
import { USE_MOCK } from '@/api/client'

interface NavItem {
  to: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  role?: 'MANAGER' | 'ADMIN'
  /** Hiển thị chấm đỏ với số bản ghi đang chờ xác nhận. */
  badgeKey?: 'needs_review'
  end?: boolean
}

const NAV: { section?: string; items: NavItem[] }[] = [
  {
    items: [
      { to: '/', label: 'Bảng điều khiển', icon: LayoutGrid, end: true },
      { to: '/documents', label: 'Chứng từ', icon: FileText },
      { to: '/documents?status=needs_review', label: 'Chờ xác nhận', icon: Flag, badgeKey: 'needs_review' },
      { to: '/runs', label: 'Lần chạy', icon: ListOrdered },
      { to: '/employees', label: 'Nhân viên AI', icon: Bot },
      { to: '/reports', label: 'Báo cáo', icon: Table2 },
    ],
  },
  {
    section: 'QUẢN TRỊ',
    items: [{ to: '/settings', label: 'Cấu hình', icon: Settings, role: 'ADMIN' }],
  },
]

export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-[#F4F6FA]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="thin-scroll flex min-h-0 flex-1 flex-col overflow-y-auto px-5 py-5 lg:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function Sidebar() {
  const { hasRole } = useAuth()
  const loc = useLocation()
  const { data: metrics } = useQuery({ queryKey: ['metrics'], queryFn: getMetrics, staleTime: STALE.runs })

  // NavLink không phân biệt được query string, nên tự xác định mục đang chọn
  const isActive = (item: NavItem) => {
    const [path, search] = item.to.split('?')
    if (loc.pathname !== path) return false
    if (search) return loc.search.includes(search)
    if (path === '/documents') return !loc.search.includes('needs_review')
    return true
  }

  return (
    <aside className="hidden w-[230px] shrink-0 flex-col bg-nav py-4 text-nav-text md:flex">
      <div className="mb-3.5 flex items-center gap-2.5 border-b border-nav-line px-4 pb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#4F7CFF] to-[#8B5CF6] text-[13px] font-bold text-white">
          AI
        </div>
        <div className="min-w-0">
          <p className="truncate text-[13.5px] font-bold text-white">SME AI Workforce</p>
          <p className="truncate text-[10px] text-[#7D8FAC]">Công ty TNHH TM An Phát</p>
        </div>
      </div>

      <nav className="flex-1 px-2.5">
        {NAV.map((group, gi) => {
          const items = group.items.filter((i) => !i.role || hasRole(i.role))
          if (items.length === 0) return null
          return (
            <div key={gi}>
              {group.section && (
                <p className="px-3 pb-1.5 pt-3.5 text-[10px] font-bold tracking-widest text-[#61738F]">
                  {group.section}
                </p>
              )}
              {items.map((item) => {
                const Icon = item.icon
                const count = item.badgeKey === 'needs_review' ? metrics?.needs_review_open ?? 0 : 0
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={cn(
                      'mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] transition-colors',
                      isActive(item) ? 'bg-nav-hover font-semibold text-white' : 'hover:bg-white/5',
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0 opacity-85" />
                    <span className="truncate">{item.label}</span>
                    {count > 0 && (
                      <span className="ml-auto rounded-full bg-[#E0533B] px-1.5 py-px text-[10.5px] font-bold text-white">
                        {count}
                      </span>
                    )}
                  </NavLink>
                )
              })}
            </div>
          )
        })}
      </nav>

      {USE_MOCK && (
        <div className="mx-2.5 rounded-lg border border-[#3C5686] bg-white/[0.04] px-3 py-2 text-[10.5px] leading-snug text-[#8FA3C4]">
          Đang chạy với <b className="text-[#C9D8F0]">dữ liệu giả</b>.
          Đặt <span className="font-mono">VITE_USE_MOCK=false</span> để gọi backend thật.
        </div>
      )}
    </aside>
  )
}

function Topbar() {
  const { user, logout } = useAuth()
  const [open, setOpen] = React.useState(false)
  const { data: metrics } = useQuery({ queryKey: ['metrics'], queryFn: getMetrics, staleTime: STALE.runs })

  const initials = (user?.full_name ?? '')
    .split(' ').slice(-2).map((w) => w[0] ?? '').join('').toUpperCase()

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-white px-5 lg:px-6">
      <span className="text-[12.5px] text-ink-mute md:hidden">SME AI Workforce</span>
      <div className="ml-auto flex items-center gap-3">
        {metrics && (
          <Badge tone={metrics.llm_status === 'ok' ? 'ok' : 'error'} dot className="hidden sm:inline-flex">
            {metrics.llm_status === 'ok' ? 'Máy chủ AI hoạt động' : 'Máy chủ AI có sự cố'}
          </Badge>
        )}
        <div className="relative">
          <button
            onClick={() => setOpen((v) => !v)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            className="flex items-center gap-2 rounded-lg px-1.5 py-1 hover:bg-black/5"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#D9E2F1] text-[11px] font-bold text-[#3B4E70]">
              {initials || '?'}
            </span>
            <span className="hidden text-[12.5px] font-medium text-ink sm:block">{user?.full_name}</span>
            <ChevronDown className="h-3.5 w-3.5 text-ink-faint" />
          </button>
          {open && (
            <div className="absolute right-0 top-full z-20 mt-1 w-56 rounded-lg border border-line bg-white py-1 shadow-lg">
              <div className="border-b border-line px-3 py-2">
                <p className="text-[12.5px] font-semibold text-ink">{user?.full_name}</p>
                <p className="text-[11px] text-ink-mute">{user?.email}</p>
                <p className="mt-1 text-[10.5px] text-ink-faint">Vai trò: {user?.roles.join(', ')}</p>
              </div>
              <button
                onClick={logout}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-[12.5px] text-ink-soft hover:bg-black/5"
              >
                <LogOut className="h-3.5 w-3.5" /> Đăng xuất
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
