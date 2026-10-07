/** 對話框：使用原生 <dialog>（焦點鎖定、Esc 關閉都由瀏覽器處理）。 */

import { type ReactNode, useEffect, useRef } from 'react'
import { cx } from '@/lib/cx'

interface DialogProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  children: ReactNode
  actions?: ReactNode
  wide?: boolean
}

export function Dialog({ open, onClose, title, children, actions, wide }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose()
      }}
      className={cx(
        'm-auto w-[calc(100%-32px)] rounded-lg border border-line bg-sheet p-0 text-ink shadow-pop',
        'backdrop:bg-[var(--overlay)] backdrop:backdrop-blur-[2px]',
        'open:animate-[dialog-in_var(--dur)_var(--ease-out)]',
        wide ? 'max-w-[880px]' : 'max-w-[440px]',
      )}
    >
      <div className="flex max-h-[85dvh] flex-col">
        <h2 className="m-0 border-b border-rule px-6 py-4 font-display text-lg font-bold">{title}</h2>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
        {actions && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-6 py-4">{actions}</div>}
      </div>
    </dialog>
  )
}
