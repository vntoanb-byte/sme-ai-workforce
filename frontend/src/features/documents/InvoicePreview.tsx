/**
 * Khung xem ảnh chứng từ — cột trái của màn hình kiểm tra kết quả.
 *
 * Khi có tệp thật (chế độ backend thật), hiển thị ảnh gốc qua thẻ <img>.
 * Khi chạy ở chế độ dữ liệu giả, dựng lại một hoá đơn giá trị gia tăng theo
 * đúng bố cục mẫu Việt Nam để bạn thử được luồng đối chiếu ngay, không cần
 * chuẩn bị ảnh.
 *
 * Lưu ý: bản dựng lại này CỐ Ý hiển thị con số ĐÚNG (lấy từ phép cộng), trong
 * khi cột phải hiển thị con số MÔ HÌNH ĐỌC ĐƯỢC. Chênh lệch giữa hai bên chính
 * là thứ người kiểm tra cần phát hiện.
 */
import type { InvoiceData } from '@/api/types'
import { formatDate, formatMoney } from '@/lib/format'

export function InvoicePreview({ data, fileUrl }: { data: InvoiceData; fileUrl?: string }) {
  if (fileUrl) {
    return (
      <img
        src={fileUrl}
        alt="Ảnh chứng từ gốc"
        className="mx-auto max-w-full rounded bg-white shadow-lg"
      />
    )
  }

  // Giá trị ĐÚNG theo phép cộng — đây là thứ in trên tờ hoá đơn thật
  const lineSum = data.line_items.reduce((a, i) => a + i.amount, 0)
  const vat = Math.round((lineSum * data.totals.vat_rate) / 100)
  const grand = lineSum + vat

  return (
    <div
      className="mx-auto w-[400px] bg-white px-6 py-5 text-[9.5px] leading-[1.55] text-[#2A2A2A] shadow-[0_2px_12px_rgba(0,0,0,0.16)]"
      style={{ transform: 'rotate(-0.6deg)' }}
    >
      <div className="mb-2.5 border-b-[1.5px] border-[#333] pb-2 text-center">
        <p className="text-[13px] font-bold tracking-wide">HOÁ ĐƠN GIÁ TRỊ GIA TĂNG</p>
        <p className="mt-0.5 text-[8.5px] text-[#666]">
          Ký hiệu: {data.invoice_form ?? '—'} · Số: {data.invoice_no}
        </p>
        <p className="text-[8.5px] text-[#666]">
          Ngày {formatDate(data.issue_date).replaceAll('/', ' tháng ').replace(/ tháng (\d{4})$/, ' năm $1')}
        </p>
      </div>

      <p><b>Đơn vị bán hàng:</b> {data.seller.name.toUpperCase()}</p>
      <p><b>Mã số thuế:</b> {data.seller.tax_code ? spaced(correctTaxCode(data.seller.tax_code)) : '—'}</p>
      <p className="mb-2"><b>Địa chỉ:</b> {data.seller.address ?? '—'}</p>

      {/* NOTE (TASK-007): backend thật (schemas/invoice.py) trả buyer=null khi
          hoá đơn không ghi thông tin bên mua (thực tế thường gặp, vd. bán lẻ)
          — mock trước đây luôn có sẵn buyer nên chưa lộ ca này. */}
      <p><b>Đơn vị mua hàng:</b> {(data.buyer?.name ?? '').toUpperCase() || '—'}</p>
      <p className="mb-2.5"><b>Mã số thuế:</b> {data.buyer?.tax_code ? spaced(data.buyer.tax_code) : '—'}</p>

      <table className="mb-2 w-full border-collapse text-[8.5px]">
        <thead>
          <tr className="bg-[#F0F0F0]">
            <Th className="w-7 text-center">STT</Th>
            <Th>Tên hàng hoá</Th>
            <Th className="w-10 text-center">ĐVT</Th>
            <Th className="w-9 text-center">SL</Th>
            <Th className="w-[62px] text-right">Đơn giá</Th>
            <Th className="w-[70px] text-right">Thành tiền</Th>
          </tr>
        </thead>
        <tbody>
          {data.line_items.map((it) => (
            <tr key={it.line_no}>
              <Td className="text-center">{it.line_no}</Td>
              <Td>{it.description}</Td>
              <Td className="text-center">{it.unit}</Td>
              <Td className="text-center">{it.quantity}</Td>
              <Td className="text-right">{formatMoney(it.unit_price)}</Td>
              <Td className="text-right">{formatMoney(it.amount)}</Td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="text-right leading-[1.7]">
        <p><b>Cộng tiền hàng: {formatMoney(lineSum)}</b></p>
        <p>Thuế suất GTGT: {data.totals.vat_rate}% · Tiền thuế: {formatMoney(vat)}</p>
        <p className="mt-1 inline-block bg-[#FFF0B8] px-1 py-0.5 text-[10.5px] font-bold">
          Tổng thanh toán: {formatMoney(grand)}
        </p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-center text-[8px] text-[#777]">
        <div><p className="italic">Người mua hàng</p><p className="mt-6">(Ký, ghi rõ họ tên)</p></div>
        <div><p className="italic">Người bán hàng</p><p className="mt-6">(Ký, ghi rõ họ tên)</p></div>
      </div>
    </div>
  )
}

function Th({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <th className={`border border-[#999] px-1 py-[3px] text-left text-[8px] font-semibold text-[#333] ${className}`}>{children}</th>
}
function Td({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`border border-[#999] px-1 py-[3px] ${className}`}>{children}</td>
}

/** Trên tờ hoá đơn thật, mã số thuế luôn là chữ số — dùng để tạo chênh lệch với bản mô hình đọc sai. */
function correctTaxCode(s: string): string {
  return s.replace(/[IiLl]/g, '1').replace(/[Oo]/g, '0').replace(/[Ss]/g, '5').replace(/[Bb]/g, '8')
}

/** Mã số thuế trên hoá đơn in cách nhau từng chữ số. */
function spaced(s: string): string {
  return s.split('').join(' ')
}
