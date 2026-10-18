import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// 每次重新載入模組，模擬「新開一個分頁」或「重新整理」
const fresh = async () => {
  vi.resetModules()
  return import('./pomodoro')
}
const saved = () => JSON.parse(localStorage.getItem('ls-pomodoro')!)
const MINUTE = 60_000

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ now: new Date('2026-10-17T09:00:00+08:00') })
})
afterEach(() => vi.useRealTimers())

describe('番茄鐘', () => {
  it('暫停 10 分鐘後按繼續，第一個畫面就是正確的剩餘時間', async () => {
    const m = await fresh()
    const { result } = renderHook(() => m.useRemaining(m.usePomodoro()))
    act(() => m.pomodoro.start())
    act(() => void vi.advanceTimersByTime(MINUTE))
    act(() => m.pomodoro.pause())
    vi.setSystemTime(Date.now() + 10 * MINUTE)
    act(() => m.pomodoro.resume())
    expect(result.current).toBe(24 * 60)
  })

  it('待命一段時間後按開始，第一個畫面是整段長度', async () => {
    const m = await fresh()
    const { result } = renderHook(() => m.useRemaining(m.usePomodoro()))
    vi.setSystemTime(Date.now() + 10 * MINUTE)
    act(() => m.pomodoro.start())
    expect(result.current).toBe(25 * 60)
  })

  it('兩個分頁：A 暫停後，B 不會照舊時間結束、也不會多算一個番茄', async () => {
    const tabA = await fresh()
    tabA.pomodoro.start()
    await fresh() // 分頁 B 在 A 開始後載入
    tabA.pomodoro.pause()
    vi.advanceTimersByTime(25 * MINUTE + 1000)
    expect(saved().phase).toBe('focus')
    expect(saved().pausedLeft).not.toBeNull()
    expect(saved().done.count).toBe(0)
  })

  it('兩個分頁同時開著，時間到只算一個番茄', async () => {
    const tabA = await fresh()
    tabA.pomodoro.start()
    await fresh()
    vi.advanceTimersByTime(25 * MINUTE + 1500)
    expect(saved().phase).toBe('break')
    expect(saved().done.count).toBe(1)
  })

  it('專心中關掉瀏覽器，兩小時後打開：休息也早就結束，直接回到待命，番茄算進去', async () => {
    const endedAt = Date.now() - 2 * 3600_000
    localStorage.setItem(
      'ls-pomodoro',
      JSON.stringify({ phase: 'focus', endsAt: endedAt, pausedLeft: null, focusMinutes: 25, breakMinutes: 5, done: { day: '2026-10-17', count: 0 } }),
    )
    const m = await fresh()
    expect(saved().phase).toBe('idle')
    expect(m.todayCount(saved())).toBe(1)
  })

  it('專心時間到後 2 分鐘才發現：休息從專心結束的時刻起算', async () => {
    const m = await fresh()
    m.pomodoro.start()
    // 背景分頁計時器被暫停，2 分鐘後才檢查
    vi.setSystemTime(Date.now() + 27 * MINUTE)
    vi.advanceTimersByTime(1000)
    expect(saved().phase).toBe('break')
    expect(Math.round((saved().endsAt - Date.now()) / 1000)).toBe(3 * 60 - 1)
  })

  it('番茄記在實際完成的那一天', async () => {
    vi.setSystemTime(new Date('2026-10-17T23:40:00+08:00'))
    localStorage.setItem(
      'ls-pomodoro',
      JSON.stringify({
        phase: 'focus',
        endsAt: new Date('2026-10-17T23:50:00+08:00').getTime(),
        pausedLeft: null,
        focusMinutes: 25,
        breakMinutes: 5,
        done: { day: '2026-10-17', count: 2 },
      }),
    )
    vi.setSystemTime(new Date('2026-10-18T08:00:00+08:00'))
    const m = await fresh()
    expect(saved().done).toEqual({ day: '2026-10-17', count: 3 })
    expect(m.todayCount(saved())).toBe(0)
  })

  it('提早休息不算完成一個番茄', async () => {
    const m = await fresh()
    m.pomodoro.start()
    vi.advanceTimersByTime(5000)
    m.pomodoro.skip()
    expect(saved().phase).toBe('break')
    expect(m.todayCount(saved())).toBe(0)
  })
})
