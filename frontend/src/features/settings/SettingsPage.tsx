/**
 * P-10 — Cấu hình (chỉ quản trị viên).
 *
 * Dùng khuôn DetailTabs: người dùng (từ /admin/users), mô hình AI (gắn máy chủ
 * mô hình và khoá API — LlmSettings), tình trạng hệ thống (từ /admin/metrics).
 */
import { useQuery } from '@tanstack/react-query'
import { getMetrics, listUsers } from '@/api/admin'
import type { RoleCode } from '@/api/types'
import { STALE } from '@/lib/query'
import { formatMoney } from '@/lib/format'
import { USE_MOCK } from '@/api/client'
import { PageHeader } from '@/components/shared/PageHeader'
import { DetailTabs } from '@/components/shared/DetailTabs'
import { ErrorState } from '@/components/shared/States'
import { Badge, Card, CardTitle, Skeleton } from '@/components/ui/primitives'
import { LlmSettings } from './LlmSettings'

const ROLE_LABEL: Record<RoleCode, string> = {
  USER: 'Kế toán viên',
  MANAGER: 'Quản lý',
  ADMIN: 'Quản trị viên',
}

export function SettingsPage() {
  const m = useQuery({ queryKey: ['metrics'], queryFn: getMetrics, staleTime: STALE.runs })
  const users = useQuery({ queryKey: ['admin-users'], queryFn: listUsers, staleTime: STALE.list })

  return (
    <>
      <PageHeader title="Cấu hình" subtitle="Người dùng, kết nối mô hình và tình trạng hệ thống" />
      <DetailTabs
        tabs={[
          {
            key: 'users', label: 'Người dùng',
            element: users.isError ? (
              <ErrorState error={users.error} onRetry={() => users.refetch()} />
            ) : (
              <Card className="overflow-hidden">
                {users.isLoading ? (
                  <Skeleton className="h-40 w-full" />
                ) : (
                  <table className="w-full text-[12.5px]">
                    <thead>
                      <tr className="border-b border-line bg-[#FAFBFD] text-[11px] uppercase tracking-wide text-ink-mute">
                        <th className="px-3 py-2.5 text-left font-semibold">Họ tên</th>
                        <th className="w-32 px-3 py-2.5 text-left font-semibold">Tên đăng nhập</th>
                        <th className="px-3 py-2.5 text-left font-semibold">Thư điện tử</th>
                        <th className="w-60 px-3 py-2.5 text-left font-semibold">Vai trò</th>
                        <th className="w-28 px-3 py-2.5 text-left font-semibold">Trạng thái</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(users.data ?? []).map((u) => (
                        <tr key={u.id} className="border-b border-line-soft last:border-0">
                          <td className="px-3 py-2.5 font-semibold text-ink">{u.full_name}</td>
                          <td className="px-3 py-2.5 font-mono text-ink-soft">{u.username}</td>
                          <td className="px-3 py-2.5 text-ink-soft">{u.email}</td>
                          <td className="px-3 py-2.5 text-ink-soft">{u.roles.map((r) => ROLE_LABEL[r]).join(', ')}</td>
                          <td className="px-3 py-2.5">
                            <Badge tone={u.is_active ? 'ok' : 'error'} dot>{u.is_active ? 'Hoạt động' : 'Đã khoá'}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Card>
            ),
          },
          {
            key: 'llm', label: 'Mô hình AI',
            element: <LlmSettings status={m.data?.llm_status} />,
          },
          {
            key: 'system', label: 'Hệ thống',
            element: (
              <Card className="max-w-2xl p-4">
                <CardTitle>Tình trạng hệ thống</CardTitle>
                <Row label="Chế độ dữ liệu" value={
                  USE_MOCK
                    ? <Badge tone="warn" dot>Dữ liệu giả (chưa nối backend)</Badge>
                    : <Badge tone="ok" dot>Đang nối backend thật</Badge>
                } />
                <Row label="Cơ sở dữ liệu" value={<span className="font-mono">SQLite · chế độ WAL</span>} />
                <Row label={`Lần chạy (${m.data?.period_label ?? 'tháng này'})`} value={String(m.data?.runs_this_month ?? '—')} />
                <Row label="Độ trễ mô hình trung bình" value={
                  m.data?.avg_llm_latency_ms != null ? `${(m.data.avg_llm_latency_ms / 1000).toFixed(1).replace('.', ',')} giây` : '—'
                } />
                <Row label="Token đã dùng trong tháng" value={formatMoney(m.data?.tokens_this_month)} last />
              </Card>
            ),
          },
        ]}
      />
    </>
  )
}

function Row({ label, value, last }: { label: string; value: React.ReactNode; last?: boolean }) {
  return (
    <div className={`flex items-center justify-between py-2 text-[12.5px] ${last ? '' : 'border-b border-line-soft'}`}>
      <span className="text-ink-mute">{label}</span>
      <span className="font-semibold text-ink">{value}</span>
    </div>
  )
}
