/**
 * P-05 — Danh sách chứng từ.
 *
 * QUAN TRỌNG: "Hàng đợi chờ xác nhận" KHÔNG phải một màn hình riêng — nó chính
 * là danh sách này với bộ lọc status=needs_review. Nhận ra điều đó bỏ được
 * trọn một màn hình mà không mất chức năng nào, và người dùng còn chia sẻ được
 * đường dẫn kèm bộ lọc.
 *
 * NGÔN NGỮ HÌNH ẢNH của riêng trang này: đây là "hộp thư đến" của công việc —
 * người dùng lướt qua nhiều dòng để biết dòng nào cần xử lý NGAY, dòng nào đã
 * xong xuôi. Khác với trang chi tiết (P-06, chủ đề "tờ giấy thật" đối chiếu
 * 1-1), ở đây vai trò là QUÉT NHANH hàng chục dòng cùng lúc — nên trạng thái
 * phải đọc được bằng mắt trước khi đọc chữ:
 *   - Chờ xác nhận  → dòng "nổi": dải màu + nền ám vàng nhạt + tên tệp đậm,
 *     giống email chưa đọc.
 *   - Lỗi           → dải đỏ ở mép trái, cần chú ý nhưng không phải việc của
 *     người dùng xử lý thủ công ngay.
 *   - Đang xử lý    → chấm xanh nhấp nháy nhẹ cạnh tên tệp — báo hiệu "đang
 *     sống", máy đang làm việc, không cần bận tâm.
 *   - Đạt / Đã từ chối → im lặng, chữ nhạt hẳn đi — đã xong, không cần nhìn lại.
 * Toàn bộ màu dùng lại NGUYÊN XI hai mã hex đã tồn tại sẵn trong chính file
 * này trước khi sửa (#B4700B cho cảnh báo, #B33520 cho PDF/lỗi) — không phát
 * sinh màu mới, chỉ tổ chức lại cách dùng để làm rõ mức độ ưu tiên.
 */
import * as React from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, FileImage, FileText, Inbox, Upload } from 'lucide-react'
import { listDocuments } from '@/api/documents'
import type { DocStatus, DocumentRow } from '@/api/types'
import { formatDate, formatMoney, formatRelativeDay } from '@/lib/format'
import { cn } from '@/lib/cn'
import { usePagedQuery } from '@/hooks/usePagedQuery'
import { PageHeader } from '@/components/shared/PageHeader'
import { DataTable, type Column, type FilterDef } from '@/components/shared/DataTable'
import { DocStatusBadge } from '@/components/shared/StatusBadge'
import { Button, Callout } from '@/components/ui/primitives'
import { UploadDrawer } from './UploadDrawer'

const FILTER_KEYS = ['status', 'q']

const filters: FilterDef[] = [
  { key: 'q', kind: 'search', placeholder: 'Tìm theo số hoá đơn hoặc nhà cung cấp…' },
  {
    key: 'status', kind: 'select', label: 'Trạng thái',
    options: [
      { value: 'needs_review', label: 'Chờ xác nhận' },
      { value: 'ok', label: 'Đạt' },
      { value: 'processing', label: 'Đang xử lý' },
      { value: 'failed', label: 'Lỗi' },
    ],
  },
]

/**
 * Dải màu ưu tiên ở mép trái ô "Tệp" + nền ám nhẹ cho trạng thái cần chú ý.
 * Chỉ hai trạng thái thật sự cần "giật mình": chờ xác nhận (việc của người
 * dùng) và lỗi (việc của hệ thống nhưng cần biết). "Đang xử lý" dùng luôn màu
 * brand có sẵn trong tailwind.config.ts (không phải màu mới). "Đạt" và
 * "Đã từ chối" cố tình không có dải màu — im lặng nghĩa là không cần nhìn.
 */
const STATUS_ACCENT: Partial<Record<DocStatus, { stripe: string; wash?: string }>> = {
  needs_review: { stripe: 'bg-[#B4700B]', wash: 'bg-[#B4700B]/[0.07]' },
  failed: { stripe: 'bg-[#B33520]' },
  processing: { stripe: 'bg-brand' },
}

/** Độ đậm/nhạt của tên tệp theo trạng thái — mô phỏng "đã đọc / chưa đọc". */
function filenameTone(status: DocStatus) {
  if (status === 'needs_review') return 'font-semibold text-ink'
  if (status === 'ok' || status === 'rejected') return 'text-ink-faint'
  return 'text-ink-soft'
}

