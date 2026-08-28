/**
 * Biểu mẫu dữ liệu hoá đơn — cột phải của màn hình kiểm tra kết quả (P-06).
 *
 * Hai điểm thiết kế đáng chú ý:
 *
 * 1. Trường vi phạm quy tắc được tô nền cảnh báo kèm dòng giải thích CỤ THỂ
 *    ngay bên dưới — nêu rõ phép tính, không chỉ nói "sai". Người kiểm tra
 *    phải hiểu ngay vì sao bị đánh dấu mà không cần hỏi ai.
 *
 * 2. Tổng được tính lại theo thời gian thực khi người dùng sửa dòng hàng, để
 *    thấy ngay tác động của chỉnh sửa. Con số tính lại hiện cạnh ô nhập chứ
 *    KHÔNG tự ghi đè — quyết định vẫn thuộc về con người.
 */
import * as React from 'react'
import { Plus, Trash2, Wand2 } from 'lucide-react'
import type { InvoiceData, QCResult } from '@/api/types'
import { formatMoney, parseMoney } from '@/lib/format'
import { Input, Label } from '@/components/ui/primitives'
import { cn } from '@/lib/cn'

interface Props {
  data: InvoiceData
  qc: QCResult[]
  onChange: (next: InvoiceData) => void
}

