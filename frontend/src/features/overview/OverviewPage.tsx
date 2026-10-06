/** 作答總覽：整體數字、最近 30 天作答量、各科與各標籤正確率（低的排前面，一眼看出弱點）。 */

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { ButtonLink } from '@/components/Button'
import { cx } from '@/lib/cx'
import { percent, shortName } from '@/lib/format'
import type { Overview } from '@/lib/types'

const fetchOverview = () => api.get<Overview>('/review/overview')

function lastDays(count: number): string[] {
  const days: string[] = []
  const today = new Date()
  for (let offset = count - 1; offset >= 0; offset -= 1) {
    const date = new Date(today)
    date.setDate(today.getDate() - offset)
    days.push(date.toLocaleDateString('en-CA', { timeZone: 'Asia/Taipei' }))
  }
  return days
}

/** 最近 30 天：每天一欄，高度是作答題數，深色部分是答對 */
function Activity({ daily }: { daily: Overview['daily'] }) {
  const byDay = new Map(daily.map((entry) => [entry.day, entry]))
  const days = lastDays(30)
  const max = Math.max(10, ...daily.map((entry) => entry.attempts))
  return (
    <figure className="m-0 flex flex-col gap-3">
      <div className="flex h-36 items-end gap-[3px]" role="img" aria-label="最近 30 天每日作答題數">
        {days.map((day) => {
          const entry = byDay.get(day)
          const attempts = entry?.attempts ?? 0
          const correct = entry?.correct ?? 0
          return (
            <div key={day} className="group relative flex h-full flex-1 flex-col justify-end" title={`${day.slice(5)}：${attempts} 題，答對 ${correct}`}>
              <div
                className="flex w-full flex-col justify-end overflow-hidden rounded-t-[3px] bg-rule transition-[height] duration-[var(--dur-slow)]"
                style={{ height: `${(attempts / max) * 100}%`, minHeight: attempts ? 3 : 0 }}
              >
                <div className="w-full bg-ink" style={{ height: attempts ? `${(correct / attempts) * 100}%` : 0 }} />
              </div>
              {attempts === 0 && <div className="h-[3px] w-full rounded-full bg-line" />}
            </div>
          )
        })}
      </div>
      <figcaption className="flex justify-between text-xs text-muted">
        <span>{days[0].slice(5).replace('-', '/')}</span>
        <span className="flex gap-4">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-[2px] bg-ink" /> 答對
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-[2px] bg-rule" /> 答錯
          </span>
        </span>
        <span>今天</span>
      </figcaption>
    </figure>
  )
}

function AccuracyList({ title, stats }: { title: string; stats: Overview['by_subject'] }) {
  if (stats.length === 0) return null
  return (
    <section className="flex flex-col gap-3" aria-label={title}>
      <h2 className="eyebrow m-0">{title}</h2>
      <ul className="m-0 flex list-none flex-col gap-4 p-0">
        {stats.map((stat) => {
          const weak = stat.accuracy < 0.6
          return (
            <li key={stat.name} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 gap-y-1.5">
              <span className="truncate text-sm text-ink">{shortName(stat.name)}</span>
              <span className={cx('tabular text-sm', weak ? 'text-accent' : 'text-ink')}>{percent(stat.accuracy)}</span>
              <span className="col-span-2 h-[6px] overflow-hidden rounded-full bg-line">
                <span
                  className={cx('block h-full rounded-full transition-[width] duration-[var(--dur-slow)]', weak ? 'bg-accent' : 'bg-ink')}
                  style={{ width: percent(stat.accuracy) }}
                />
              </span>
              <span className="col-span-2 text-xs text-muted">
                作答 {stat.attempts} 次・錯題本 {stat.wrong_book} 題
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function OverviewPage() {
  const overview = useQuery({ queryKey: ['review', 'overview'], queryFn: fetchOverview })
  if (overview.isPending) return <Loading />
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
  const data = overview.data

  return (
    <div className="flex flex-col gap-10">
      <PageHeader eyebrow="總覽" title="學習狀況" description="各科正確率由低到高排列，最上面的就是最需要加強的。" />
      {data.attempts === 0 ? (
        <EmptyState title="還沒有作答紀錄" action={<ButtonLink to="/bank">去寫題目</ButtonLink>}>
          寫完題目後，這裡會顯示每天的作答量和各科正確率。
        </EmptyState>
      ) : (
        <>
          <dl className="m-0 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-rule bg-rule sm:grid-cols-3 lg:grid-cols-6">
            {[
              ['整體正確率', percent(data.accuracy), true],
              ['作答次數', String(data.attempts), false],
              ['寫過的題目', String(data.answered_questions), false],
              ['錯題本', String(data.wrong_book), false],
              ['今天該複習', String(data.review_due), data.review_due > 0],
              ['已掌握', String(data.mastered), false],
            ].map(([label, value, emphasis]) => (
              <div key={String(label)} className="flex flex-col gap-1 bg-sheet px-5 py-4">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className={cx('tabular m-0 text-2xl', emphasis ? 'text-accent' : 'text-ink')}>{value}</dd>
              </div>
            ))}
          </dl>
          <section className="flex flex-col gap-3 rounded-lg bg-sheet p-5 shadow-sheet sm:p-7" aria-label="最近 30 天">
            <h2 className="eyebrow m-0">最近 30 天</h2>
            <Activity daily={data.daily} />
          </section>
          <div className="grid gap-10 md:grid-cols-2">
            <AccuracyList title="各科正確率" stats={data.by_subject} />
            <AccuracyList title="各主題正確率" stats={data.by_tag} />
          </div>
        </>
      )}
    </div>
  )
}