export function DocumentListPage() {
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const state = usePagedQuery(FILTER_KEYS)
  const [uploadOpen, setUploadOpen] = React.useState(false)

  const reviewMode = state.filters.status === 'needs_review'

  const q = useQuery({
    queryKey: ['documents', state.filters, state.page],
    queryFn: () => listDocuments({ ...state.filters, page: state.page, page_size: state.pageSize }),
  })

  const columns: Column<DocumentRow>[] = [
    {
      key: 'file', header: 'Tệp', width: 'w-[240px]',
      render: (d) => {
        const accent = STATUS_ACCENT[d.status]
        return (
          // Huỷ đúng phần đệm mà DataTable đặt trên <td> (px-3 py-2.5) bằng
          // margin âm rồi đắp lại padding tương đương, để div này phủ trọn ô
          // và dải màu/nền ám vẽ được sát mép — không phải sửa DataTable.tsx.
          <div className={cn('relative -mx-3 -my-2.5 flex items-center gap-2 py-2.5 pl-3 pr-3', accent?.wash)}>
            {accent && <span className={cn('absolute inset-y-0 left-0 w-[3px]', accent.stripe)} aria-hidden />}
            {d.source_kind === 'pdf'
              ? <FileText className="h-4 w-4 shrink-0 text-[#B33520]" />
              : <FileImage className="h-4 w-4 shrink-0 text-brand" />}
            <span className={cn('truncate font-mono text-[11.5px]', filenameTone(d.status))}>{d.filename}</span>
            {d.status === 'processing' && (
              <span
                className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-brand"
                aria-hidden
                title="Đang xử lý"
              />
            )}
          </div>
        )
      },
    },
    {
      key: 'invoice_no', header: 'Số hoá đơn', width: 'w-[110px]',
      render: (d) => d.invoice_no
        ? <span className="font-mono font-semibold">{d.invoice_no}</span>
        : <span className="text-ink-faint">—</span>,
    },
    { key: 'issue_date', header: 'Ngày lập', width: 'w-[100px]', render: (d) => formatDate(d.issue_date) },
    {
      key: 'seller', header: 'Nhà cung cấp',
      render: (d) => <span className="line-clamp-1">{d.seller_name ?? '—'}</span>,
    },
    {
      key: 'total', header: 'Tổng tiền', width: 'w-[130px]', align: 'right',
      render: (d) => <span className="font-mono tabular-nums">{formatMoney(d.total)}</span>,
    },
    {
      key: 'status', header: 'Trạng thái', width: 'w-[150px]',
      render: (d) => (
        <div className="flex items-center gap-1.5">
          <DocStatusBadge status={d.status} />
          {d.qc_failed > 0 && (
            <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-[#B4700B]">
              <AlertTriangle className="h-3 w-3" />{d.qc_failed}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'created', header: 'Nạp lúc', width: 'w-[120px]',
      render: (d) => <span className="text-ink-mute">{formatRelativeDay(d.created_at)}</span>,
    },
  ]

  return (
    <>
      <PageHeader
        title={reviewMode ? 'Chờ xác nhận' : 'Chứng từ'}
        subtitle={
          reviewMode
            ? 'Các chứng từ hệ thống phát hiện bất thường và cần người kiểm tra lại'
            : 'Toàn bộ chứng từ đã nạp vào hệ thống'
        }
        actions={
          <Button variant="primary" onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4" /> Nạp chứng từ
          </Button>
        }
      />

      {reviewMode && !q.isLoading && !q.error && !!q.data && q.data.total > 0 && (
        <Callout tone="warn" className="mb-3">
          <div className="flex items-start gap-2">
            <Inbox className="mt-[1px] h-4 w-4 shrink-0" aria-hidden />
            <span>
              <b>{q.data.total.toLocaleString('vi-VN')} chứng từ</b> đang chờ bạn xác nhận — mở từng dòng để đối
              chiếu lại thông tin trước khi hệ thống ghi nhận chính thức.
            </span>
          </div>
        </Callout>
      )}

      <DataTable
        columns={columns}
        filters={filters}
        state={state}
        data={q.data}
        isLoading={q.isLoading}
        error={q.error}
        onRetry={() => q.refetch()}
        rowKey={(d) => d.id}
        onRowClick={(d) => nav(`/documents/${d.id}${sp.toString() ? `?back=${encodeURIComponent(sp.toString())}` : ''}`)}
        emptyTitle={reviewMode ? 'Không có chứng từ nào chờ xác nhận' : 'Chưa có chứng từ nào'}
        emptyHint={
          reviewMode
            ? 'Mọi chứng từ đã qua kiểm tra tự động. Không cần bạn làm gì thêm.'
            : 'Bấm "Nạp chứng từ" để đưa hoá đơn vào hệ thống, hoặc để nhân viên AI tự lấy từ thư mục theo dõi.'
        }
      />

      <UploadDrawer open={uploadOpen} onClose={() => setUploadOpen(false)} onDone={() => q.refetch()} />
    </>
  )
}
