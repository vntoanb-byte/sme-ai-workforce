/**
 * Trạng thái rỗng và trạng thái lỗi.
 *
 * Nguyên tắc: KHÔNG bao giờ để trang trắng. Mọi danh sách rỗng phải nói được
 * người dùng nên làm gì tiếp theo; mọi lỗi phải kèm mã truy vết để người dùng
 * đọc cho quản trị viên khi cần hỗ trợ.
 */
import { AlertTriangle, Inbox } from 'lucide-react'
import { Button } from '@/components/ui/primitives'
import { ApiError } from '@/api/client'

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <Inbox className="h-8 w-8 text-ink-faint" />
      <p className="text-[13.5px] font-semibold text-ink">{title}</p>
      {hint && <p className="max-w-md text-[12.5px] text-ink-mute">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const isApi = error instanceof ApiError
  const message = isApi ? error.message : 'Không kết nối được tới máy chủ. Kiểm tra lại kết nối rồi thử lại.'
  const traceId = isApi ? error.traceId : undefined
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      <AlertTriangle className="h-8 w-8 text-[#D0492F]" />
      <p className="max-w-lg text-[13px] font-semibold text-ink">{message}</p>
      {traceId && <p className="font-mono text-[11px] text-ink-faint">Mã truy vết: {traceId}</p>}
      {onRetry && <Button size="sm" className="mt-2" onClick={onRetry}>Thử lại</Button>}
    </div>
  )
}
