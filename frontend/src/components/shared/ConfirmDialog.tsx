import { Button } from '@/components/ui/primitives'
import { Dialog } from '@/components/ui/overlay'

/** Hộp thoại xác nhận dùng chung cho mọi thao tác cần người dùng khẳng định. */
export function ConfirmDialog({ open, title, message, confirmLabel = 'Xác nhận', danger, onConfirm, onClose, loading }: {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  danger?: boolean
  loading?: boolean
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      width="max-w-md"
      footer={
        <>
          <Button onClick={onClose}>Huỷ</Button>
          <Button
            className="ml-auto"
            variant={danger ? 'danger' : 'primary'}
            loading={loading}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-[13px] leading-relaxed text-ink-soft">{message}</p>
    </Dialog>
  )
}
