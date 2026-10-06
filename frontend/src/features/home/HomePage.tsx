import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Button, ButtonLink } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { PageHeader } from '@/components/PageHeader'
import { ErrorState, Loading } from '@/components/States'
import { cx } from '@/lib/cx'
import { formatDateTime, percent, score, shortName, todayLabel } from '@/lib/format'
import { useStartSession } from '@/lib/sessions'
import type { SessionSummary } from '@/lib/types'
import { fetchCountdown, fetchOverview, fetchPapers, fetchSessions, fetchVocabStats } from './api'

/** 一排短短的螢光筆劃記，用來表示「完成幾個」 */
function Bubbles({ total, done, label }: { total: number; done: number; label: string }) {
  return (
    <span className="flex gap-1.5" role="img" aria-label={label}>
      {Array.from({ length: total }, (_, index) => (
        <span
          key={index}
          className={cx(
            'h-2.5 w-6 rounded-[var(--radius-marker)] transition-colors duration-[var(--dur)]',
            index < done ? 'bg-hl' : 'bg-line',
          )}
        />
      ))}
    </span>
  )
}

interface TaskRowProps {
  index: number
  title: string
  detail: ReactNode
  status: ReactNode
  action: ReactNode
  done?: boolean
}

/** 今天的任務：左邊是手寫的編號，完成的項目整個標題被螢光筆劃過 */
function TaskRow({ index, title, detail, status, action, done }: TaskRowProps) {
  return (
    <li className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 border-b border-rule py-5 last:border-b-0 sm:grid-cols-[auto_1fr_auto] sm:items-center">
      <span
        className={cx('grid w-8 place-items-center font-hand text-2xl leading-none', done ? 'text-ok' : 'text-accent')}
        aria-hidden="true"
      >
        {done ? <Icon name="check" size={22} /> : index}
      </span>
      <div className="flex min-w-0 flex-col gap-1.5">
        <h3 className="m-0 text-base font-medium">
          <span className={cx('marker [--marker-color:var(--ok-hl)]', done ? '[--marker-scale:1]' : '[--marker-scale:0]')}>
            {title}
          </span>
        </h3>
        <div className="text-sm text-muted">{detail}</div>
        {status}
      </div>
      <div className="col-start-2 sm:col-start-3">{action}</div>
    </li>
  )
}

function SessionRow({ session }: { session: SessionSummary }) {
  const submitted = session.submitted_at !== null
  return (
    <li>
      <Link
        to={`/exam/${session.id}`}
        className="group grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-0.5 rounded-md px-3 py-3 transition-colors hover:bg-sheet-tint"
      >
        <span className="truncate font-medium">{shortName(session.title)}</span>
        <span className="tabular row-span-2 text-right text-sm">
          {submitted ? (
            <>
              <span className="text-ink">{score(session.score ?? 0)}</span>
              <span className="text-muted">／{score(session.max_score)}</span>
            </>
          ) : (
            <span className="text-accent">
              {session.answered_count}／{session.total} 題
            </span>
          )}
        </span>
        <span className="text-xs text-muted">
          {formatDateTime(session.started_at)}　{session.mode === 'mock' ? '模擬考' : '練習'}
        </span>
      </Link>
    </li>
  )
}

