import { Icon, type IconName } from '@/components/Icon'
import { cx } from '@/lib/cx'
import { type ThemePreference, useTheme } from '@/lib/theme'

const OPTIONS: Array<{ value: ThemePreference; label: string; icon: IconName }> = [
  { value: 'light', label: '日間', icon: 'sun' },
  { value: 'system', label: '跟隨系統', icon: 'system' },
  { value: 'dark', label: '夜間', icon: 'moon' },
]

/** 日間／跟隨系統／夜間 三段切換。 */
export function ThemeToggle({ className }: { className?: string }) {
  const { preference, setPreference } = useTheme()
  return (
    <div
      role="radiogroup"
      aria-label="外觀"
      className={cx('inline-flex rounded-full border border-line bg-sheet p-0.5', className)}
    >
      {OPTIONS.map((option) => {
        const active = preference === option.value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            title={option.label}
            onClick={() => setPreference(option.value)}
            className={cx(
              'grid h-8 w-8 place-items-center rounded-full transition-colors duration-[var(--dur)]',
              active ? 'bg-ink text-paper' : 'text-muted hover:text-ink',
            )}
          >
            <Icon name={option.icon} size={17} label={option.label} />
          </button>
        )
      })}
    </div>
  )
}
