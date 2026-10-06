import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

interface PageHeaderProps {
  /** 原子筆批註感的小標，例如「錯題本」「115 年普考」 */
  eyebrow?: ReactNode
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

/** 頁首：手寫標題，下半部被淡黃色螢光筆刷過（進場時刷一次）。 */
export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <header className={cx('flex flex-col gap-4 border-b border-line pb-6', className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="flex min-w-0 flex-col gap-1.5">
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h1 className="m-0 font-hand text-2xl font-bold text-ink [word-break:keep-all] sm:text-[38px] sm:leading-tight">
            <span className="marker [--marker-color:var(--hl-soft)] [&::before]:top-[52%] [&::before]:animate-[swipe_520ms_var(--ease-marker)_120ms_both]">
              {title}
            </span>
          </h1>
          {description && <p className="m-0 mt-1 max-w-[60ch] text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </header>
  )
}
