/**
 * Thẻ "Mô hình AI" trong trang Cấu hình — quản trị viên gắn máy chủ mô hình
 * khác (vLLM nội bộ, Ollama, OpenRouter, OpenAI, Gemini…) mà không sửa tệp .env.
 *
 * - Thử kết nối / lấy danh sách model bằng giá trị ĐANG NHẬP, trước khi lưu.
 * - Khoá API không bao giờ quay về trình duyệt: ô nhập để trống = giữ khoá đã lưu.
 * - Lưu xong có hiệu lực ngay ở API và trong vài giây ở tiến trình nền.
 * - Địa chỉ ngoài mạng nội bộ → cảnh báo: chứng từ sẽ bị gửi ra dịch vụ bên ngoài.
 */
import * as React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getLlmConfig, listLlmModels, saveLlmConfig, testLlm } from '@/api/admin'
import type { LlmConfig, LlmSettingsInput, LlmSource } from '@/api/types'
import { formatMoney } from '@/lib/format'
import { ErrorState } from '@/components/shared/States'
import { Badge, Button, Callout, Card, CardTitle, Input, Label, Select, Skeleton } from '@/components/ui/primitives'

interface Preset { key: string; label: string; url: string; model?: string }

const PRESETS: Preset[] = [
  { key: 'vllm', label: 'vLLM nội bộ (mặc định)', url: 'http://vllm:8000/v1', model: 'Qwen3-VL-8B' },
  { key: 'ollama', label: 'Ollama', url: 'http://localhost:11434/v1' },
  { key: 'lmstudio', label: 'LM Studio', url: 'http://localhost:1234/v1' },
  { key: 'openrouter', label: 'OpenRouter', url: 'https://openrouter.ai/api/v1', model: 'qwen/qwen3-vl-8b-instruct' },
  { key: 'openai', label: 'OpenAI', url: 'https://api.openai.com/v1' },
  { key: 'gemini', label: 'Google Gemini', url: 'https://generativelanguage.googleapis.com/v1beta/openai' },
]
const CUSTOM = 'custom'

const SOURCE_LABEL: Record<LlmSource, string> = { settings: 'trang Cài đặt', env: 'tệp .env' }

function presetOf(url: string): string {
  const clean = url.replace(/\/+$/, '')
  return PRESETS.find((p) => p.url === clean)?.key ?? CUSTOM
}

/** Địa chỉ nằm ngoài mạng nội bộ → dữ liệu chứng từ rời khỏi doanh nghiệp. */
export function isExternal(url: string): boolean {
  let host: string
  try {
    host = new URL(url).hostname.toLowerCase()
  } catch {
    return false
  }
  if (!host.includes('.')) return false // tên dịch vụ trong Docker: vllm, ollama…
  if (host === 'localhost' || host.endsWith('.local') || host.endsWith('.internal') || host.endsWith('.lan')) return false
  return !/^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)/.test(host)
}

interface Form { base_url: string; model: string; api_key: string; clear_key: boolean }

function formFrom(c: LlmConfig): Form {
  return { base_url: c.base_url, model: c.model, api_key: '', clear_key: false }
}

