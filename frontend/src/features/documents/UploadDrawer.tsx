/**
 * M-02 — Ngăn nạp chứng từ.
 *
 * Là ngăn kéo chứ không phải một tuyến đường: nạp tệp là một trạng thái tạm
 * thời trên trang danh sách, không phải một trang mới.
 *
 * Điểm đáng chú ý: mã băm SHA-256 được tính NGAY TẠI TRÌNH DUYỆT rồi hỏi máy
 * chủ xem tệp đã có chưa. Trong nghiệp vụ kế toán, cùng một hoá đơn thường
 * được gửi lại nhiều lần qua nhiều kênh — bước này tiết kiệm cả băng thông
 * lẫn thời gian chờ của người dùng.
 */
import * as React from 'react'
import { CheckCircle2, CloudUpload, FileWarning, X } from 'lucide-react'
import { Drawer } from '@/components/ui/overlay'
import { Button, Callout } from '@/components/ui/primitives'
import { presignDocument, uploadDocument } from '@/api/documents'
import { cn } from '@/lib/cn'

const MAX_MB = 20
const ACCEPT = ['.jpg', '.jpeg', '.png', '.pdf']
const PARALLEL = 3

type ItemState = 'queued' | 'hashing' | 'uploading' | 'done' | 'duplicate' | 'error'

interface Item {
  id: string
  file: File
  state: ItemState
  progress: number
  message?: string
}

export function UploadDrawer({ open, onClose, onDone }: {
  open: boolean
  onClose: () => void
  onDone: () => void
}) {
  const [items, setItems] = React.useState<Item[]>([])
  const [dragging, setDragging] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  const patch = (id: string, p: Partial<Item>) =>
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...p } : it)))

  function addFiles(files: FileList | File[]) {
    const next: Item[] = []
    for (const file of Array.from(files)) {
      const ext = '.' + file.name.split('.').pop()!.toLowerCase()
      if (!ACCEPT.includes(ext)) {
        next.push({ id: crypto.randomUUID(), file, state: 'error', progress: 0, message: `Chỉ nhận ${ACCEPT.join(', ')}` })
        continue
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        next.push({ id: crypto.randomUUID(), file, state: 'error', progress: 0, message: `Vượt quá ${MAX_MB} MB` })
        continue
      }
      next.push({ id: crypto.randomUUID(), file, state: 'queued', progress: 0 })
    }
    setItems((prev) => [...prev, ...next])
    void run(next.filter((i) => i.state === 'queued'))
  }

  async function run(queue: Item[]) {
    const workers = Array.from({ length: PARALLEL }, async () => {
      while (queue.length) {
        const it = queue.shift()
        if (!it) break
        try {
          patch(it.id, { state: 'hashing', progress: 10 })
          const hash = await sha256(it.file)

          const { exists } = await presignDocument(hash)
          if (exists) {
            patch(it.id, { state: 'duplicate', progress: 100 })
            continue
          }

          patch(it.id, { state: 'uploading', progress: 45 })
          await uploadDocument(it.file)

          patch(it.id, { state: 'done', progress: 100 })
        } catch (e) {
          patch(it.id, { state: 'error', progress: 0, message: e instanceof Error ? e.message : 'Tải lên thất bại' })
        }
      }
    })
    await Promise.all(workers)
    onDone()
  }

  const doneCount = items.filter((i) => i.state === 'done').length
  const busy = items.some((i) => i.state === 'hashing' || i.state === 'uploading' || i.state === 'queued')

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Nạp chứng từ"
      subtitle="Kéo thả nhiều tệp cùng lúc — ảnh JPG, PNG hoặc PDF"
      footer={
        <>
          <span className="text-[12px] text-ink-mute">
            {items.length > 0 && `${doneCount} / ${items.length} tệp đã xong`}
          </span>
          <Button className="ml-auto" onClick={onClose} disabled={busy}>
            {busy ? 'Đang xử lý…' : 'Đóng'}
          </Button>
        </>
      }
    >
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
          dragging ? 'border-brand bg-brand-light' : 'border-[#CBD5E4] hover:border-brand/50 hover:bg-[#FAFBFD]',
        )}
      >
        <CloudUpload className="h-7 w-7 text-ink-faint" />
        <p className="text-[13.5px] font-semibold text-ink">Kéo thả tệp vào đây</p>
        <p className="text-[12px] text-ink-mute">hoặc bấm để chọn từ máy · tối đa {MAX_MB} MB mỗi tệp</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT.join(',')}
          className="hidden"
          onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = '' }}
        />
      </div>

      {items.length > 0 && (
        <ul className="mt-4 flex flex-col gap-1.5">
          {items.map((it) => (
            <li key={it.id} className="rounded-lg border border-line px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="truncate font-mono text-[11.5px] text-ink-soft">{it.file.name}</span>
                <span className="ml-auto shrink-0">
                  {it.state === 'done' && <CheckCircle2 className="h-4 w-4 text-[#137A47]" />}
                  {it.state === 'duplicate' && <span className="text-[11px] font-semibold text-[#9A6206]">Đã có</span>}
                  {it.state === 'error' && <FileWarning className="h-4 w-4 text-[#B33520]" />}
                  {(it.state === 'hashing' || it.state === 'uploading') && (
                    <span className="text-[11px] text-ink-mute">{it.state === 'hashing' ? 'Đang kiểm tra…' : 'Đang tải lên…'}</span>
                  )}
                </span>
              </div>
              {it.state !== 'error' && it.state !== 'done' && (
                <div className="mt-1.5 h-1 overflow-hidden rounded bg-black/[0.06]">
                  <div className="h-full rounded bg-brand transition-all" style={{ width: `${it.progress}%` }} />
                </div>
              )}
              {it.message && <p className="mt-1 text-[11px] text-[#B33520]">{it.message}</p>}
            </li>
          ))}
        </ul>
      )}

      <Callout tone="brand" className="mt-4">
        Nhân viên AI cũng tự lấy tệp mới từ thư mục theo dõi trên máy chủ mỗi phút.
        Bạn chỉ cần nạp tay khi muốn xử lý ngay một chứng từ lẻ.
      </Callout>
    </Drawer>
  )
}

/** Tính SHA-256 ngay tại trình duyệt để hỏi máy chủ xem tệp đã tồn tại chưa. */
async function sha256(file: File): Promise<string> {
  const buf = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('')
}
