/**
 * P-10 — Cấu hình (chỉ quản trị viên).
 *
 * Dùng khuôn DetailTabs: người dùng (từ /admin/users), kết nối mô hình (thử
 * kết nối thật qua /admin/llm/test), tình trạng hệ thống (từ /admin/metrics).
 */
import { useMutation, useQuery } from '@tanstack/react-query'
import { getMetrics, listUsers, testLlm } from '@/api/admin'
import type { RoleCode } from '@/api/types'
import { STALE } from '@/lib/query'
import { formatMoney } from '@/lib/format'
import { USE_MOCK } from '@/api/client'
import { PageHeader } from '@/components/shared/PageHeader'
import { DetailTabs } from '@/components/shared/DetailTabs'
import { ErrorState } from '@/components/shared/States'
import { Badge, Button, Callout, Card, CardTitle, Skeleton } from '@/components/ui/primitives'

const ROLE_LABEL: Record<RoleCode, string> = {
  USER: 'Kế toán viên',
  MANAGER: 'Quản lý',
  ADMIN: 'Quản trị viên',
}

export function SettingsPage() {
  const m = useQuery({ queryKey: ['metrics'], queryFn: getMetrics, staleTime: STALE.runs })
  const users = useQuery({ queryKey: ['admin-users'], queryFn: listUsers, staleTime: STALE.list })
  const llm = useMutation({ mutationFn: testLlm })

  const llmState = llm.data ? (llm.data.ok ? 'ok' : 'down') : m.data?.llm_status

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
            key: 'llm', label: 'Kết nối mô hình',
            element: (
              <Card className="max-w-2xl p-4">
                <CardTitle action={
                  <Button size="sm" loading={llm.isPending} onClick={() => llm.mutate()}>Kiểm tra kết nối</Button>
                }>
                  Máy chủ mô hình
                </CardTitle>
                <Row label="Trạng thái" value={
                  <Badge tone={llmState === 'ok' ? 'ok' : llmState === 'degraded' ? 'warn' : 'error'} dot>
                    {llmState === 'ok' ? 'Hoạt động bình thường' : llmState === 'degraded' ? 'Chập chờn' : 'Không phản hồi'}
                  </Badge>
                } />
                <Row label="Mô hình" value={<span className="font-mono">{llm.data?.model ?? '— (bấm Kiểm tra kết nối)'}</span>} />
                <Row label="Điểm cuối" value={<span className="font-mono text-[11.5px]">{llm.data?.base_url ?? '—'}</span>} />
                <Row label="Độ trễ lần thử" value={llm.data ? `${formatMoney(llm.data.latency_ms)} ms` : '—'} />
                <Row label="Giới hạn ảnh" value="Cạnh dài 1280 px · tối đa 1.638.400 điểm ảnh" last />
                {llm.data?.error && (
                  <Callout tone="error" className="mt-3.5">{llm.data.error}</Callout>
                )}
                <Callout tone="brand" className="mt-3.5">
                  Đổi mô hình chỉ cần sửa hai biến <span className="font-mono">LLM_BASE_URL</span> và{' '}
                  <span className="font-mono">LLM_MODEL</span> trong tệp cấu hình rồi khởi động lại —
                  không phải sửa mã nguồn.
                </Callout>
              </Card>
            ),
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
