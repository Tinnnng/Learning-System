/**
 * 番茄鐘：全站共用一個計時器（換頁不會停），狀態記在 localStorage，重新整理也接得上。
 * 用「結束時刻」計算剩餘時間，不靠 setInterval 累加：手機切到背景、計時器被暫停，回來時間還是準的。
 * 專心時間到 → 自動開始休息；休息到 → 回到待命。時間到會響一聲、震動，允許通知的話也跳通知。
 * 開好幾個分頁時，localStorage 才是準的：每次動作與檢查前都先讀回最新狀態，避免舊分頁把別的分頁的暫停蓋掉。
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
const dayKey = (at: number = Date.now()) => new Date(at).toLocaleDateString('en-CA')
/** 時間到超過這麼久才發現（瀏覽器關著、分頁被丟棄）：不響鈴、不跳通知 */
const LATE_ALERT_MS = 60_000

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
/** 每一份狀態是什麼時候產生的：剛按開始／繼續時，畫面用這個時刻算剩餘時間，不會拿到按之前的舊時刻 */
const stampedAt = new WeakMap<PomodoroState, number>([[state, Date.now()]])
/** 這個分頁最後一次讀到或寫入的內容，用來判斷別的分頁有沒有改過 */
let lastRaw: string | null = readRaw()

function readRaw(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function emit() {
  for (const listener of listeners) listener()
}

/** 別的分頁改過狀態就讀回來 */
function refresh() {
  const raw = readRaw()
  if (raw === lastRaw) return
  lastRaw = raw
  state = load()
  stampedAt.set(state, Date.now())
  emit()
}

function set(next: Partial<PomodoroState>) {
  state = { ...state, ...next }
  stampedAt.set(state, Date.now())
  try {
    lastRaw = JSON.stringify(state)
    localStorage.setItem(STORAGE_KEY, lastRaw)
  } catch {
    // 存不了（無痕模式）：這次開著的頁面仍然有效
  }
  emit()
}

const minutes = (phase: Phase) => (phase === 'break' ? state.breakMinutes : state.focusMinutes) * 60_000

export const pomodoro = {
  start() {
    refresh()
    void notify.ask()
    set({ phase: 'focus', endsAt: Date.now() + minutes('focus'), pausedLeft: null })
  },
  pause() {
    refresh()
    if (state.endsAt) set({ pausedLeft: Math.max(0, state.endsAt - Date.now()), endsAt: null })
  },
  resume() {
    refresh()
    if (state.pausedLeft !== null) set({ endsAt: Date.now() + state.pausedLeft, pausedLeft: null })
  },
  reset() {
    refresh()
    set({ phase: 'idle', endsAt: null, pausedLeft: null })
  },
  /** 直接跳到下一段（專心 → 休息、休息 → 待命）。提早休息不算完成一個番茄 */
  skip() {
    refresh()
    if (state.phase === 'focus') set({ phase: 'break', endsAt: Date.now() + minutes('break'), pausedLeft: null })
    else if (state.phase === 'break') set({ phase: 'idle', endsAt: null, pausedLeft: null })
  },
  setLengths(focusMinutes: number, breakMinutes: number) {
    refresh()
    set({ focusMinutes, breakMinutes })
  },
}

/** 時間到：下一段從這一段「應該結束的時刻」起算，不是從發現的時刻；中間整段都過了就一路跳過 */
function finish() {
  const now = Date.now()
  if (state.endsAt === null || now < state.endsAt) return
  const endedAt = state.endsAt
  const alert = now - endedAt < LATE_ALERT_MS
  if (state.phase === 'focus') {
    // 番茄記在實際完成的那一天
    const day = dayKey(endedAt)
    const count = state.done.day === day ? state.done.count + 1 : 1
    const breakEnds = endedAt + minutes('break')
    if (now >= breakEnds) {
      set({ phase: 'idle', endsAt: null, pausedLeft: null, done: { day, count } })
      return
    }
    set({ phase: 'break', endsAt: breakEnds, pausedLeft: null, done: { day, count } })
    if (alert) notify.fire('專心時間結束', `完成第 ${count} 個番茄，休息 ${state.breakMinutes} 分鐘吧。`)
  } else if (state.phase === 'break') {
    set({ phase: 'idle', endsAt: null, pausedLeft: null })
    if (alert) notify.fire('休息結束', '準備好就開始下一個番茄。')
  }
}

function check() {
  refresh()
  if (state.endsAt !== null && Date.now() >= state.endsAt) finish()
}

// 每秒檢查一次有沒有到時間（只有一個計時器，全站共用）
window.setInterval(check, 1000)
// 從背景回來時立刻檢查
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) check()
})
// 別的分頁改了狀態：馬上跟著更新畫面
window.addEventListener('storage', (event) => {
  if (event.key === STORAGE_KEY || event.key === null) refresh()
})
// 打開頁面時，關著的期間可能已經時間到
check()

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
  // 待命、暫停時 now 停在舊時刻；狀態剛變（按開始／繼續）的第一個畫面改用狀態產生的時刻
  const at = Math.max(now, stampedAt.get(current) ?? 0)
  if (current.endsAt !== null) return Math.max(0, Math.ceil((current.endsAt - at) / 1000))
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
