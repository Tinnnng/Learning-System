/**
 * 「清除…」按鈕：按下去先跳確認視窗，確定後才清除。清除前後端會自動備份一份「清除前」快照，
 * 視窗裡會說明可以到備份頁還原。完成後在按鈕旁顯示結果（常駐朗讀區，螢幕閱讀器念得出來）。
 */

import { useMutation } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { Button } from '@/components/Button'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'

interface ResetButtonProps<T> {
  /** 按鈕文字，例如「清除單字進度」 */
  label: string
  /** 確認視窗標題，例如「清除所有單字的學習進度？」 */
  title: string
  /** 會清掉什麼、不會動到什麼 */
  children: ReactNode
  confirmLabel: string
  run: () => Promise<T>
  /** 完成後顯示的一句話 */
  doneText: (result: T) => string
  onDone?: () => void
  className?: string
}

export function ResetButton<T extends { backup: string }>({
  label,
  title,
  children,
  confirmLabel,
  run,
  doneText,
  onDone,
  className,
}: ResetButtonProps<T>) {
  const [open, setOpen] = useState(false)
  const reset = useMutation({
    mutationFn: run,
    onSuccess: () => {
      setOpen(false)
      onDone?.()
    },
  })

  return (
    <div className={className}>
      <Button variant="danger" size="sm" onClick={() => setOpen(true)}>
        <Icon name="trash" size={16} />
        {label}
      </Button>
      <p className="m-0 mt-2 text-xs text-muted empty:hidden" aria-live="polite">
        {reset.data ? `${doneText(reset.data)}清除前的資料備份在「${reset.data.backup}」。` : ''}
      </p>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={title}
        actions={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button variant="danger" onClick={() => reset.mutate()} disabled={reset.isPending}>
              {reset.isPending ? '清除中…' : confirmLabel}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3 text-[15px]">
          {children}
          <p className="m-0 text-sm text-muted">
            清除前會先自動備份一份（備份頁標示「清除前」），按錯了可以到「備份」頁還原。
          </p>
          {reset.isError && <ErrorState error={reset.error} />}
        </div>
      </Dialog>
    </div>
  )
}
