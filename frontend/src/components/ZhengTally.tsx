/**
 * 「正」字掌握進度：錯題要連續答對 5 次才移出錯題本，剛好寫完一個「正」字。
 * 每答對一次多一筆（依筆順），答錯歸零；寫滿時變成答對色。
 */

import { cx } from '@/lib/cx'

// 「正」的五筆，依筆順：上橫、中豎、中短橫、左豎、下橫
const STROKES = ['M7 7H33', 'M20 7V34', 'M20 20H31', 'M10 20V34', 'M5 34H35']

interface ZhengTallyProps {
  count: number
  target?: number
  size?: number
  showLabel?: boolean
  className?: string
}

export function ZhengTally({ count, target = 5, size = 32, showLabel = true, className }: ZhengTallyProps) {
  const filled = Math.max(0, Math.min(count, STROKES.length))
  const done = count >= target
  return (
    <span className={cx('inline-flex items-center gap-2', className)}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        role="img"
        aria-label={done ? '已掌握' : `連續答對 ${count} 次，共需 ${target} 次`}
        className="flex-none"
      >
        <rect x="1" y="1" width="38" height="38" fill="none" stroke="var(--rule)" strokeDasharray="2 3" />
        {STROKES.map((d, index) => (
          <path
            key={d}
            d={d}
            fill="none"
            stroke={done ? 'var(--ok)' : 'var(--accent)'}
            strokeWidth={3.2}
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={index < filled ? 0 : 1}
            style={{ transition: 'stroke-dashoffset var(--dur-slow) var(--ease-draw), stroke var(--dur) ease' }}
          />
        ))}
      </svg>
      {showLabel && (
        <span className="text-sm text-muted">
          {done ? (
            <span className="text-ok font-medium">已掌握</span>
          ) : (
            <>
              連續答對 <span className="tabular text-ink">{count}</span>／{target}
            </>
          )}
        </span>
      )}
    </span>
  )
}
