/**
 * 番茄鐘：全站共用一個計時器（換頁不會停），狀態記在 localStorage，重新整理也接得上。
 * 用「結束時刻」計算剩餘時間，不靠 setInterval 累加：手機切到背景、計時器被暫停，回來時間還是準的。
 * 專心時間到 → 自動開始休息；休息到 → 回到待命。時間到會響一聲、震動，允許通知的話也跳通知。
 */

import { useEffect, useState, useSyncExternalStore } from 'react'

export type Phase = 'idle' | 'focus' | 'break'

export interface PomodoroState {
  phase: Phase
  /** 進行中：結束的時間戳（毫秒） */
  endsAt: number | null
  /** 暫停中：剩幾毫秒 */
  pausedLeft: number | null
  focusMinutes: number
  breakMinutes: number
  /** 今天完成幾個番茄（key 是 YYYY-MM-DD） */
  done: { day: string; count: number }
}

const STORAGE_KEY = 'ls-pomodoro'
const listeners = new Set<() => void>()
const dayKey = () => new Date().toLocaleDateString('en-CA')

function load(): PomodoroState {
  const fallback: PomodoroState = {
    phase: 'idle',
    endsAt: null,
    pausedLeft: null,
    focusMinutes: 25,
    breakMinutes: 5,
    done: { day: dayKey(), count: 0 },
  }
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null') as PomodoroState | null
    return saved ? { ...fallback, ...saved } : fallback
  } catch {
    return fallback
  }
}

let state = load()

function set(next: Partial<PomodoroState>) {
  state = { ...state, ...next }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // 存不了（無痕模式）：這次開著的頁面仍然有效
  }
  for (const listener of listeners) listener()
}

const minutes = (phase: Phase) => (phase === 'break' ? state.breakMinutes : state.focusMinutes) * 60_000

export const pomodoro = {
  start() {
    void notify.ask()
    set({ phase: 'focus', endsAt: Date.now() + minutes('focus'), pausedLeft: null })
  },
  pause() {
    if (state.endsAt) set({ pausedLeft: Math.max(0, state.endsAt - Date.now()), endsAt: null })
  },
  resume() {
    if (state.pausedLeft !== null) set({ endsAt: Date.now() + state.pausedLeft, pausedLeft: null })
  },
  reset() {
    set({ phase: 'idle', endsAt: null, pausedLeft: null })
  },
  /** 直接跳到下一段（專心 → 休息、休息 → 待命） */
  skip() {
    finish(false)
  },
  setLengths(focusMinutes: number, breakMinutes: number) {
    set({ focusMinutes, breakMinutes })
  },
}

function finish(alert = true) {
  if (state.phase === 'focus') {
    const today = dayKey()
    const count = state.done.day === today ? state.done.count + 1 : 1
    set({ phase: 'break', endsAt: Date.now() + minutes('break'), pausedLeft: null, done: { day: today, count } })
    if (alert) notify.fire('專心時間結束', `完成第 ${count} 個番茄，休息 ${state.breakMinutes} 分鐘吧。`)
  } else if (state.phase === 'break') {
    set({ phase: 'idle', endsAt: null, pausedLeft: null })
    if (alert) notify.fire('休息結束', '準備好就開始下一個番茄。')
  }
}

// 每秒檢查一次有沒有到時間（只有一個計時器，全站共用）
window.setInterval(() => {
  if (state.endsAt !== null && Date.now() >= state.endsAt) finish()
}, 1000)
// 從背景回來時立刻檢查
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && state.endsAt !== null && Date.now() >= state.endsAt) finish()
})

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function usePomodoro(): PomodoroState {
  return useSyncExternalStore(subscribe, () => state)
}

/** 剩幾秒（每秒更新）；待命時是整段的長度 */
export function useRemaining(current: PomodoroState): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (current.endsAt === null) return
    const timer = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(timer)
  }, [current.endsAt])
  if (current.endsAt !== null) return Math.max(0, Math.ceil((current.endsAt - now) / 1000))
  if (current.pausedLeft !== null) return Math.ceil(current.pausedLeft / 1000)
  return (current.phase === 'break' ? current.breakMinutes : current.focusMinutes) * 60
}

export function todayCount(current: PomodoroState): number {
  return current.done.day === dayKey() ? current.done.count : 0
}

/** 時間到的提醒：響一聲（Web Audio，不用音檔）＋震動＋通知（使用者允許的話） */
const notify = {
  async ask() {
    try {
      if ('Notification' in window && Notification.permission === 'default') await Notification.requestPermission()
    } catch {
      // 有些瀏覽器（iPhone Safari 非主畫面模式）不支援通知，只用聲音提醒
    }
  },
  fire(title: string, body: string) {
    chime()
    navigator.vibrate?.([200, 100, 200])
    try {
      if ('Notification' in window && Notification.permission === 'granted' && document.hidden) new Notification(title, { body })
    } catch {
      // 通知失敗不影響計時
    }
  },
}

function chime() {
  try {
    const context = new AudioContext()
    const now = context.currentTime
    // 兩個音的「叮—咚」，像桌上的小鈴
    for (const [index, frequency] of [880, 660].entries()) {
      const oscillator = context.createOscillator()
      const gain = context.createGain()
      oscillator.type = 'sine'
      oscillator.frequency.value = frequency
      gain.gain.setValueAtTime(0.0001, now + index * 0.35)
      gain.gain.exponentialRampToValueAtTime(0.3, now + index * 0.35 + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + index * 0.35 + 1.2)
      oscillator.connect(gain).connect(context.destination)
      oscillator.start(now + index * 0.35)
      oscillator.stop(now + index * 0.35 + 1.3)
    }
    window.setTimeout(() => void context.close(), 2500)
  } catch {
    // 沒有聲音就算了
  }
}
