/**
 * Nhận nhật ký thời gian thực qua Server-Sent Events.
 *
 * Dùng SSE thay vì WebSocket vì luồng dữ liệu ở đây hoàn toàn một chiều
 * (máy chủ → trình duyệt) và SSE chạy trên HTTP thường, thuận lợi khi đi qua
 * máy chủ proxy trong mạng doanh nghiệp.
 *
 * Ở chế độ VITE_USE_MOCK, hook nhả dần các dòng nhật ký mẫu để giao diện
 * trông đúng như đang chạy thật.
 */
import { useEffect, useRef, useState } from 'react'
import type { LogLine } from '@/api/types'
import { USE_MOCK } from '@/api/client'
import { mockLogLines } from '@/api/mock/data'

const MAX_LINES = 500

export function useRunLogs(runId: number, active: boolean) {
  const [logs, setLogs] = useState<LogLine[]>([])
  const [connected, setConnected] = useState(false)
  const idx = useRef(0)

  useEffect(() => {
    setLogs([])
    idx.current = 0
    if (!active) { setConnected(false); return }

    // ── Chế độ giả: nhả dần từng dòng ──
    if (USE_MOCK) {
      const all = mockLogLines()
      setConnected(true)
      const t = setInterval(() => {
        if (idx.current >= all.length) { clearInterval(t); return }
        const line = all[idx.current++]
        setLogs((prev) => [...prev.slice(-(MAX_LINES - 1)), line])
      }, 550)
      return () => { clearInterval(t); setConnected(false) }
    }

    // ── Chế độ thật ──
    const es = new EventSource(`/api/v1/runs/${runId}/logs`, { withCredentials: true })
    es.onopen = () => setConnected(true)
    es.addEventListener('log', (e) => {
      const line = JSON.parse((e as MessageEvent).data) as LogLine
      setLogs((prev) => [...prev.slice(-(MAX_LINES - 1)), line])
    })
    es.addEventListener('done', () => { es.close(); setConnected(false) })
    es.onerror = () => setConnected(false)
    return () => { es.close(); setConnected(false) }
  }, [runId, active])

  return { logs, connected }
}
