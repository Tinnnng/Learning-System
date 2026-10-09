/**
 * 題號導覽：一格一個題號，作答過的題號用螢光筆劃起來（揭曉後變成綠／粉紅），
 * 目前的題目用原子筆圈起來。點擊跳到該題。
 * 揭曉後右上角另外標 ✓／×，色弱或列印成黑白時也分得出對錯（不只靠顏色）。
 */

import type { CSSProperties } from 'react'
import { cx } from '@/lib/cx'

export interface GridCell {
  position: number
  answered: boolean
  /** 揭曉後才有：true 對、false 錯 */
  correct?: boolean | null
}

interface AnswerGridProps {
  cells: GridCell[]
  current?: number
  onJump?: (position: number) => void
  className?: string
}

function markerColor(cell: GridCell): string | null {
  if (cell.correct === true) return 'var(--ok-hl)'
  if (cell.correct === false) return 'var(--bad-hl)'
  return cell.answered ? 'var(--hl)' : null
}

export function AnswerGrid({ cells, current, onJump, className }: AnswerGridProps) {
  return (
    <ol className={cx('grid grid-cols-[repeat(auto-fill,minmax(44px,1fr))] gap-1', className)} aria-label="題號導覽">
      {cells.map((cell) => {
        const isCurrent = cell.position === current
        const color = markerColor(cell)
        const status =
          cell.correct === true ? '答對' : cell.correct === false ? '答錯' : cell.answered ? '已作答' : '未作答'
        return (
          <li key={cell.position}>
            <button
              type="button"
              onClick={() => onJump?.(cell.position)}
              aria-current={isCurrent ? 'step' : undefined}
              aria-label={`第 ${cell.position} 題，${status}`}
              className={cx(
                'relative grid h-[44px] w-full place-items-center rounded-md transition-colors duration-[var(--dur-fast)]',
                'hover:bg-sheet-tint',
              )}
            >
              <span
                className="marker tabular text-sm text-ink"
                style={{ '--marker-color': color ?? 'transparent', '--marker-scale': color ? 1 : 0 } as CSSProperties}
              >
                {cell.position}
              </span>
              {cell.correct != null && (
                <span
                  aria-hidden="true"
                  className={cx(
                    'absolute right-0.5 top-0 text-[11px] font-bold leading-none',
                    cell.correct ? 'text-ok' : 'text-bad',
                  )}
                >
                  {cell.correct ? '✓' : '×'}
                </span>
              )}
              {isCurrent && (
                <svg
                  aria-hidden="true"
                  viewBox="0 0 40 40"
                  className="pointer-events-none absolute inset-0 m-auto h-9 w-9 text-accent"
                  fill="none"
                >
                  {/* 原子筆隨手一圈：起點和終點故意沒接上 */}
                  <path
                    d="M27 7.5C21 4.5 9 6 6.5 15.5 4 25 12 34 21.5 33 31 32 35.5 22 33 14 31.5 9.5 26 6.5 19 7"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    pathLength={1}
                    strokeDasharray={1}
                    className="animate-[draw_var(--dur-slow)_var(--ease-marker)_both]"
                  />
                </svg>
              )}
            </button>
          </li>
        )
      })}
    </ol>
  )
}
