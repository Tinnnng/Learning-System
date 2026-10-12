/** 頁首的小計時：番茄鐘進行中（或暫停中）才出現，點了回首頁看番茄鐘。 */

import { Link } from 'react-router'
import { cx } from '@/lib/cx'
import { clock } from '@/lib/format'
import { usePomodoro, useRemaining } from '@/lib/pomodoro'

export function PomodoroChip() {
  const timer = usePomodoro()
  const left = useRemaining(timer)
  if (timer.phase === 'idle') return null
  const resting = timer.phase === 'break'
  const paused = timer.pausedLeft !== null
  return (
    <Link
      to="/"
      aria-label={`番茄鐘${resting ? '休息' : '專心'}中，剩 ${clock(left)}${paused ? '（暫停）' : ''}`}
      className={cx(
        'hit inline-flex h-8 flex-none items-center gap-1.5 rounded-full border px-2.5 text-xs transition-colors',
        resting ? 'border-ok/40 text-ok' : 'border-accent/40 text-accent-strong',
        'hover:bg-accent-faint',
      )}
    >
      <span aria-hidden="true" className={cx('h-1.5 w-1.5 rounded-full', resting ? 'bg-ok' : 'bg-accent', !paused && 'animate-pulse')} />
      <span className="tabular" aria-hidden="true">
        {clock(left)}
      </span>
    </Link>
  )
}
