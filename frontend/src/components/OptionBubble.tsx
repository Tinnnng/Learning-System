/**
 * 選項：選下去時，一道螢光筆從左刷到右（方向 B「螢光筆與原子筆」）。
 *
 * 狀態：
 * - idle：未選（滑過時淡色螢光筆整段刷過去，提示可以點）
 * - chosen：已選（尚未揭曉，例如模擬考）→ 黃色螢光筆
 * - right：選了而且對 → 綠色螢光筆
 * - wrong：選了但錯 → 粉紅螢光筆＋刪除線
 * - answer：沒選，但這是正確答案 → 延遲一拍刷上綠色，引導視線
 * - dimmed：揭曉後，與答案無關的選項（改用次要文字色，不降透明度，複習時仍讀得清楚）
 *
 * readOnly：題庫預覽、搜尋、錯題本等只是展示的地方，畫成一般文字（不是按鈕、沒有 radio 語意）。
 * disabled：作答中暫時不能選（送出中、已揭曉）。用 aria-disabled 而不是 disabled，
 *           鍵盤使用者剛按下的選項才不會失去焦點。
 */

import type { CSSProperties, ReactNode } from 'react'
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
  readOnly?: boolean
  /** 單選群組只有一個 Tab 停留點（見 lib/roving.ts），由群組決定 */
  tabIndex?: number
  onSelect?: () => void
}

const MARKER_COLOR: Partial<Record<BubbleState, string>> = {
  chosen: 'var(--hl)',
  right: 'var(--ok-hl)',
  wrong: 'var(--bad-hl)',
  answer: 'var(--ok-hl)',
}

export function OptionBubble({ letter, text, state, disabled, multiple, readOnly, tabIndex, onSelect }: OptionBubbleProps) {
  const color = MARKER_COLOR[state]
  const selected = state === 'chosen' || state === 'right' || state === 'wrong'
  const inactive = disabled || readOnly

  const content: ReactNode = (
    <>
      <span
        aria-hidden="true"
        className={cx(
          'mt-[2px] w-5 flex-none text-center font-hand text-lg leading-6 transition-colors duration-[var(--dur)]',
          state === 'right' || state === 'answer'
            ? 'text-ok'
            : state === 'wrong'
              ? 'text-bad'
              : state === 'dimmed'
                ? 'text-muted'
                : 'text-accent',
        )}
      >
        {letter}
      </span>

      <span className={cx('min-w-0 flex-1 pt-0.5 text-question leading-[1.75]', state === 'dimmed' && 'text-muted')}>
        <span
          className={cx(
            // 長選項換行時，螢光筆會一路刷過每一行（見 index.css 的 .marker-text）。
            // 滑過未選的選項：淡色螢光筆整段刷過去預覽（和文字一樣長）；選下去再用正式顏色刷一次
            'marker-text [--marker-scale:0]',
            !inactive && !color && 'group-hover:[--marker-hover:1] group-focus-visible:[--marker-hover:1]',
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
          <Icon name="check" size={18} label={state === 'right' ? '答對' : undefined} />
          {state === 'answer' && <span>正解</span>}
        </span>
      )}
      {state === 'wrong' && (
        <span className="mt-1.5 flex-none text-bad">
          <Icon name="close" size={18} label="答錯" />
        </span>
      )}
    </>
  )

  if (readOnly) {
    return <div className="flex w-full items-start gap-3.5 rounded-md px-3 py-2.5">{content}</div>
  }

  return (
    <button
      type="button"
      role={multiple ? 'checkbox' : 'radio'}
      aria-checked={selected}
      aria-disabled={disabled || undefined}
      tabIndex={tabIndex}
      onClick={disabled ? undefined : onSelect}
      className={cx(
        'group relative flex w-full items-start gap-3.5 rounded-md px-3 py-2.5 text-left',
        'transition-[background-color] duration-[var(--dur)] ease-out',
        disabled ? 'cursor-default' : 'hover:bg-sheet-tint',
      )}
    >
      {content}
    </button>
  )
}
