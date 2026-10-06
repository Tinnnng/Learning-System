import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

interface PageHeaderProps {
  /** 印刷體小標，例如「錯題本」「115 年普考」 */
  eyebrow?: ReactNode
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

/** 頁首：明體標題＋答案卡粉紅印刷雙線。 */
export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <header className={cx('flex flex-col gap-4 pb-5', className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="flex min-w-0 flex-col gap-1.5">
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h1 className="m-0 font-serif text-xl font-bold text-ink sm:text-2xl">{title}</h1>
          {description && <p className="m-0 max-w-[60ch] text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      <div aria-hidden="true" className="h-[5px] border-y border-print-rule" />
    </header>
  )
}
