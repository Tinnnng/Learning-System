/**
 * 數字跳動：第一次出現時從 0 數到目標值，之後數值改變時從舊值滾到新值（約 0.7 秒，先快後慢）。
 * 用在考試倒數、題數、統計等「這頁的重點數字」；系統設定減少動態效果時直接顯示結果。
 * 螢幕閱讀器只會讀到最後的數字。
 */

import { useEffect, useRef, useState } from 'react'

interface CountUpProps {
  value: number
  /** 小數位數（例如正確率 0 位、金額 2 位） */
  decimals?: number
  duration?: number
  className?: string
}

const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export function CountUp({ value, decimals = 0, duration = 700, className }: CountUpProps) {
  const [shown, setShown] = useState(() => (reducedMotion() ? value : 0))
  const from = useRef(shown)

  useEffect(() => {
    if (reducedMotion() || from.current === value) {
      from.current = value
      setShown(value)
      return
    }
    const start = performance.now()
    const begin = from.current
    let frame = 0
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - progress) ** 3
      const current = begin + (value - begin) * eased
      from.current = current
      setShown(current)
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value, duration])

  return (
    <span className={className}>
      <span aria-hidden="true">{shown.toFixed(decimals)}</span>
      <span className="sr-only">{value.toFixed(decimals)}</span>
    </span>
  )
}