export function HomePage() {
  const vocab = useQuery({ queryKey: ['vocab', 'stats'], queryFn: fetchVocabStats })
  const overview = useQuery({ queryKey: ['review', 'overview'], queryFn: fetchOverview })
  const open = useQuery({ queryKey: ['exam', 'sessions', 'open'], queryFn: () => fetchSessions('open') })
  const recent = useQuery({ queryKey: ['exam', 'sessions', 'submitted'], queryFn: () => fetchSessions('submitted') })
  const papers = useQuery({ queryKey: ['bank', 'papers'], queryFn: fetchPapers })
  const startReview = useStartSession()
  const countdown = useQuery({ queryKey: ['calendar', 'countdown'], queryFn: fetchCountdown })
  const nextExam = countdown.data?.next_exam

  if (vocab.isPending || overview.isPending) return <Loading />
  if (vocab.isError || overview.isError) return <ErrorState error={vocab.error ?? overview.error} onRetry={() => vocab.refetch()} />

  const words = vocab.data
  const stats = overview.data
  const dailyDone = words.daily_done >= words.daily_total && words.daily_total > 0
  const openSessions = open.data ?? []
  const questionCount = (papers.data ?? []).reduce((sum, paper) => sum + paper.question_count, 0)

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow={todayLabel()}
        title="今天要做的事"
        actions={
          nextExam ? (
            <Link to="/calendar" className="group flex items-baseline gap-2 rounded-md px-3 py-1 transition-colors hover:bg-accent-faint">
              <span className="text-sm text-muted">距離{nextExam.title}</span>
              <span className="font-hand text-3xl font-bold leading-none text-accent tabular-nums">{nextExam.days_until}</span>
              <span className="text-sm text-accent">天</span>
            </Link>
          ) : (
            countdown.isSuccess && (
              <Link to="/calendar" className="text-sm text-accent underline underline-offset-4">
                新增考試日期，開始倒數
              </Link>
            )
          )
        }
      />

      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <section aria-labelledby="tasks-title" className="rounded-lg bg-sheet px-5 shadow-sheet sm:px-7">
          <h2 id="tasks-title" className="sr-only">
            今日任務
          </h2>
          <ol className="m-0 list-none p-0">
            <TaskRow
              index={1}
              title="每日單字"
              done={dailyDone}
              detail={
                words.total === 0
                  ? '單字庫是空的，先匯入單字表。'
                  : `從 ${words.total} 個單字中，優先抽出該複習的字。`
              }
              status={
                words.total > 0 && (
                  <Bubbles
                    total={words.daily_total}
                    done={words.daily_done}
                    label={`已完成 ${words.daily_done} 題，共 ${words.daily_total} 題`}
                  />
                )
              }
              action={
                words.total === 0 ? (
                  <ButtonLink to="/vocab/words" variant="secondary">
                    匯入單字
                  </ButtonLink>
                ) : (
                  <ButtonLink to="/vocab" variant={dailyDone ? 'secondary' : 'primary'}>
                    {dailyDone ? '看今天的結果' : words.daily_done > 0 ? '繼續' : '開始'}
                    <Icon name="arrow" size={18} />
                  </ButtonLink>
                )
              }
            />
            <TaskRow
              index={2}
              title="錯題複習"
              done={stats.wrong_book > 0 && stats.review_due === 0}
              detail={
                stats.wrong_book === 0
                  ? '錯題本是空的。寫題目答錯的題會自動收進來。'
                  : stats.review_due > 0
                    ? `錯題本有 ${stats.wrong_book} 題，今天到期 ${stats.review_due} 題。`
                    : `錯題本有 ${stats.wrong_book} 題，今天沒有到期的。`
              }
              status={null}
              action={
                stats.review_due > 0 ? (
                  <Button
                    onClick={() => startReview.mutate({ mode: 'practice', source: { kind: 'review_due' } })}
                    disabled={startReview.isPending}
                  >
                    複習 {stats.review_due} 題
                    <Icon name="arrow" size={18} />
                  </Button>
                ) : (
                  <ButtonLink to="/review" variant="secondary">
                    看錯題本
                  </ButtonLink>
                )
              }
            />
            <TaskRow
              index={3}
              title={openSessions.length > 0 ? '寫到一半的測驗' : '寫一份考古題'}
              detail={
                openSessions.length > 0
                  ? openSessions.map((session) => shortName(session.title)).join('、')
                  : `題庫共 ${papers.data?.length ?? 0} 份試卷、${questionCount} 題。`
              }
              status={null}
              action={
                openSessions.length > 0 ? (
                  <ButtonLink to={`/exam/${openSessions[0].id}`}>
                    繼續作答
                    <Icon name="arrow" size={18} />
                  </ButtonLink>
                ) : (
                  <ButtonLink to="/bank" variant="secondary">
                    選試卷
                  </ButtonLink>
                )
              }
            />
          </ol>
        </section>

        <aside className="flex flex-col gap-8">
          <section aria-labelledby="glance-title" className="flex flex-col gap-4">
            <h2 id="glance-title" className="eyebrow m-0">
              到目前為止
            </h2>
            <dl className="m-0 grid grid-cols-2 gap-x-6 gap-y-5">
              {[
                ['作答正確率', stats.attempts ? percent(stats.accuracy) : '—'],
                ['寫過的題目', `${stats.answered_questions}`],
                ['錯題本', `${stats.wrong_book}`],
                ['已掌握', `${stats.mastered}`],
                ['學過的單字', `${words.studied}`],
                ['錯題單字', `${words.wrong_list}`],
              ].map(([label, value]) => (
                <div key={label} className="flex flex-col gap-0.5 border-l-2 border-rule pl-3">
                  <dt className="text-xs text-muted">{label}</dt>
                  <dd className="tabular m-0 text-xl text-ink">{value}</dd>
                </div>
              ))}
            </dl>
            <Link to="/overview" className="text-sm text-accent underline underline-offset-4">
              看完整總覽
            </Link>
          </section>

          <section aria-labelledby="recent-title" className="flex flex-col gap-2">
            <h2 id="recent-title" className="eyebrow m-0">
              最近交卷
            </h2>
            {recent.data && recent.data.length > 0 ? (
              <ul className="-mx-3 m-0 list-none p-0">
                {recent.data.map((session) => (
                  <SessionRow key={session.id} session={session} />
                ))}
              </ul>
            ) : (
              <p className="m-0 text-sm text-muted">還沒有交過卷。</p>
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}
