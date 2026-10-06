/**
 * 題號導覽：做成答案卡的「劃記區」。每格是題號＋小橢圓，作答過塗黑，
 * 揭曉後變成對錯色；目前的題目有粉紅框。點擊跳到該題。
 */

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

export function AnswerGrid({ cells, current, onJump, className }: AnswerGridProps) {
  return (
    <ol
      className={cx('grid grid-cols-[repeat(auto-fill,minmax(38px,1fr))] gap-x-1 gap-y-2', className)}
      aria-label="題號導覽"
    >
      {cells.map((cell) => {
        const isCurrent = cell.position === current
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
                'flex w-full flex-col items-center gap-1 rounded-sm py-1.5',
                'transition-colors duration-[var(--dur-fast)] hover:bg-print-faint',
                isCurrent && 'bg-print-faint ring-1 ring-print',
              )}
            >
              <span className="tabular text-[11px] leading-none text-print">{cell.position}</span>
              <span
                className={cx(
                  'h-[13px] w-[9px] rounded-full border transition-colors duration-[var(--dur)]',
                  cell.correct === true
                    ? 'border-ok bg-ok'
                    : cell.correct === false
                      ? 'border-bad bg-bad'
                      : cell.answered
                        ? 'border-ink bg-ink'
                        : 'border-print',
                )}
              />
            </button>
          </li>
        )
      })}
    </ol>
  )
}
