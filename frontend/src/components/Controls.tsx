/** 表單控制項：分段選擇、開關、篩選標籤。 */

import { type ReactNode, useId } from 'react'
import { cx } from '@/lib/cx'

interface SegmentedProps<T extends string> {
  label: string
  value: T
  options: Array<{ value: T; label: ReactNode; hint?: ReactNode }>
  onChange: (value: T) => void
  className?: string
}

/** 分段選擇（單選）。每個選項可以附一行說明。 */
export function Segmented<T extends string>({ label, value, options, onChange, className }: SegmentedProps<T>) {
  return (
    <div role="radiogroup" aria-label={label} className={cx('grid gap-2', className)} style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={cx(
              'flex flex-col items-start gap-0.5 rounded-md border px-3.5 py-2.5 text-left transition-[border-color,background-color,box-shadow] duration-[var(--dur)]',
              active
                ? 'border-ink bg-sheet shadow-[inset_0_0_0_1px_var(--ink)]'
                : 'border-line bg-sheet hover:border-print-rule',
            )}
          >
            <span className={cx('text-sm font-medium', active ? 'text-ink' : 'text-ink-soft')}>{option.label}</span>
            {option.hint && <span className="text-xs text-muted">{option.hint}</span>}
          </button>
        )
      })}
    </div>
  )
}

interface SwitchProps {
  label: ReactNode
  description?: ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
}

/** 開關：外觀是一個可以塗滿的橢圓格，延續答案卡的語言。 */
export function Switch({ label, description, checked, onChange }: SwitchProps) {
  const id = useId()
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-3 py-1">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cx(
          'relative mt-0.5 h-6 w-10 flex-none rounded-full border-[1.5px] transition-colors duration-[var(--dur)]',
          checked ? 'border-ink bg-ink' : 'border-line bg-sheet',
        )}
      >
        <span
          className={cx(
            'absolute top-1/2 h-[14px] w-[14px] -translate-y-1/2 rounded-full transition-[left,background-color] duration-[var(--dur)] ease-[var(--ease-out)]',
            checked ? 'left-[19px] bg-paper' : 'left-[4px] bg-muted/60',
          )}
        />
      </button>
      <span className="flex flex-col">
        <span className="text-sm text-ink">{label}</span>
        {description && <span className="text-xs text-muted">{description}</span>}
      </span>
    </label>
  )
}

interface ChipGroupProps<T extends string | number> {
  label: string
  value: T | null
  options: Array<{ value: T; label: ReactNode }>
  onChange: (value: T | null) => void
}

/** 篩選標籤：點一下選、再點一下取消。 */
export function ChipGroup<T extends string | number>({ label, value, options, onChange }: ChipGroupProps<T>) {
  if (options.length === 0) return null
  return (
    <fieldset className="m-0 flex flex-wrap items-center gap-2 border-0 p-0">
      <legend className="float-left mr-1 w-14 text-xs text-muted">{label}</legend>
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={String(option.value)}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(active ? null : option.value)}
            className={cx(
              'h-8 rounded-full border px-3 text-sm transition-colors duration-[var(--dur-fast)]',
              active ? 'border-ink bg-ink text-paper' : 'border-line bg-sheet text-ink-soft hover:border-print-rule',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </fieldset>
  )
}
