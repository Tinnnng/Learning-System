import type { ReactNode } from 'react'
import { ApiError } from '@/lib/api'
import { cx } from '@/lib/cx'

export function Loading({ label = '載入中', className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cx('flex items-center gap-3 py-10 text-muted', className)}>
      <span className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="h-3 w-2 animate-pulse rounded-full border border-print"
            style={{ animationDelay: `${index * 160}ms` }}
          />
        ))}
      </span>
      {label}…
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError
      ? typeof error.detail === 'string'
        ? error.detail
        : `伺服器回應錯誤（${error.status}）`
      : '無法連線到後端，請確認已執行 npm run dev。'
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-md border border-bad/40 bg-bad-soft/50 p-5">
      <p className="m-0 text-ink">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="text-sm font-medium text-print underline underline-offset-4">
          重新載入
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="ruled flex flex-col items-start gap-3 rounded-lg border border-dashed border-print-rule px-6 py-10">
      <h2 className="m-0 font-serif text-lg font-bold">{title}</h2>
      {children && <div className="max-w-[56ch] text-muted">{children}</div>}
      {action}
    </div>
  )
}
