/** P-01 — Đăng nhập. */
import * as React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Button, Callout, Input, Label } from '@/components/ui/primitives'
import { BrandMark } from '@/components/shared/BrandMark'
import { useAuth } from '@/hooks/useAuth'
import { ApiError, USE_MOCK } from '@/api/client'

export function LoginPage() {
  const { login, user, ready } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const from = (loc.state as { from?: string } | null)?.from ?? '/'

  const [username, setUsername] = React.useState('ketoan')
  const [password, setPassword] = React.useState('123456')
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => { if (ready && user) nav(from, { replace: true }) }, [ready, user])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username, password)
      nav(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Đăng nhập thất bại.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-[380px]">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-nav shadow-sm">
            <BrandMark size={38} />
          </div>
          <div className="text-center">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-ink-faint">
              Buồng lái vận hành
            </p>
            <h1 className="mt-1 text-[19px] font-bold text-ink">SME AI Workforce</h1>
            <p className="mt-0.5 text-[12.5px] text-ink-mute">Công ty TNHH TM An Phát</p>
          </div>
        </div>

        <form onSubmit={submit} className="rounded-xl border border-line bg-white p-5 shadow-sm">
          <div className="mb-3.5">
            <Label htmlFor="u">Tên đăng nhập</Label>
            <Input id="u" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
          </div>
          <div className="mb-4">
            <Label htmlFor="p">Mật khẩu</Label>
            <Input id="p" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>

          {error && <Callout tone="error" className="mb-3.5">{error}</Callout>}

          <Button type="submit" variant="primary" loading={loading} className="w-full">
            Đăng nhập
          </Button>

          <p className="mt-3.5 text-center text-[11.5px] text-ink-faint">
            Hệ thống chạy trong mạng nội bộ doanh nghiệp
          </p>
        </form>

        {USE_MOCK && (
          <Callout tone="brand" title="Chế độ dữ liệu giả" className="mt-4">
            Đăng nhập bằng <b>ketoan</b>, <b>quanly</b> hoặc <b>admin</b> — mật khẩu đều là <b>123456</b>.
            Mỗi tài khoản có bộ quyền khác nhau để bạn thử giao diện.
          </Callout>
        )}
      </div>
    </div>
  )
}
