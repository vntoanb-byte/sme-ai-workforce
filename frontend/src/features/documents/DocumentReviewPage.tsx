/**
 * P-06 — Kiểm tra kết quả trích xuất.
 *
 * MÀN HÌNH QUAN TRỌNG NHẤT của hệ thống — nơi con người và máy gặp nhau.
 * Nó là hiện thân của nguyên tắc thiết kế: hệ thống giả định mô hình SẼ SAI,
 * và thiết kế sẵn cho tình huống đó.
 *
 * Bố cục hai cột là bắt buộc chứ không phải thẩm mỹ: người kiểm tra cần nhìn
 * ảnh gốc và dữ liệu cùng lúc để đối chiếu.
 *
 * Ngôn ngữ hình ảnh cố ý tách hai cột: trái là GIẤY THẬT (nền ấm, dấu góc như
 * máy scan), phải là DỮ LIỆU SỐ (nền trắng lạnh, đúng hệ giao diện chung của
 * app) — đúng bản chất công việc đối chiếu, không phải trang trí. Các quy tắc
 * QC không đạt hiện thành một "phiếu ghi chú" ghim vào góc thay vì banner
 * cảnh báo chung chung.
 *
 * Đây cũng là màn hình người dùng thao tác lặp lại nhiều nhất, nên có phím tắt:
 *   Ctrl+Enter → xác nhận và sang bản kế tiếp
 *   Esc        → quay lại danh sách
 */
import * as React from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Check, Minus, Paperclip, Plus, RotateCw, Stamp, X } from 'lucide-react'
import { getDocument, listDocuments, patchExtraction, resolveReview } from '@/api/documents'
import { ApiError } from '@/api/client'
import type { InvoiceData, QCResult } from '@/api/types'
import { formatDuration } from '@/lib/format'
import { cn } from '@/lib/cn'
import { SplitView } from '@/components/shared/SplitView'
import { ErrorState } from '@/components/shared/States'
import { Button, Callout, Card, Skeleton } from '@/components/ui/primitives'
import { InvoiceForm } from './InvoiceForm'
import { InvoicePreview } from './InvoicePreview'

