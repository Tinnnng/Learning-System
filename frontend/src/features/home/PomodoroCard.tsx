/**
 * 番茄鐘＋白噪音（首頁）。計時與聲音都是全站共用的（lib/pomodoro、lib/noise），離開首頁也不會停，
 * 計時中頁首會有小計時（components/PomodoroChip）。
 */

import type { CSSProperties } from 'react'
import { Button } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { cx } from '@/lib/cx'
import { clock } from '@/lib/format'
import { NOISE_LABELS, type NoiseKind, noise, useNoise } from '@/lib/noise'
import { pomodoro, todayCount, usePomodoro, useRemaining } from '@/lib/pomodoro'
import { onRovingKeyDown, rovingTabIndex } from '@/lib/roving'

const LENGTHS: Array<[number, number]> = [
  [25, 5],
  [50, 10],
  [15, 3],
]

export function PomodoroCard() {
  const timer = usePomodoro()
  const left = useRemaining(timer)
  const sound = useNoise()
  const running = timer.endsAt !== null
  const paused = timer.pausedLeft !== null
  const total = (timer.phase === 'break' ? timer.breakMinutes : timer.focusMinutes) * 60
  const progress = timer.phase === 'idle' ? 0 : 1 - left / total
  const count = todayCount(timer)

  return (
    <section aria-labelledby="pomodoro-title" className="flex flex-col gap-4 rounded-lg bg-sheet px-5 py-6 shadow-sheet sm:px-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="pomodoro-title" className="eyebrow m-0">
          番茄鐘
        </h2>
        <span className="text-xs text-muted">今天完成 {count} 個</span>
      </div>

      <div className="flex items-center gap-5">
        {/* 原子筆畫的圓：時間過去多少就畫多少 */}
        <svg viewBox="0 0 100 100" className="h-24 w-24 flex-none -rotate-90" aria-hidden="true">
          <circle cx="50" cy="50" r="44" fill="none" stroke="var(--line)" strokeWidth="5" />
          <circle
            cx="50"
            cy="50"
            r="44"
            fill="none"
            stroke={timer.phase === 'break' ? 'var(--ok)' : 'var(--accent)'}
            strokeWidth="5"
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            style={{ strokeDashoffset: 1 - progress, transition: 'stroke-dashoffset 1s linear' } as CSSProperties}
          />
        </svg>
        <div className="flex min-w-0 flex-col gap-1">
          <span className={cx('text-sm', timer.phase === 'break' ? 'text-ok' : 'text-muted')}>
            {timer.phase === 'focus' ? (paused ? '暫停中' : '專心中') : timer.phase === 'break' ? '休息一下' : '準備開始'}
          </span>
          <span className="tabular font-display text-4xl font-bold leading-none text-ink" role="timer" aria-label={`剩 ${clock(left)}`}>
            {clock(left)}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {timer.phase === 'idle' ? (
          <Button onClick={pomodoro.start}>
            <Icon name="play" size={16} />
            開始專心
          </Button>
        ) : running ? (
          <Button variant="secondary" onClick={pomodoro.pause}>
            暫停
          </Button>
        ) : (
          <Button onClick={pomodoro.resume}>
            <Icon name="play" size={16} />
            繼續
          </Button>
        )}
        {timer.phase !== 'idle' && (
          <>
            <Button variant="ghost" onClick={pomodoro.skip}>
              {timer.phase === 'focus' ? '提早休息' : '結束休息'}
            </Button>
            <Button variant="ghost" onClick={pomodoro.reset}>
              重來
            </Button>
          </>
        )}
      </div>

      {timer.phase === 'idle' && (
        <div role="radiogroup" aria-label="時間長度" className="flex flex-wrap gap-2" onKeyDown={(event) => onRovingKeyDown(event)}>
          {LENGTHS.map(([focus, rest], index) => {
            const active = timer.focusMinutes === focus && timer.breakMinutes === rest
            const anyActive = LENGTHS.some(([f, r]) => timer.focusMinutes === f && timer.breakMinutes === r)
            return (
              <button
                key={focus}
                type="button"
                role="radio"
                aria-checked={active}
                tabIndex={rovingTabIndex(active, index, anyActive)}
                onClick={() => pomodoro.setLengths(focus, rest)}
                className={cx(
                  'hit h-8 rounded-full border px-3 text-xs transition-colors',
                  active ? 'border-ink bg-ink text-paper' : 'border-line bg-sheet text-ink-soft hover:border-rule',
                )}
              >
                {focus}＋{rest} 分
              </button>
            )
          })}
        </div>
      )}

      <div className="flex flex-col gap-2 border-t border-rule pt-4">
        <span className="text-xs text-muted">背景聲音</span>
        <div className="flex flex-wrap gap-2" role="group" aria-label="背景聲音">
          {(Object.keys(NOISE_LABELS) as NoiseKind[]).map((kind) => {
            const active = sound.playing === kind
            return (
              <button
                key={kind}
                type="button"
                aria-pressed={active}
                onClick={() => (active ? noise.stop() : void noise.play(kind))}
                className={cx(
                  'hit inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs transition-colors',
                  active ? 'border-accent bg-accent-faint text-accent-strong' : 'border-line bg-sheet text-ink-soft hover:border-rule',
                )}
              >
                {active && <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
                {NOISE_LABELS[kind]}
              </button>
            )
          })}
        </div>
        {sound.playing && (
          <label className="flex items-center gap-3 text-xs text-muted">
            音量
            <input
              type="range"
              min={0.05}
              max={1}
              step={0.05}
              value={sound.volume}
              onChange={(event) => noise.setVolume(Number(event.target.value))}
              className="h-11 flex-1 accent-[var(--accent)]"
            />
          </label>
        )}
      </div>
    </section>
  )
}
