/**
 * P-09 — Báo cáo.
 *
 * ĐỘ ƯU TIÊN THẤP NHẤT trong bảng index màn hình — có thể cắt hoàn toàn nếu
 * thiếu thời gian, vì người dùng vẫn xuất được dữ liệu từ trang danh sách
 * chứng từ. Giữ ở mức đơn giản, không đầu tư thêm.
 */
import * as React from 'react'
import { useMutation } from '@tanstack/react-query'
import { Download, Table2 } from 'lucide-react'
import { previewReport, type ReportParams } from '@/api/reports'
import { formatMoney } from '@/lib/format'
import { PageHeader } from '@/components/shared/PageHeader'
import { EmptyState } from '@/components/shared/States'
import { Button, Card, Input, Label, Select } from '@/components/ui/primitives'

const GROUPS: { value: ReportParams['group_by']; label: string }[] = [
  { value: 'seller', label: 'Theo nhà cung cấp' },
  { value: 'month', label: 'Theo tháng' },
  { value: 'vat_rate', label: 'Theo thuế suất' },
]

export function ReportPage() {
  const today = new Date()
  const first = new Date(today.getFullYear(), today.getMonth(), 1)
  const iso = (d: Date) => d.toISOString().slice(0, 10)

  const [from, setFrom] = React.useState(iso(first))
  const [to, setTo] = React.useState(iso(today))
  const [groupBy, setGroupBy] = React.useState<ReportParams['group_by']>('seller')

  const preview = useMutation({ mutationFn: () => previewReport({ from, to, group_by: groupBy }) })

  return (
    <>
      <PageHeader title="Báo cáo" subtitle="Tổng hợp chứng từ theo kỳ và kết xuất ra Excel hoặc PDF" />

      <Card className="mb-4 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-40">
            <Label htmlFor="from">Từ ngày</Label>
            <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div className="w-40">
            <Label htmlFor="to">Đến ngày</Label>
            <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
          <div className="w-52">
            <Label htmlFor="gb">Nhóm theo</Label>
            <Select id="gb" value={groupBy} onChange={(e) => setGroupBy(e.target.value as ReportParams['group_by'])}>
              {GROUPS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </Select>
          </div>
          <Button variant="primary" loading={preview.isPending} onClick={() => preview.mutate()}>
            <Table2 className="h-4 w-4" /> Xem trước
          </Button>
          {preview.data && (
            <Button className="ml-auto">
              <Download className="h-4 w-4" /> Tải về Excel
            </Button>
          )}
        </div>
      </Card>

      <Card className="overflow-hidden">
        {!preview.data ? (
          <EmptyState
            title="Chọn kỳ rồi bấm Xem trước"
            hint="Báo cáo tổng hợp số lượng chứng từ, tiền hàng, tiền thuế và tổng thanh toán theo tiêu chí bạn chọn."
          />
        ) : (
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="border-b border-line bg-[#FAFBFD] text-[11px] uppercase tracking-wide text-ink-mute">
                <th className="px-3 py-2.5 text-left font-semibold">
                  {GROUPS.find((g) => g.value === preview.data!.group_by)?.label.replace('Theo ', '')}
                </th>
                <th className="w-24 px-3 py-2.5 text-right font-semibold">Số CT</th>
                <th className="w-36 px-3 py-2.5 text-right font-semibold">Tiền hàng</th>
                <th className="w-32 px-3 py-2.5 text-right font-semibold">Tiền thuế</th>
                <th className="w-36 px-3 py-2.5 text-right font-semibold">Tổng thanh toán</th>
              </tr>
            </thead>
            <tbody>
              {preview.data.rows.map((r) => (
                <tr key={r.group} className="border-b border-line-soft">
                  <td className="px-3 py-2.5">{r.group}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{r.doc_count}</td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums">{formatMoney(r.subtotal)}</td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums">{formatMoney(r.vat_amount)}</td>
                  <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums">{formatMoney(r.total)}</td>
                </tr>
              ))}
              <tr className="bg-[#FAFBFD] font-bold">
                <td className="px-3 py-2.5" colSpan={4}>Tổng cộng</td>
                <td className="px-3 py-2.5 text-right font-mono tabular-nums">{formatMoney(preview.data.grand_total)}</td>
              </tr>
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}