export function DocumentReviewPage() {
  const { id } = useParams<{ id: string }>()
  const docId = Number(id)
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const qc = useQueryClient()

  const backQuery = sp.get('back')
  const backTo = backQuery ? `/documents?${decodeURIComponent(backQuery)}` : '/documents'

  const q = useQuery({ queryKey: ['document', docId], queryFn: () => getDocument(docId) })
  const [draft, setDraft] = React.useState<InvoiceData | null>(null)
  const [zoom, setZoom] = React.useState(1)
  const [rotate, setRotate] = React.useState(0)

  React.useEffect(() => { setDraft(q.data?.data ?? null) }, [q.data?.id])

  // Danh sách các bản còn chờ xác nhận — để nhảy sang bản kế tiếp sau khi lưu
  const queue = useQuery({
    queryKey: ['documents', { status: 'needs_review' }, 1],
    queryFn: () => listDocuments({ status: 'needs_review', page: 1, page_size: 50 }),
  })
  const pending = queue.data?.items ?? []
  const posInQueue = pending.findIndex((d) => d.id === docId)
  const nextDoc = pending.find((d) => d.id !== docId)

  const save = useMutation({
    mutationFn: (data: InvoiceData) => patchExtraction(docId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      qc.invalidateQueries({ queryKey: ['metrics'] })
      if (nextDoc) nav(`/documents/${nextDoc.id}${backQuery ? `?back=${backQuery}` : ''}`)
      else nav(backTo)
    },
  })

  const reject = useMutation({
    mutationFn: () => resolveReview(docId, 'reject'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      qc.invalidateQueries({ queryKey: ['metrics'] })
      if (nextDoc) nav(`/documents/${nextDoc.id}${backQuery ? `?back=${backQuery}` : ''}`)
      else nav(backTo)
    },
  })
  const actionError = [save.error, reject.error].find((e) => e instanceof ApiError) as ApiError | undefined

  const confirm = React.useCallback(() => { if (draft) save.mutate(draft) }, [draft])

  React.useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') nav(backTo)
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); confirm() }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [confirm, backTo])

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />

  const doc = q.data
  const failed = doc?.qc.filter((r) => !r.passed) ?? []
  // NOTE (phát hiện thật, TASK-007): khi trích xuất thất bại (status=processing/
  // failed/rejected), backend thật trả data={} (rỗng) — InvoiceForm/InvoicePreview
  // giả định data luôn đủ trường (line_items, totals...) nên crash trắng trang nếu
  // render với object rỗng. Mock trước đây luôn có sẵn dữ liệu đầy đủ nên chưa lộ.
  const hasExtraction = !!draft && Object.keys(draft).length > 0

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="mb-4 flex flex-wrap items-start gap-3 border-b border-line pb-3.5">
        <button
          onClick={() => nav(backTo)}
          aria-label="Quay lại"
          className="mt-0.5 rounded-md border border-[#CBD5E4] bg-white p-1.5 text-ink-soft hover:bg-[#F7F9FC] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>

        <div className="min-w-0">
          <div className="flex items-baseline gap-2 font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-faint">
            <span>Phiếu kiểm tra</span>
            {posInQueue >= 0 && (
              <span className="tabular-nums">
                {String(posInQueue + 1).padStart(2, '0')} / {String(pending.length).padStart(2, '0')}
              </span>
            )}
          </div>
          <h1 className="truncate font-mono text-[18px] font-bold tracking-tight text-ink">
            {doc ? doc.filename : 'Đang tải…'}
          </h1>
          {doc && (
            <p className="mt-0.5 text-[12px] text-ink-mute">{doc.model_name} · {formatDuration(doc.latency_ms)}</p>
          )}
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button
            variant="danger"
            loading={reject.isPending}
            disabled={doc?.status !== 'needs_review'}
            title={doc?.status !== 'needs_review' ? 'Chỉ từ chối được chứng từ đang chờ xác nhận' : undefined}
            onClick={() => reject.mutate()}
          >
            <X className="h-4 w-4" /> Từ chối
          </Button>
          <Button onClick={() => (nextDoc ? nav(`/documents/${nextDoc.id}`) : nav(backTo))}>
            Bỏ qua
          </Button>
          <Button variant="success" loading={save.isPending} onClick={confirm} disabled={!draft}>
            <Check className="h-4 w-4" /> Xác nhận và lưu
          </Button>
        </div>
      </header>

      {actionError && (
        <Callout tone="error" className="mb-3.5">
          {actionError.message}
          {actionError.details && actionError.details.length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {(actionError.details as { loc?: string[]; message?: string }[]).map((d, i) => (
                <li key={i}>{d.loc ? `${d.loc.slice(1).join('.')}: ` : ''}{d.message}</li>
              ))}
            </ul>
          )}
        </Callout>
      )}

      {failed.length > 0 ? (
        <CorrectionSlip items={failed} className="mb-3.5" />
      ) : doc && hasExtraction ? (
        <ApprovalStamp className="mb-3.5" />
      ) : null}

      {q.isLoading || !doc || !draft ? (
        <Skeleton className="h-[520px] w-full rounded-xl" />
      ) : !hasExtraction ? (
        <Card className="flex h-[520px] flex-col items-center justify-center gap-3 text-center">
          <AlertTriangle className="h-8 w-8 text-[#B33520]" aria-hidden />
          <p className="text-[15px] font-semibold text-ink">Trích xuất thất bại — không có dữ liệu để đối chiếu</p>
          <p className="max-w-md text-[13px] text-ink-mute">
            Hệ thống chưa đọc được nội dung chứng từ này (mô hình AI lỗi hoặc tệp không hợp lệ). Kiểm tra kết nối
            mô hình rồi thử nạp lại chứng từ.
          </p>
          <Button onClick={() => nav(backTo)}>Quay lại danh sách</Button>
        </Card>
      ) : (
        <SplitView
          storageKey="doc-review"
          left={
            <Card className="relative flex h-full flex-col overflow-hidden">
              <div className="flex items-center gap-2 border-b border-line px-3.5 py-2">
                <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-ink-mute">Ảnh gốc</span>
                <span className="truncate font-mono text-[11.5px] text-ink-faint">{doc.filename}</span>
                <div className="ml-auto flex shrink-0 gap-1">
                  <IconBtn onClick={() => setZoom((z) => Math.max(0.5, z - 0.15))} label="Thu nhỏ"><Minus className="h-3.5 w-3.5" /></IconBtn>
                  <span className="px-1 text-[11.5px] font-semibold tabular-nums text-ink-soft">{Math.round(zoom * 100)}%</span>
                  <IconBtn onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))} label="Phóng to"><Plus className="h-3.5 w-3.5" /></IconBtn>
                  <IconBtn onClick={() => setRotate((r) => (r + 90) % 360)} label="Xoay"><RotateCw className="h-3.5 w-3.5" /></IconBtn>
                </div>
              </div>
              <div
                className="thin-scroll flex-1 overflow-auto p-4"
                style={{
                  backgroundColor: '#EDE7D6',
                  backgroundImage: 'radial-gradient(rgba(22,35,60,0.08) 1px, transparent 1px)',
                  backgroundSize: '16px 16px',
                }}
              >
                <div style={{ transform: `scale(${zoom}) rotate(${rotate}deg)`, transformOrigin: 'top center' }}>
                  {/* file_url rỗng ở mock ('') -> InvoicePreview tự dựng lại hoá
                      đơn "đúng" để đối chiếu (thiết kế có chủ đích, xem docstring
                      InvoicePreview.tsx); backend thật trả file_url thật -> hiện
                      ảnh gốc. */}
                  <InvoicePreview data={doc.data} fileUrl={doc.file_url} />
                </div>
              </div>
              <RegistrationMarks />
            </Card>
          }
          right={
            <Card className="flex h-full flex-col overflow-hidden">
              <div className="flex items-center gap-2 border-b border-line px-3.5 py-2">
                <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-ink-mute">
                  Dữ liệu AI đọc được
                </span>
                <span className="ml-auto shrink-0 font-mono text-[11px] tabular-nums text-ink-faint">
                  {failed.length > 0 ? `${failed.length} mục cần kiểm tra` : 'không có sai lệch'}
                </span>
              </div>
              <div className="thin-scroll flex-1 overflow-y-auto px-4 py-3.5">
                <InvoiceForm data={draft} qc={doc.qc} onChange={setDraft} />
              </div>
              <div className="border-t border-line px-4 py-2 font-mono text-[10.5px] tracking-wide text-ink-faint">
                <b className="text-ink-soft">Ctrl + Enter</b> xác nhận · <b className="text-ink-soft">Esc</b> quay lại danh sách
              </div>
            </Card>
          }
        />
      )}
    </div>
  )
}

