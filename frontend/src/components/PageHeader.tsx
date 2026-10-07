import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

interface PageHeaderProps {
  /** 標題上方的小標籤，例如「錯題本」「115 年普考」 */
  eyebrow?: ReactNode
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

/** 頁首：粗體標題，進場時底下用原子筆從左到右畫一條略帶抖動的線（方向 A「白紙」的記號）。 */
export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <header className={cx('flex flex-col gap-4 border-b border-line pb-6', className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="flex min-w-0 flex-col gap-2">
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h1 className="m-0 font-display text-2xl font-bold tracking-[0.01em] text-ink [word-break:keep-all] sm:text-[34px] sm:leading-tight">
            <span className="relative inline-block pb-2">
              {title}
              <PenStroke />
            </span>
          </h1>
          {description && <p className="m-0 max-w-[60ch] text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </header>
  )
}

/** 手寫感的底線：pathLength=1 讓 stroke-dashoffset 從 1 到 0 就是「畫完一條線」，不管標題多長 */
function PenStroke() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 200 8"
      preserveAspectRatio="none"
      className="pointer-events-none absolute -bottom-0.5 left-0 h-2 w-[min(100%,14rem)] overflow-visible"
    >
      <path
        d="M2 5.2C34 3.4 66 4.6 98 3.6S164 2.6 198 4.4"
        pathLength={1}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={2.2}
        strokeLinecap="round"
        strokeDasharray="1"
        className="animate-[draw_var(--dur-pen)_var(--ease-pen)_160ms_both]"
      />
    </svg>
  )
}
