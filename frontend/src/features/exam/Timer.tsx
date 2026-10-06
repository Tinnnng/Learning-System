import { useEffect, useRef, useState } from 'react'
import { Icon } from '@/components/Icon'
import { cx } from '@/lib/cx'
import { clock } from '@/lib/format'

interface TimerProps {
  remainingSeconds: number
  onExpire: () => void
}

/** 模擬考倒數。剩 5 分鐘變印刷粉紅、剩 1 分鐘閃爍；時間到呼叫 onExpire（只呼叫一次）。 */
export function Timer({ remainingSeconds, onExpire }: TimerProps) {
  const deadline = useRef<number | null>(null)
  const expired = useRef(false)
  const [left, setLeft] = useState(remainingSeconds)

  useEffect(() => {
    deadline.current ??= Date.now() + remainingSeconds * 1000
    const tick = () => {
      if (deadline.current === null) return
      const seconds = Math.max(0, Math.round((deadline.current - Date.now()) / 1000))
      setLeft(seconds)
      if (seconds === 0 && !expired.current) {
        expired.current = true
        onExpire()
      }
    }
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [onExpire, remainingSeconds])

  const warning = left <= 300
  const urgent = left <= 60
  return (
    <span
      role="timer"
      aria-label={`剩餘時間 ${clock(left)}`}
      className={cx(
        'tabular inline-flex items-center gap-1.5 text-lg transition-colors duration-[var(--dur)]',
        warning ? 'text-print' : 'text-ink',
        urgent && 'animate-pulse',
      )}
    >
      <Icon name="clock" size={18} />
      {clock(left)}
    </span>
  )
}