export function InvoiceForm({ data, qc, onChange }: Props) {
  /** Tra thông báo lỗi theo tên trường, ví dụ 'totals.total'. */
  const errorOf = (field: string): string | null =>
    qc.find((r) => !r.passed && r.field === field)?.message ?? null

  const set = <K extends keyof InvoiceData>(key: K, value: InvoiceData[K]) =>
    onChange({ ...data, [key]: value })

  // Giá trị tính lại từ dòng hàng — dùng để đối chiếu, không tự ghi đè
  const lineSum = data.line_items.reduce((a, i) => a + (i.amount || 0), 0)
  const expectedTotal = (data.totals.subtotal || 0) + (data.totals.vat_amount || 0)
  const subtotalMismatch = Math.abs(lineSum - data.totals.subtotal) > 1
  const totalMismatch = Math.abs(expectedTotal - data.totals.total) > 1

  const updateLine = (idx: number, patch: Partial<InvoiceData['line_items'][number]>) => {
    const items = data.line_items.map((it, i) => {
      if (i !== idx) return it
      const next = { ...it, ...patch }
      // Tự tính lại thành tiền khi người dùng sửa số lượng hoặc đơn giá
      if ('quantity' in patch || 'unit_price' in patch) {
        next.amount = Math.round(next.quantity * next.unit_price)
      }
      return next
    })
    onChange({ ...data, line_items: items })
  }

  const addLine = () =>
    onChange({
      ...data,
      line_items: [
        ...data.line_items,
        { line_no: data.line_items.length + 1, description: '', unit: '', quantity: 0, unit_price: 0, amount: 0 },
      ],
    })

  const removeLine = (idx: number) =>
    onChange({
      ...data,
      line_items: data.line_items.filter((_, i) => i !== idx).map((it, i) => ({ ...it, line_no: i + 1 })),
    })

  return (
    <div className="flex flex-col gap-3.5">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Số hoá đơn" error={errorOf('invoice_no')}>
          <Input className="font-mono" value={data.invoice_no} invalid={!!errorOf('invoice_no')}
                 onChange={(e) => set('invoice_no', e.target.value)} />
        </Field>
        <Field label="Ngày lập" error={errorOf('issue_date')}>
          <Input type="date" value={data.issue_date} invalid={!!errorOf('issue_date')}
                 onChange={(e) => set('issue_date', e.target.value)} />
        </Field>
      </div>

      <Field label="Đơn vị bán" error={errorOf('seller.name')}>
        <Input value={data.seller.name} onChange={(e) => set('seller', { ...data.seller, name: e.target.value })} />
      </Field>

      <Field label="Mã số thuế bên bán" error={errorOf('seller.tax_code')}>
        <div className="flex gap-2">
          <Input
            className="font-mono"
            value={data.seller.tax_code}
            invalid={!!errorOf('seller.tax_code')}
            onChange={(e) => set('seller', { ...data.seller, tax_code: e.target.value })}
          />
          {/* Gợi ý sửa nhanh: thay ký tự chữ dễ nhầm bằng chữ số tương ứng */}
          {errorOf('seller.tax_code') && /[a-zA-Z]/.test(data.seller.tax_code) && (
            <button
              type="button"
              onClick={() => set('seller', { ...data.seller, tax_code: fixConfusable(data.seller.tax_code) })}
              className="flex shrink-0 items-center gap-1 rounded-md border border-[#CBD5E4] bg-white px-2.5 text-[11.5px] font-semibold text-brand hover:bg-brand-light"
              title="Thay I→1, O→0, S→5, B→8"
            >
              <Wand2 className="h-3.5 w-3.5" /> Sửa nhanh
            </button>
          )}
        </div>
      </Field>

      {/* ── Bảng dòng hàng ── */}
      <div>
        <div className="mb-1.5 flex items-center gap-2">
          <Label className="mb-0">Chi tiết hàng hoá ({data.line_items.length} dòng)</Label>
          <button onClick={addLine} type="button"
                  className="ml-auto flex items-center gap-1 text-[11.5px] font-semibold text-brand hover:underline">
            <Plus className="h-3.5 w-3.5" /> Thêm dòng
          </button>
        </div>
        <div className="overflow-hidden rounded-lg border border-line">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-line bg-[#FAFBFD] text-[10.5px] uppercase tracking-wide text-ink-mute">
                <th className="px-2 py-1.5 text-left font-semibold">Tên hàng</th>
                <th className="w-[62px] px-2 py-1.5 text-right font-semibold">SL</th>
                <th className="w-[96px] px-2 py-1.5 text-right font-semibold">Đơn giá</th>
                <th className="w-[110px] px-2 py-1.5 text-right font-semibold">Thành tiền</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {data.line_items.map((it, i) => (
                <tr key={i} className="border-b border-line-soft last:border-0">
                  <td className="px-1 py-1">
                    <CellInput value={it.description} onChange={(v) => updateLine(i, { description: v })} />
                  </td>
                  <td className="px-1 py-1">
                    <CellInput align="right" value={String(it.quantity)}
                               onChange={(v) => updateLine(i, { quantity: parseMoney(v) })} />
                  </td>
                  <td className="px-1 py-1">
                    <CellInput align="right" mono value={formatMoney(it.unit_price)}
                               onChange={(v) => updateLine(i, { unit_price: parseMoney(v) })} />
                  </td>
                  <td className="px-1 py-1">
                    <CellInput align="right" mono value={formatMoney(it.amount)}
                               onChange={(v) => updateLine(i, { amount: parseMoney(v) })} />
                  </td>
                  <td className="px-1 py-1 text-center">
                    <button onClick={() => removeLine(i)} type="button"
                            className="rounded p-1 text-ink-faint hover:bg-[#FDE8E4] hover:text-[#B33520]"
                            aria-label="Xoá dòng">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Tổng ── */}
      <div className="grid grid-cols-2 gap-3">
        <Field
          label="Cộng tiền hàng"
          error={errorOf('totals.subtotal')}
          hint={subtotalMismatch ? `Tổng dòng hàng đang là ${formatMoney(lineSum)}` : undefined}
        >
          <Input className="font-mono tabular-nums" invalid={subtotalMismatch || !!errorOf('totals.subtotal')}
                 value={formatMoney(data.totals.subtotal)}
                 onChange={(e) => set('totals', { ...data.totals, subtotal: parseMoney(e.target.value) })} />
        </Field>
        <Field label="Thuế suất">
          <Input value={`${data.totals.vat_rate}%`}
                 onChange={(e) => set('totals', { ...data.totals, vat_rate: parseMoney(e.target.value) })} />
        </Field>
        <Field label="Tiền thuế" error={errorOf('totals.vat_amount')}>
          <Input className="font-mono tabular-nums" value={formatMoney(data.totals.vat_amount)}
                 onChange={(e) => set('totals', { ...data.totals, vat_amount: parseMoney(e.target.value) })} />
        </Field>
        <Field
          label="Tổng thanh toán"
          error={errorOf('totals.total')}
          hint={totalMismatch ? `Phép cộng cho kết quả ${formatMoney(expectedTotal)}` : undefined}
        >
          <div className="flex gap-2">
            <Input className="font-mono tabular-nums font-semibold" invalid={totalMismatch || !!errorOf('totals.total')}
                   value={formatMoney(data.totals.total)}
                   onChange={(e) => set('totals', { ...data.totals, total: parseMoney(e.target.value) })} />
            {totalMismatch && (
              <button
                type="button"
                onClick={() => set('totals', { ...data.totals, total: expectedTotal })}
                className="shrink-0 rounded-md border border-[#CBD5E4] bg-white px-2.5 text-[11.5px] font-semibold text-brand hover:bg-brand-light"
                title={`Đặt thành ${formatMoney(expectedTotal)}`}
              >
                Lấy giá trị đúng
              </button>
            )}
          </div>
        </Field>
      </div>
    </div>
  )
}

function Field({ label, error, hint, children }: {
  label: string; error?: string | null; hint?: string; children: React.ReactNode
}) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
      {error && (
        <p className="mt-1.5 border-l-2 border-[#B33520] pl-2 text-[11px] italic leading-snug text-[#7A4433]">
          {error}
        </p>
      )}
      {!error && hint && (
        <p className="mt-1.5 border-l-2 border-[#D8A63D] pl-2 text-[11px] italic leading-snug text-[#8A5D06]">{hint}</p>
      )}
    </div>
  )
}

function CellInput({ value, onChange, align, mono }: {
  value: string; onChange: (v: string) => void; align?: 'right'; mono?: boolean
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'w-full rounded border border-transparent bg-transparent px-1.5 py-1 text-[12px] text-ink',
        'hover:border-[#D7DFEC] focus:border-brand/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand/20',
        align === 'right' && 'text-right tabular-nums',
        mono && 'font-mono',
      )}
    />
  )
}

/** Thay các ký tự chữ dễ bị đọc nhầm thành chữ số tương ứng. */
function fixConfusable(s: string): string {
  return s.replace(/[IiLl]/g, '1').replace(/[Oo]/g, '0').replace(/[Ss]/g, '5').replace(/[Bb]/g, '8')
}
