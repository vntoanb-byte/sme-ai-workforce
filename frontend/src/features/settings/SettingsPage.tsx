/**
 * P-10 — Cấu hình.
 *
 * Dùng khuôn DetailTabs. Có thể rút gọn xuống còn tab Người dùng nếu thiếu
 * thời gian; hai tab kia thay bằng sửa trực tiếp tệp biến môi trường.
 */
import { useQuery } from '@tanstack/react-query'
import { getMetrics } from '@/api/admin'
import { STALE } from '@/lib/query'
import { USE_MOCK } from '@/api/client'
import { PageHeader } from '@/components/shared/PageHeader'
import { DetailTabs } from '@/components/shared/DetailTabs'
import { Badge, Button, Callout, Card, CardTitle } from '@/components/ui/primitives'

const USERS = [
  { name: 'Nguyễn Thị Hoa', username: 'ketoan', email: 'hoa@anphat.vn', roles: 'Kế toán viên' },
  { name: 'Trần Thu Hương', username: 'quanly', email: 'huong@anphat.vn', roles: 'Kế toán viên, Quản lý' },
  { name: 'Quản trị hệ thống', username: 'admin', email: 'admin@anphat.vn', roles: 'Quản trị viên' },
]

export function SettingsPage() {
  const m = useQuery({ queryKey: ['metrics'], queryFn: getMetrics, staleTime: STALE.runs })

  return (
    <>
      <PageHeader title="Cấu hình" subtitle="Người dùng, kết nối mô hình và tình trạng hệ thống" />
      <DetailTabs
        tabs={[
          {
            key: 'users', label: 'Người dùng',
            element: (
              <Card className="overflow-hidden">
                <table className="w-full text-[12.5px]">
                  <thead>
                    <tr className="border-b border-line bg-[#FAFBFD] text-[11px] uppercase tracking-wide text-ink-mute">
                      <th className="px-3 py-2.5 text-left font-semibold">Họ tên</th>
                      <th className="w-32 px-3 py-2.5 text-left font-semibold">Tên đăng nhập</th>
                      <th className="px-3 py-2.5 text-left font-semibold">Thư điện tử</th>
                      <th className="w-60 px-3 py-2.5 text-left font-semibold">Vai trò</th>
                    </tr>
                  </thead>
                  <tbody>
                    {USERS.map((u) => (
                      <tr key={u.username} className="border-b border-line-soft last:border-0">
                        <td className="px-3 py-2.5 font-semibold text-ink">{u.name}</td>
                        <td className="px-3 py-2.5 font-mono text-ink-soft">{u.username}</td>
                        <td className="px-3 py-2.5 text-ink-soft">{u.email}</td>
                        <td className="px-3 py-2.5 text-ink-soft">{u.roles}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            ),
          },
          {
            key: 'llm', label: 'Kết nối mô hình',
            element: (
              <Card className="max-w-2xl p-4">
                <CardTitle action={<Button size="sm">Kiểm tra kết nối</Button>}>Máy chủ mô hình</CardTitle>
                <Row label="Trạng thái" value={
                  <Badge tone={m.data?.llm_status === 'ok' ? 'ok' : 'error'} dot>
                    {m.data?.llm_status === 'ok' ? 'Hoạt động bình thường' : 'Không phản hồi'}
                  </Badge>
                } />
                <Row label="Mô hình" value={<span className="font-mono">Qwen3-VL-8B</span>} />
                <Row label="Điểm cuối" value={<span className="font-mono text-[11.5px]">http://vllm:8000/v1</span>} />
                <Row label="Giới hạn ảnh" value="Cạnh dài 1280 px · tối đa 1.638.400 điểm ảnh" last />
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
                <Row label="Tiến trình xử lý nền" value="1 tiến trình" />
                <Row label="Sao lưu gần nhất" value="Hôm nay 02:00" last />
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
