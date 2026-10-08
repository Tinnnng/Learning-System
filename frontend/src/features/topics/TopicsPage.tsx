/** 知識點與弱點：AI 依科目幫題目標知識點，再用作答紀錄算出每個知識點的正確率，弱的可以直接練。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button } from '@/components/Button'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { cx } from '@/lib/cx'
import { percent, shortName } from '@/lib/format'
import { useStartSession } from '@/lib/sessions'

type TopicsOverview = components['schemas']['TopicsOverview']
type SubjectTopics = components['schemas']['SubjectTopics']
type TopicStat = components['schemas']['TopicStat']
type TagResult = components['schemas']['TagResult']

function usePractice() {
  const start = useStartSession()
  return {
    start,
    practice: (questionIds: number[]) =>
      start.mutate({ mode: 'practice', source: { kind: 'questions', question_ids: questionIds }, shuffle_questions: true }),
  }
}

function TopicRow({
  stat,
  threshold,
  onPractice,
  disabled,
}: {
  stat: TopicStat
  threshold: number
  onPractice: () => void
  disabled: boolean
}) {
  const accuracy = stat.accuracy
  const low = accuracy !== null && accuracy < threshold
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 border-b border-rule py-3.5 last:border-b-0">
      <span className="flex min-w-0 flex-col gap-1.5">
        <span className="flex items-baseline gap-2">
          <span className={cx('truncate text-[15px] text-ink', stat.weak && 'underline decoration-bad decoration-wavy decoration-[1.5px] underline-offset-[5px]')}>
            {stat.topic}
            {stat.weak && <span className="sr-only">（弱點）</span>}
          </span>
          <span
            className={cx(
              'tabular shrink-0 text-sm',
              accuracy === null ? 'text-muted' : stat.weak ? 'text-bad' : low ? 'text-ink-soft' : 'text-ok',
            )}
          >
            {accuracy === null ? '還沒寫過' : percent(accuracy)}
          </span>
        </span>
        <span className="h-[6px] overflow-hidden rounded-full bg-line" aria-hidden>
          {accuracy !== null && accuracy > 0 && (
            // 作答次數還不夠判斷弱點時，偏低的正確率用淡一點的粉紅
            <span
              className={cx(
                'block h-full rounded-full transition-[width] duration-[var(--dur-slow)]',
                stat.weak ? 'bg-bad' : low ? 'bg-bad/40' : 'bg-ok',
              )}
              style={{ width: `${accuracy * 100}%` }}
            />
          )}
        </span>
        <span className="text-xs text-muted">
          {stat.questions} 題・寫過 {stat.answered} 題、{stat.attempts} 次{stat.wrong_book > 0 && `・錯題本 ${stat.wrong_book} 題`}
        </span>
      </span>
      <Button variant="ghost" size="sm" className="h-11" onClick={onPractice} disabled={disabled} aria-label={`練習「${stat.topic}」`}>
        <Icon name="play" size={15} />
        練習
      </Button>
    </li>
  )
}

function SubjectCard({
  subject,
  threshold,
  busy,
  onTag,
  onRetag,
  onPractice,
  practicing,
}: {
  subject: SubjectTopics
  threshold: number
  busy: boolean
  onTag: () => void
  onRetag: () => void
  onPractice: (ids: number[]) => void
  practicing: boolean
}) {
  const [showAll, setShowAll] = useState(false)
  const untagged = subject.questions - subject.tagged
  const visible = showAll ? subject.topics : subject.topics.slice(0, 6)
  return (
    <section className="flex flex-col gap-3 rounded-lg bg-sheet px-5 py-5 shadow-sheet sm:px-6" aria-label={subject.subject}>
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 className="m-0 font-display text-lg font-bold [word-break:keep-all]">{shortName(subject.subject)}</h2>
          <span className="text-xs text-muted">
            {subject.topics.length > 0 ? `${subject.topics.length} 個知識點・` : ''}已標記 {subject.tagged}／{subject.questions} 題
          </span>
        </div>
        {untagged > 0 ? (
          <Button size="sm" onClick={onTag} disabled={busy}>
            <Icon name="spark" size={16} />
            {subject.tagged > 0 ? `標記新的 ${untagged} 題` : 'AI 標記知識點'}
          </Button>
        ) : (
          <button
            type="button"
            onClick={onRetag}
            disabled={busy}
            aria-label={`重新標記${shortName(subject.subject)}的知識點`}
            className="min-h-11 px-1 text-xs text-muted hover:text-ink disabled:opacity-45"
          >
            重新標記
          </button>
        )}
      </header>
      {subject.topics.length === 0 ? (
        <p className="m-0 text-sm text-muted">
          還沒標記。AI 會先讀過這科的題目整理出知識點，再把每題歸類，大約呼叫 {subject.estimated_calls} 次（Haiku，每次約 0.003 美元）。
        </p>
      ) : (
        <>
          <ul className="stagger m-0 list-none p-0">
            {visible.map((stat) => (
              <TopicRow key={stat.topic} stat={stat} threshold={threshold} onPractice={() => onPractice(stat.question_ids)} disabled={practicing} />
            ))}
          </ul>
          {subject.topics.length > visible.length || showAll ? (
            <button type="button" onClick={() => setShowAll(!showAll)} className="h-9 self-start text-sm text-accent hover:underline">
              {showAll ? '收合' : `顯示全部 ${subject.topics.length} 個知識點`}
            </button>
          ) : null}
        </>
      )}
    </section>
  )
}

export function TopicsPage() {
  const queryClient = useQueryClient()
  const overview = useQuery({ queryKey: ['topics'], queryFn: () => api.get<TopicsOverview>('/topics') })
  const { start, practice } = usePractice()
  const [queue, setQueue] = useState<{ subjects: string[]; done: number } | null>(null)
  const [retagTarget, setRetagTarget] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<TagResult | null>(null)

  const tag = useMutation({
    mutationFn: (data: { subject: string; retag?: boolean }) => api.post<TagResult>('/topics/tag', data),
    onSuccess: (result) => {
      setLastResult(result)
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      queryClient.invalidateQueries({ queryKey: ['ai', 'status'] })
    },
  })

  // 一次標記多個科目：一科完成再送下一科，每科存好就更新畫面
  const runQueue = async (subjects: string[]) => {
    setQueue({ subjects, done: 0 })
    try {
      for (const [index, subject] of subjects.entries()) {
        await tag.mutateAsync({ subject })
        setQueue({ subjects, done: index + 1 })
      }
    } catch {
      // 錯誤訊息由 tag.error 顯示，已完成的科目都已儲存
    } finally {
      setQueue(null)
    }
  }

  const data = overview.data
  const untaggedSubjects = data?.subjects.filter((subject) => subject.tagged < subject.questions) ?? []
  const totalCalls = untaggedSubjects.reduce((sum, subject) => sum + subject.estimated_calls, 0)
  const anyTagged = data?.subjects.some((subject) => subject.tagged > 0) ?? false
  const busy = tag.isPending || queue !== null

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="弱點分析"
        title="知識點"
        description="AI 依科目把題目歸到知識點，再用你的作答紀錄算出每個知識點的正確率；弱的那幾個，直接拿來練。"
        actions={
          untaggedSubjects.length > 1 ? (
            <Button onClick={() => runQueue(untaggedSubjects.map((subject) => subject.subject))} disabled={busy}>
              <Icon name="spark" size={17} />
              全部科目一起標記
            </Button>
          ) : undefined
        }
      />

      {queue && (
        <p className="m-0 flex items-center gap-2 rounded-md bg-accent-faint px-4 py-3 text-[15px]" role="status">
          <span className="h-3 w-2 animate-pulse rounded-full border border-accent" />
          正在標記「{shortName(queue.subjects[queue.done] ?? '')}」（{queue.done + 1}／{queue.subjects.length} 科），每科大約 10–40 秒…
        </p>
      )}
      {!queue && tag.isPending && (
        <p className="m-0 flex items-center gap-2 rounded-md bg-accent-faint px-4 py-3 text-[15px]" role="status">
          <span className="h-3 w-2 animate-pulse rounded-full border border-accent" />
          AI 正在標記「{shortName(tag.variables?.subject ?? '')}」，大約 10–40 秒…
        </p>
      )}
      {tag.isError && <ErrorState error={tag.error} />}
      {!busy && lastResult && lastResult.tagged > 0 && (
        <p className="m-0 rounded-md bg-ok-soft/60 px-4 py-3 text-[15px]" role="status">
          已標記「{shortName(lastResult.subject)}」{lastResult.tagged} 題（呼叫 AI {lastResult.calls} 次）。
        </p>
      )}
      {start.isError && <ErrorState error={start.error} />}

      {overview.isPending ? (
        <Loading />
      ) : overview.isError ? (
        <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
      ) : !data || data.subjects.length === 0 ? (
        <EmptyState title="題庫還是空的">先匯入題目，才能分析知識點。</EmptyState>
      ) : (
        <>
          <section aria-label="你的弱點" className="flex flex-col gap-3">
            <h2 className="eyebrow m-0">你的弱點</h2>
            {data.weak.length > 0 ? (
              <ul className="stagger m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
                {data.weak.slice(0, 6).map((stat) => (
                  <li key={`${stat.subject}-${stat.topic}`} className="flex flex-col gap-2 rounded-lg border border-rule bg-sheet px-4 py-4">
                    <span className="text-xs text-muted">{shortName(stat.subject)}</span>
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="text-lg text-ink underline decoration-bad decoration-wavy decoration-[1.5px] underline-offset-[5px]">{stat.topic}</span>
                      <span className="tabular text-bad">{percent(stat.accuracy ?? 0)}</span>
                    </span>
                    <span className="text-xs text-muted">
                      寫過 {stat.attempts} 次・錯題本 {stat.wrong_book} 題・共 {stat.questions} 題
                    </span>
                    <Button size="sm" variant="secondary" className="mt-1 self-start" onClick={() => practice(stat.question_ids)} disabled={start.isPending}>
                      <Icon name="play" size={15} />
                      練這 {stat.questions} 題
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="m-0 max-w-[60ch] text-sm text-muted">
                {anyTagged
                  ? `目前沒有弱點。某個知識點寫過 ${data.weak_min_attempts} 次以上、正確率低於 ${percent(data.weak_accuracy)} 時，會列在這裡。`
                  : `先用 AI 幫科目標記知識點（全部約 ${totalCalls} 次 AI 呼叫），之後寫題目的紀錄就會累積成每個知識點的正確率。`}
              </p>
            )}
          </section>

          <div className="grid items-start gap-5 lg:grid-cols-2">
            {/* 已標記的科目排前面 */}
            {[...data.subjects].sort((a, b) => Number(b.tagged > 0) - Number(a.tagged > 0)).map((subject) => (
              <SubjectCard
                key={subject.subject}
                subject={subject}
                threshold={data.weak_accuracy}
                busy={busy}
                onTag={() => tag.mutate({ subject: subject.subject })}
                onRetag={() => setRetagTarget(subject.subject)}
                onPractice={practice}
                practicing={start.isPending}
              />
            ))}
          </div>
        </>
      )}

      <Dialog
        open={retagTarget !== null}
        onClose={() => setRetagTarget(null)}
        title="重新標記知識點？"
        actions={
          <>
            <Button variant="ghost" onClick={() => setRetagTarget(null)}>
              取消
            </Button>
            <Button
              onClick={() => {
                if (retagTarget) tag.mutate({ subject: retagTarget, retag: true })
                setRetagTarget(null)
              }}
            >
              重新標記
            </Button>
          </>
        }
      >
        <p className="m-0 text-[15px]">
          會清掉「{retagTarget && shortName(retagTarget)}」目前 AI 標的知識點，重新整理清單再標一次（會再花一些 Claude 用量）。作答紀錄不受影響。
        </p>
      </Dialog>
    </div>
  )
}
