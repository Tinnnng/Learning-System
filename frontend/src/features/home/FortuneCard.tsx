/**
 * 每日抽籤：純屬好玩。一天一支（記在後端，手機和電腦看到同一支），按下去籤筒搖一搖再翻出籤詩。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/Button'
import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { cx } from '@/lib/cx'

type Fortune = components['schemas']['Fortune']
type FortuneToday = components['schemas']['FortuneToday']

const GOOD_LEVELS = new Set(['大吉', '中吉'])

/** 籤筒：三支竹籤插在筒裡，抽的時候整個搖一搖 */
function Canister({ shaking }: { shaking: boolean }) {
  return (
    <svg
      viewBox="0 0 64 80"
      aria-hidden="true"
      className={cx('h-20 w-16 flex-none text-accent', shaking && 'animate-[fortune-shake_520ms_var(--ease-out)_2]')}
    >
      <g stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none">
        <path d="M24 30 L20 6" />
        <path d="M32 30 L32 2" />
        <path d="M40 30 L45 8" />
        <path d="M14 30 h36 l-4 44 a3 3 0 0 1 -3 3 h-22 a3 3 0 0 1 -3 -3 z" fill="var(--sheet)" />
        <path d="M17 44 h30" strokeDasharray="2 3" />
      </g>
      <text x="32" y="64" textAnchor="middle" fontSize="12" fill="currentColor" fontFamily="var(--font-display)">
        籤
      </text>
    </svg>
  )
}

function Slip({ fortune }: { fortune: Fortune }) {
  const good = GOOD_LEVELS.has(fortune.level)
  return (
    <div className="flex flex-col gap-3 animate-[rise-in_var(--dur-slow)_var(--ease-out)]">
      <div className="flex items-baseline gap-3">
        <span className={cx('font-display text-3xl font-bold leading-none', good ? 'text-bad' : 'text-ink')}>{fortune.level}</span>
        <span className="text-xs text-muted">今日籤</span>
      </div>
      <p className="m-0 text-[15px] leading-relaxed text-ink">{fortune.line}</p>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-ok">宜</dt>
        <dd className="m-0 text-ink-soft">{fortune.good}</dd>
        <dt className="text-bad">忌</dt>
        <dd className="m-0 text-ink-soft">{fortune.bad}</dd>
        <dt className="text-accent">幸運</dt>
        <dd className="m-0 text-ink-soft">{fortune.lucky}</dd>
      </dl>
    </div>
  )
}

export function FortuneCard() {
  const queryClient = useQueryClient()
  const today = useQuery({ queryKey: ['activity', 'fortune'], queryFn: () => api.get<FortuneToday>('/activity/fortune') })
  const draw = useMutation({
    mutationFn: async () => {
      // 先搖一下籤筒再揭曉（減少動態效果時直接揭曉）
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      const [fortune] = await Promise.all([
        api.post<Fortune>('/activity/fortune'),
        new Promise((resolve) => window.setTimeout(resolve, reduce ? 0 : 1050)),
      ])
      return fortune
    },
    onSuccess: (fortune) => queryClient.setQueryData<FortuneToday>(['activity', 'fortune'], { fortune }),
  })
  const fortune = today.data?.fortune ?? null

  return (
    <section aria-labelledby="fortune-title" className="flex flex-col gap-4 rounded-lg bg-sheet px-5 py-6 shadow-sheet sm:px-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="fortune-title" className="eyebrow m-0">
          每日抽籤
        </h2>
        <span className="text-xs text-muted">純屬好玩・一天一支</span>
      </div>
      <div aria-live="polite">
        {fortune ? (
          <Slip fortune={fortune} />
        ) : today.isSuccess ? (
          <div className="flex items-center gap-5">
            <Canister shaking={draw.isPending} />
            <div className="flex flex-col items-start gap-3">
              <p className="m-0 text-sm text-muted">讀書前抽一支，看看今天的考運。</p>
              <Button onClick={() => draw.mutate()} disabled={draw.isPending}>
                {draw.isPending ? '搖籤中…' : '抽今天的籤'}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
      {draw.isError && <p className="m-0 text-sm text-bad">沒有抽到，請再試一次。</p>}
    </section>
  )
}
