/**
 * Khung nhật ký thời gian thực.
 *
 * Hai chi tiết quan trọng:
 *  1. Giữ tối đa 500 dòng gần nhất (xử lý trong hook useRunLogs) để không làm
 *     nặng trình duyệt trong các lần chạy dài.
 *  2. Tự cuộn xuống dưới, nhưng DỪNG tự cuộn nếu người dùng đang cuộn lên đọc.
 *     Thiếu chi tiết này thì không ai đọc được nhật ký của một lần chạy đang chạy.
 */
import * as React from 'react'
import type { LogLine } from '@/api/types'
import { formatTime } from '@/lib/format'
import { Badge } from '@/components/ui/primitives'
import { cn } from '@/lib/cn'

const LEVEL: Record<LogLine['level'], string> = {
  DEBUG: 'text-[#6B7B96]',
  INFO:  'text-[#5DBE8A]',
  WARN:  'text-[#E8B75C]',
  ERROR: 'text-[#F0776A]',
}

export function LogStream({ logs, live }: { logs: LogLine[]; live: boolean }) {
  const boxRef = React.useRef<HTMLDivElement>(null)
  const [stick, setStick] = React.useState(true)

  React.useEffect(() => {
    if (!stick || !boxRef.current) return
    boxRef.current.scrollTop = boxRef.current.scrollHeight
  }, [logs, stick])

  const onScroll = () => {
    const el = boxRef.current
    if (!el) return
    // Coi là "đang bám đáy" khi còn cách đáy dưới 40px
    setStick(el.scrollHeight - el.scrollTop - el.clientHeight < 40)
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-line bg-white">
      <div className="flex items-center gap-2 border-b border-line px-3.5 py-2">
        <span className="text-[11.5px] font-semibold uppercase tracking-wide text-ink-mute">Nhật ký thực thi</span>
        <span className="ml-auto flex items-center gap-2">
          {!stick && (
            <button
              onClick={() => setStick(true)}
              className="text-[11px] font-semibold text-brand hover:underline"
            >
              Cuộn xuống cuối
            </button>
          )}
          {live ? <Badge tone="running" dot>Trực tiếp</Badge> : <Badge tone="neutral">Đã kết thúc</Badge>}
        </span>
      </div>

      <div
        ref={boxRef}
        onScroll={onScroll}
        className="thin-scroll flex-1 overflow-y-auto bg-[#131C2E] px-4 py-3 font-mono text-[11.5px] leading-[1.95] text-[#B9C7DE]"
      >
        {logs.length === 0 && <p className="text-[#5D7093]">Đang chờ dòng nhật ký đầu tiên…</p>}
        {logs.map((l, i) => (
          <div key={i} className="whitespace-pre-wrap break-words">
            <span className="text-[#5D7093]">{formatTime(l.ts)}</span>{' '}
            <span className={cn('font-semibold', LEVEL[l.level])}>{l.level.padEnd(5)}</span>{' '}
            <span>{l.message}</span>
          </div>
        ))}
        {live && <div className="text-[#7EA9F0]">▊</div>}
      </div>
    </div>
  )
}
