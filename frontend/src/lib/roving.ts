/**
 * 單選群組的鍵盤操作（WAI-ARIA radio group）：整組只有一個 Tab 停留點，
 * 用方向鍵在選項之間移動（←↑ 上一個、→↓ 下一個，頭尾相接；Home／End 跳到第一個／最後一個）。
 *
 * select = true：移過去就選下去（分段選擇、日夜切換這類選了不會怎樣的設定）。
 * select = false：只移動焦點，按空白鍵或 Enter 才選（作答選項：選下去就會送出答案，不能讓方向鍵代替作答）。
 */

import type { KeyboardEvent } from 'react'

const ITEMS = '[role="radio"], [role="checkbox"]'
const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

export function onRovingKeyDown(event: KeyboardEvent<HTMLElement>, select = true) {
  const { key } = event
  if (!(key in STEP) && key !== 'Home' && key !== 'End') return
  if (event.altKey || event.ctrlKey || event.metaKey) return
  const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(ITEMS)).filter(
    (item) => !(item as HTMLButtonElement).disabled,
  )
  const index = items.indexOf(document.activeElement as HTMLElement)
  if (index < 0 || items.length === 0) return
  const next = key === 'Home' ? 0 : key === 'End' ? items.length - 1 : (index + STEP[key] + items.length) % items.length
  event.preventDefault()
  items[next].focus()
  if (select && items[next].getAttribute('aria-checked') !== 'true') items[next].click()
}

/** 群組裡哪一個選項可以用 Tab 移到：選中的那個；都沒選時是第一個。 */
export function rovingTabIndex(checked: boolean, index: number, anyChecked: boolean): 0 | -1 {
  return checked || (!anyChecked && index === 0) ? 0 : -1
}
