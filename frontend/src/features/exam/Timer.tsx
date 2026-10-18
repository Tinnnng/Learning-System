import { useEffect, useRef, useState } from 'react'
import { Icon } from '@/components/Icon'
import { cx } from '@/lib/cx'
import { clock } from '@/lib/format'

interface TimerProps {
  /** 截止時刻（瀏覽器時鐘的毫秒） */
  deadline: number
  /** 時間到時呼叫一次（只提醒，不交卷） */
  onTimeUp: () => void
}

const secondsLeft = (deadline: number) => Math.round((deadline - Date.now()) / 1000)

/** 模擬考倒數。剩 5 分鐘變印刷粉紅、剩 1 分鐘閃爍；時間到不交卷，改成顯示「已超時」繼續計時。 */
export function Timer({ deadline, onTimeUp }: TimerProps) {
  const [left, setLeft] = useState(() => secondsLeft(deadline))
  const notified = useRef(false)

  useEffect(() => {
    const tick = () => {
      const seconds = secondsLeft(deadline)
      setLeft(seconds)
      if (seconds <= 0 && !notified.current) {
        notified.current = true
        onTimeUp()
      }
    }
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [deadline, onTimeUp])

  const over = left <= 0
  const warning = left <= 300
  const urgent = left > 0 && left <= 60
  // 剩 5 分鐘、1 分鐘、時間到時念一次（role=timer 本身不朗讀，避免每秒打擾）；隱藏的那份計時器不會念
  const notice = over ? '時間到，可以繼續作答' : urgent ? '剩不到 1 分鐘' : warning ? '剩不到 5 分鐘' : ''
  return (
    <span
      role="timer"
      aria-label={over ? `已超時 ${clock(-left)}` : `剩餘時間 ${clock(left)}`}
      className={cx(
        'tabular inline-flex items-center gap-1.5 text-lg transition-colors duration-[var(--dur)]',
        over ? 'text-bad' : warning ? 'text-accent' : 'text-ink',
        urgent && 'animate-pulse',
      )}
    >
      <Icon name="clock" size={18} />
      {over ? (
        <>
          <span className="text-sm">超時</span>+{clock(-left)}
        </>
      ) : (
        clock(left)
      )}
      <span className="sr-only" aria-live="polite">
        {notice}
      </span>
    </span>
  )
}
