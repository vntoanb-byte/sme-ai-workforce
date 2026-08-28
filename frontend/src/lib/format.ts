/**
 * Định dạng tiền tệ, ngày tháng và số theo quy ước Việt Nam.
 *
 * Quy ước: dấu chấm phân cách hàng nghìn, dấu phẩy phân cách thập phân,
 * ngày dạng dd/MM/yyyy. Toàn bộ dữ liệu từ backend dùng UTC dạng ISO-8601,
 * việc chuyển sang giờ Việt Nam chỉ làm ở tầng hiển thị này.
 */

const NF = new Intl.NumberFormat('vi-VN')

/** 12440000 → "12.440.000" */
export function formatMoney(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return NF.format(v)
}

/** 12440000 → "12.440.000 đ" */
export function formatMoneyUnit(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return NF.format(v) + ' đ'
}

/** "12.440.000" hoặc "12440000" → 12440000 */
export function parseMoney(s: string): number {
  const cleaned = s.replace(/[^\d,-]/g, '').replace(/\./g, '').replace(',', '.')
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : 0
}

export function formatNumber(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return NF.format(v)
}

/** "2026-08-22" hoặc ISO đầy đủ → "22/08/2026" */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`
}

/** ISO → "22/08/2026 09:12" */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${formatDate(iso)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** ISO → "09:12:04" — dùng cho khung nhật ký */
export function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** ISO → "hôm nay 08:00" · "hôm qua 17:30" · "23/08 09:00" */
export function formatRelativeDay(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const today = new Date()
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diffDays = Math.round((startOf(today) - startOf(d)) / 86_400_000)
  const hhmm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (diffDays === 0) return `Hôm nay ${hhmm}`
  if (diffDays === 1) return `Hôm qua ${hhmm}`
  if (diffDays === -1) return `Ngày mai ${hhmm}`
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${hhmm}`
}

/** 15400 → "15,4 giây" · 92000 → "1 phút 32 giây" */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms} ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1).replace('.', ',')} giây`
  const m = Math.floor(s / 60)
  const rest = Math.round(s % 60)
  return rest === 0 ? `${m} phút` : `${m} phút ${rest} giây`
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}
