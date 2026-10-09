/**
 * 作答與單字測驗的單鍵快捷鍵（1–9、A–J）開關，記在 localStorage，所有頁面共用同一個設定。
 * 語音輸入或容易誤觸鍵盤的人可以關掉（WCAG 2.1.4）；方向鍵不是字元鍵，不受影響。
 */

import { useSyncExternalStore } from 'react'

const STORAGE_KEY = 'ls-shortcuts'
const listeners = new Set<() => void>()

function read(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== 'off'
  } catch {
    return true
  }
}

let enabled = read()

export function setShortcutsEnabled(value: boolean) {
  enabled = value
  try {
    localStorage.setItem(STORAGE_KEY, value ? 'on' : 'off')
  } catch {
    // 無痕模式等存不了：這次開著的頁面仍然有效
  }
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useShortcutsEnabled(): boolean {
  return useSyncExternalStore(subscribe, () => enabled)
}