export function LlmSettings({ status }: { status?: 'ok' | 'degraded' | 'down' }) {
  const qc = useQueryClient()
  const config = useQuery({ queryKey: ['llm-config'], queryFn: getLlmConfig })
  const [form, setForm] = React.useState<Form | null>(null)
  const [saved, setSaved] = React.useState(false)

  React.useEffect(() => {
    if (config.data && form === null) setForm(formFrom(config.data))
  }, [config.data, form])

  // Giá trị đang nhập, dùng để thử trước khi lưu (khoá trống = dùng khoá đã lưu).
  const draft: LlmSettingsInput = form
    ? { base_url: form.base_url.trim(), model: form.model.trim(), api_key: form.api_key.trim() || undefined }
    : {}

  const test = useMutation({ mutationFn: () => testLlm(draft) })
  const models = useMutation({ mutationFn: () => listLlmModels(draft) })
  const save = useMutation({
    mutationFn: (input: LlmSettingsInput) => saveLlmConfig(input),
    onSuccess: (data) => {
      qc.setQueryData(['llm-config'], data)
      qc.invalidateQueries({ queryKey: ['metrics'] })
      setForm(formFrom(data))
      setSaved(true)
    },
  })

  if (config.isError) return <ErrorState error={config.error} onRetry={() => config.refetch()} />
  if (!config.data || !form) return <Card className="max-w-2xl p-4"><Skeleton className="h-64 w-full" /></Card>

  const current = config.data
  const change = (patch: Partial<Form>) => { setForm({ ...form, ...patch }); setSaved(false) }
  const onPreset = (key: string) => {
    const p = PRESETS.find((x) => x.key === key)
    if (p) change({ base_url: p.url, model: p.model ?? form.model })
  }
  const onSave = () => save.mutate({
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    // Khoá: tích "xoá" → chuỗi rỗng; ô trống → không gửi (giữ nguyên khoá đã lưu).
    ...(form.clear_key ? { api_key: '' } : form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
  })
  const onReset = () => save.mutate({ base_url: '', model: '', api_key: '' })

  const state = test.data ? (test.data.ok ? 'ok' : 'down') : status
  const external = isExternal(form.base_url)
  const dirty = form.base_url.trim() !== current.base_url || form.model.trim() !== current.model
    || Boolean(form.api_key.trim()) || form.clear_key

  return (
    <Card className="max-w-2xl p-4">
      <CardTitle action={
        <Badge tone={state === 'ok' ? 'ok' : state === 'degraded' ? 'warn' : 'error'} dot>
          {state === 'ok' ? 'Hoạt động bình thường' : state === 'degraded' ? 'Chập chờn' : 'Không phản hồi'}
        </Badge>
      }>
        Mô hình AI
      </CardTitle>
      <p className="mb-3.5 text-[12px] text-ink-mute">
        Đang dùng <span className="font-mono text-ink">{current.model}</span> tại{' '}
        <span className="font-mono text-ink">{current.base_url}</span> (địa chỉ và model lấy từ{' '}
        {SOURCE_LABEL[current.sources.base_url]}). Mọi máy chủ theo chuẩn OpenAI đều dùng được;
        mô hình cần đọc được ảnh để xử lý hoá đơn.
      </p>

      <div className="grid gap-3">
        <div>
          <Label htmlFor="llm-preset">Nhà cung cấp</Label>
          <Select id="llm-preset" value={presetOf(form.base_url)} onChange={(e) => onPreset(e.target.value)}>
            {PRESETS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
            <option value={CUSTOM}>Tuỳ chỉnh</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="llm-url">Địa chỉ máy chủ</Label>
          <Input id="llm-url" className="font-mono" value={form.base_url} placeholder="http://vllm:8000/v1"
            onChange={(e) => change({ base_url: e.target.value })} />
        </div>
        <div>
          <Label htmlFor="llm-model">Tên model</Label>
          <div className="flex gap-2">
            <Input id="llm-model" className="font-mono" list="llm-model-options" value={form.model}
              placeholder="Qwen3-VL-8B" onChange={(e) => change({ model: e.target.value })} />
            <Button size="sm" className="h-auto" loading={models.isPending} onClick={() => models.mutate()}>
              Lấy danh sách
            </Button>
          </div>
          <datalist id="llm-model-options">
            {(models.data?.models ?? []).map((m) => <option key={m} value={m} />)}
          </datalist>
          {models.data && (models.data.ok
            ? <p className="mt-1 text-[11.5px] text-ink-mute">Máy chủ có {models.data.models.length} model — bấm vào ô để chọn.</p>
            : <p className="mt-1 text-[11.5px] text-[#A93318]">{models.data.error}</p>)}
        </div>
        <div>
          <Label htmlFor="llm-key">Khoá API</Label>
          <Input id="llm-key" type="password" autoComplete="new-password" value={form.api_key}
            disabled={form.clear_key}
            placeholder={current.api_key_set
              ? `Đã có khoá (từ ${SOURCE_LABEL[current.sources.api_key]}) — để trống nếu giữ nguyên`
              : 'Để trống nếu máy chủ nội bộ không cần khoá'}
            onChange={(e) => change({ api_key: e.target.value })} />
          {current.sources.api_key === 'settings' && (
            <label className="mt-1.5 flex items-center gap-2 text-[12px] text-ink-soft">
              <input type="checkbox" checked={form.clear_key} onChange={(e) => change({ clear_key: e.target.checked, api_key: '' })} />
              Xoá khoá đã lưu
            </label>
          )}
          <p className="mt-1 text-[11.5px] text-ink-mute">
            Khoá được mã hoá khi lưu và không bao giờ hiển thị lại.
          </p>
        </div>
      </div>

      {external && (
        <Callout tone="warn" title="Máy chủ nằm ngoài mạng nội bộ" className="mt-3.5">
          Ảnh và dữ liệu hoá đơn sẽ được gửi tới dịch vụ bên ngoài. Chỉ dùng với dữ liệu thử nghiệm
          hoặc khi doanh nghiệp đã đồng ý; dịch vụ trả phí sẽ tính tiền theo số token.
        </Callout>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button variant="primary" loading={save.isPending} disabled={!dirty} onClick={onSave}>Lưu cấu hình</Button>
        <Button loading={test.isPending} onClick={() => test.mutate()}>Thử kết nối</Button>
        {(current.sources.base_url === 'settings' || current.sources.model === 'settings' || current.sources.api_key === 'settings') && (
          <Button variant="ghost" onClick={onReset} disabled={save.isPending}>Dùng lại cấu hình trong .env</Button>
        )}
      </div>

      {save.isError && <Callout tone="error" className="mt-3.5">{(save.error as Error).message}</Callout>}
      {saved && !save.isError && (
        <Callout tone="ok" className="mt-3.5">Đã lưu — hệ thống dùng cấu hình mới ngay, không cần khởi động lại.</Callout>
      )}
      {test.data && (
        <Callout tone={test.data.ok ? 'ok' : 'error'} className="mt-3.5"
          title={test.data.ok ? 'Kết nối thành công' : 'Không kết nối được'}>
          <span className="font-mono">{test.data.model}</span> · {test.data.base_url} ·{' '}
          {formatMoney(test.data.latency_ms)} ms
          {test.data.error && <div className="mt-1">{test.data.error}</div>}
        </Callout>
      )}
    </Card>
  )
}