/** "Phiếu ghi chú" ghim ở góc — thay cho banner cảnh báo chung chung, mỗi mục nêu đúng phép tính bị lệch. */
function CorrectionSlip({ items, className }: { items: QCResult[]; className?: string }) {
  return (
    <div className={cn('relative pl-1 pt-2', className)}>
      <Paperclip
        className="absolute -top-0.5 left-4 h-5 w-5 rotate-[-8deg] text-ink-faint"
        strokeWidth={2.25}
        aria-hidden
      />
      <div className="slip-enter origin-top-left rotate-[-0.4deg] rounded-sm border border-[#E5BFB2] bg-[#FEF6F3] px-4 pb-3 pt-3.5 shadow-sm">
        <div className="mb-2 flex items-baseline gap-2 border-b border-dashed border-[#E5BFB2] pb-2 font-mono text-[10.5px] uppercase tracking-[0.12em] text-[#A93318]">
          <span className="font-bold">Phiếu ghi chú</span>
          <span className="normal-case tracking-normal text-[#B3705F]">{items.length} mục cần kiểm tra</span>
        </div>
        <ul className="space-y-1.5">
          {items.map((r) => (
            <li key={r.rule_code} className="flex items-start gap-2 text-[12.5px] leading-snug text-[#7A4433]">
              <span className="mt-[1px] shrink-0 rounded border border-dashed border-[#C98A76] px-1 font-mono text-[10px] font-bold text-[#A93318]">
                {r.rule_code}
              </span>
              <span>{r.message}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

/** Con dấu "đã đối chiếu" khi không phát hiện sai lệch — phần thưởng thị giác nhỏ khi mọi quy tắc đều đạt. */
function ApprovalStamp({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'slip-enter flex w-fit -rotate-1 items-center gap-2.5 rounded-sm border-2 border-dashed border-[#137A47] bg-[#F0FDF4] px-3.5 py-2 text-[#0F6E42]',
        className,
      )}
    >
      <Stamp className="h-4 w-4" strokeWidth={2.25} aria-hidden />
      <span className="font-mono text-[11.5px] font-bold uppercase tracking-[0.1em]">
        Đã đối chiếu — không phát hiện sai lệch
      </span>
    </div>
  )
}

/** Dấu góc kiểu máy scan — nhấn mạnh cột trái là ảnh chụp một vật thể thật để đối chiếu. */
function RegistrationMarks() {
  const corner = 'pointer-events-none absolute h-3.5 w-3.5 border-ink/25'
  return (
    <>
      <span className={cn(corner, 'left-2.5 top-2.5 border-l-2 border-t-2')} />
      <span className={cn(corner, 'right-2.5 top-2.5 border-r-2 border-t-2')} />
      <span className={cn(corner, 'bottom-2.5 left-2.5 border-b-2 border-l-2')} />
      <span className={cn(corner, 'bottom-2.5 right-2.5 border-b-2 border-r-2')} />
    </>
  )
}

function IconBtn({ children, onClick, label }: { children: React.ReactNode; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="rounded border border-[#CBD5E4] bg-white p-1 text-ink-soft hover:bg-[#F7F9FC] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
    >
      {children}
    </button>
  )
}
