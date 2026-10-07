/**
 * 選項：選下去時，一道螢光筆從左刷到右（方向 B「螢光筆與原子筆」）。
 *
 * 狀態：
 * - idle：未選（滑過時整列變亮，提示可以點）
 * - chosen：已選（尚未揭曉，例如模擬考）→ 黃色螢光筆
 * - right：選了而且對 → 綠色螢光筆
 * - wrong：選了但錯 → 粉紅螢光筆＋刪除線
 * - answer：沒選，但這是正確答案 → 延遲一拍刷上綠色，引導視線
 * - dimmed：揭曉後，與答案無關的選項
 */

import type { CSSProperties } from 'react'
import { Icon } from '@/components/Icon'
import { RichText } from '@/components/RichText'
import { cx } from '@/lib/cx'

export type BubbleState = 'idle' | 'chosen' | 'right' | 'wrong' | 'answer' | 'dimmed'

interface OptionBubbleProps {
  letter: string
  text: string
  state: BubbleState
  disabled?: boolean
  multiple?: boolean
  onSelect?: () => void
}

const MARKER_COLOR: Partial<Record<BubbleState, string>> = {
  chosen: 'var(--hl)',
  right: 'var(--ok-hl)',
  wrong: 'var(--bad-hl)',
  answer: 'var(--ok-hl)',
}

export function OptionBubble({ letter, text, state, disabled, multiple, onSelect }: OptionBubbleProps) {
  const color = MARKER_COLOR[state]
  const selected = state === 'chosen' || state === 'right' || state === 'wrong'

  return (
    <button
      type="button"
      role={multiple ? 'checkbox' : 'radio'}
      aria-checked={selected}
      disabled={disabled}
      onClick={onSelect}
      className={cx(
        'group relative flex w-full items-start gap-3.5 rounded-md px-3 py-2.5 text-left',
        'transition-[background-color,opacity] duration-[var(--dur)] ease-out',
        !disabled && 'hover:bg-sheet-tint',
        state === 'dimmed' && 'opacity-55',
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          'mt-[2px] w-5 flex-none text-center font-hand text-lg leading-6 transition-colors duration-[var(--dur)]',
          state === 'right' || state === 'answer' ? 'text-ok' : state === 'wrong' ? 'text-bad' : 'text-accent',
        )}
      >
        {letter}
      </span>

      <span className="min-w-0 flex-1 pt-0.5 text-question leading-[1.75]">
        <span
          className={cx(
            // 長選項換行時，螢光筆會一路刷過每一行（見 index.css 的 .marker-text）。
            // 滑過時只讓整列變亮，不先露出一小截螢光筆：只有選下去才刷，避免看起來像殘留的色塊
            'marker-text [--marker-scale:0]',
            state === 'answer' && 'delay-[220ms]',
            state === 'wrong' && 'line-through decoration-bad decoration-2',
          )}
          style={color ? ({ '--marker-color': color, '--marker-scale': 1 } as CSSProperties) : undefined}
        >
          <span className="sr-only">選項 {letter}：</span>
          <RichText inline>{text}</RichText>
        </span>
      </span>

      {(state === 'right' || state === 'answer') && (
        <span className="mt-1 flex flex-none items-center gap-1 font-hand text-base text-ok">
          <Icon name="check" size={18} />
          {state === 'answer' && <span>正解</span>}
        </span>
      )}
      {state === 'wrong' && (
        <span className="mt-1.5 flex-none text-bad">
          <Icon name="close" size={18} label="答錯" />
        </span>
      )}
    </button>
  )
}
