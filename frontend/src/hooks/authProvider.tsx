/**
 * Trạng thái đăng nhập và phân quyền phía giao diện.
 *
 * Quyết định bảo mật: mã truy cập chỉ nằm trong BỘ NHỚ, không ghi vào
 * localStorage — nếu ghi, một lỗi XSS bất kỳ cũng đọc được token.
 *
 * Hệ quả là khi người dùng tải lại trang, bộ nhớ bị xoá. Vì vậy phải có bước
 * KHÔI PHỤC PHIÊN lúc khởi động: gọi /auth/refresh bằng cookie chỉ máy chủ
 * đọc được. Thiếu bước này thì mỗi lần nhấn F5 là bị đăng xuất.
 *
 * Lưu ý: việc ẩn hiện nút theo vai trò ở đây CHỈ để thuận tiện cho người dùng.
 * Quyết định thật sự luôn nằm ở backend — mỗi điểm cuối tự kiểm tra quyền.
 * Không bao giờ coi giao diện là lớp bảo vệ.
 */
import * as React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import type { RoleCode, User } from '@/api/types'
import { login as apiLogin, logout as apiLogout } from '@/api/auth'
import { USE_MOCK, api, setAccessToken } from '@/api/client'
import { Spinner } from '@/components/ui/primitives'

const MOCK_KEY = 'sme-ai-workforce:session'

interface AuthValue {
  user: User | null
  /** false khi còn đang thử khôi phục phiên — chưa được phép chuyển hướng. */
  ready: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  hasRole: (role: RoleCode) => boolean
}

const Ctx = React.createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null)
  const [ready, setReady] = React.useState(false)

  // ── Khôi phục phiên khi tải lại trang ──
  React.useEffect(() => {
    let cancelled = false
    const restore = async () => {
      try {
        if (USE_MOCK) {
          // Chế độ giả: lưu dấu phiên trong sessionStorage (mất khi đóng tab)
          const raw = sessionStorage.getItem(MOCK_KEY)
          if (raw) {
            setAccessToken('mock-token')
            if (!cancelled) setUser(JSON.parse(raw) as User)
          }
        } else {
          // Chế độ thật: đổi cookie làm mới lấy mã truy cập mới
          const res = await api.post<{ access_token: string; user: User }>('/auth/refresh')
          setAccessToken(res.access_token)
          if (!cancelled) setUser(res.user)
        }
      } catch {
        // Chưa đăng nhập hoặc phiên đã hết hạn — im lặng, để RequireAuth xử lý
      } finally {
        if (!cancelled) setReady(true)
      }
    }
    void restore()
    return () => { cancelled = true }
  }, [])

  const value: AuthValue = {
    user,
    ready,
    login: async (username, password) => {
      const u = await apiLogin(username, password)
      setUser(u)
      if (USE_MOCK) sessionStorage.setItem(MOCK_KEY, JSON.stringify(u))
    },
    logout: () => {
      void apiLogout().catch(() => undefined)
      setUser(null)
      if (USE_MOCK) sessionStorage.removeItem(MOCK_KEY)
    },
    hasRole: (role) => !!user?.roles.includes(role),
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthValue {
  const v = React.useContext(Ctx)
  if (!v) throw new Error('useAuth phải được dùng bên trong <AuthProvider>')
  return v
}

/**
 * Bọc các tuyến đường cần đăng nhập.
 * Trong lúc còn đang khôi phục phiên thì KHÔNG chuyển hướng — nếu không,
 * người dùng tải lại trang sẽ bị đá về màn hình đăng nhập rồi mới quay lại.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth()
  const loc = useLocation()

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center gap-2.5 text-ink-mute">
        <Spinner className="h-5 w-5" />
        <span className="text-[13px]">Đang khôi phục phiên làm việc…</span>
      </div>
    )
  }
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname + loc.search }} replace />
  return <>{children}</>
}
