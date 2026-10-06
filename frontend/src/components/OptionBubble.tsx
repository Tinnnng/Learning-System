/**
 * 選項：答案卡上的橢圓劃記格。選取時像 2B 鉛筆一樣由中心塗滿。
 *
 * 狀態：
 * - idle：未選
 * - chosen：已選（尚未揭曉，例如模擬考）
 * - right：選了而且對
 * - wrong：選了但錯
 * - answer：沒選，但這是正確答案（揭曉後提示）
 * - dimmed：揭曉後，與答案無關的選項
 */

import { RichText } from '@/components/RichText'
import { Icon } from '@/components/Icon'
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

const filled = (state: BubbleState) => state === 'chosen' || state === 'right' || state === 'wrong'

export function OptionBubble({ letter, text, state, disabled, multiple, onSelect }: OptionBubbleProps) {
  const isFilled = filled(state)
  return (
    <button
      type="button"
      role={multiple ? 'checkbox' : 'radio'}
      aria-checked={isFilled}
      disabled={disabled}
      onClick={onSelect}
      className={cx(
        'group relative flex w-full items-start gap-4 rounded-md px-3 py-2.5 text-left',
        'transition-colors duration-[var(--dur)] ease-out',
        !disabled && 'hover:bg-sheet-tint',
        state === 'right' && 'bg-ok-soft/60',
        state === 'wrong' && 'bg-bad-soft/60',
        state === 'answer' && 'bg-ok-soft/40',
      )}
    >
      {/* 橢圓劃記格 */}
      <span
        className={cx(
          'relative mt-0.5 grid h-8 w-[22px] flex-none place-items-center overflow-hidden rounded-full border-[1.5px]',
          'transition-[border-color,box-shadow] duration-[var(--dur)]',
          state === 'answer' ? 'border-ok border-2' : isFilled ? 'border-ink' : 'border-print',
          state === 'dimmed' && 'opacity-50',
          state === 'right' && 'shadow-[0_0_0_3px_color-mix(in_srgb,var(--ok)_35%,transparent)]',
          state === 'wrong' && 'shadow-[0_0_0_3px_color-mix(in_srgb,var(--bad)_30%,transparent)]',
          !disabled && !isFilled && 'group-hover:border-[2px]',
        )}
        aria-hidden="true"
      >
        <span
          className={cx(
            'absolute inset-0 rounded-full',
            'bg-[radial-gradient(circle_at_35%_30%,color-mix(in_srgb,var(--ink)_68%,transparent),var(--ink)_72%)]',
            'origin-center transition-transform duration-[var(--dur-slow)] ease-[var(--ease-draw)]',
            isFilled ? 'scale-100' : 'scale-0',
          )}
        />
        <span
          className={cx(
            'relative font-mono text-xs font-medium transition-colors duration-[var(--dur)]',
            isFilled ? 'text-transparent' : state === 'answer' ? 'text-ok' : 'text-print',
          )}
        >
          {letter}
        </span>
      </span>

      <span
        className={cx(
          'min-w-0 flex-1 pt-0.5 font-serif text-question leading-[1.75]',
          state === 'wrong' && 'line-through decoration-bad decoration-2',
          state === 'dimmed' && 'text-muted',
        )}
      >
        <span className="sr-only">選項 {letter}：</span>
        <RichText inline>{text}</RichText>
      </span>

      {(state === 'right' || state === 'answer') && (
        <span className="mt-1.5 flex flex-none items-center gap-1 text-sm font-medium text-ok">
          <Icon name="check" size={18} />
          {state === 'answer' && <span>正確答案</span>}
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
