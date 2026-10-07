/** 交卷後：得分、題號對錯一覽、每題詳解、錯題重寫。 */

import { useQueryClient } from '@tanstack/react-query'
import { type CSSProperties, useCallback, useMemo, useState } from 'react'
import { AnswerGrid } from '@/components/AnswerGrid'
import { Button, ButtonLink } from '@/components/Button'
import { Segmented } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'
import { clock, formatDateTime, parseUtc, score, shortName } from '@/lib/format'
import { useStartSession } from '@/lib/sessions'
import type { ItemOut, SessionCreate, SessionOut } from '@/lib/types'
import { QuestionBlock } from './QuestionBlock'

type Filter = 'all' | 'wrong' | 'right' | 'pending'

/** 申論題有寫、但還沒自評 */
const isPending = (item: ItemOut) => item.type === 'essay' && !item.graded

export function ResultView({ session }: { session: SessionOut }) {
  const result = session.result!
  // 有申論題待自評就先看那些；否則有答錯就先只看答錯的題目，檢討比較快
  const [filter, setFilter] = useState<Filter>(() =>
    session.items.some(isPending) ? 'pending' : session.items.some((item) => !item.is_correct) ? 'wrong' : 'all',
  )
  const start = useStartSession()
  const queryClient = useQueryClient()
  const updateItem = useCallback(
    (updated: ItemOut) =>
      queryClient.setQueryData<SessionOut>(['exam', 'session', session.id], (old) =>
        old ? { ...old, items: old.items.map((entry) => (entry.position === updated.position ? updated : entry)) } : old,
      ),
    [queryClient, session.id],
  )
  const essayProps = { sessionId: session.id, practice: session.mode === 'practice', submitted: true, onUpdate: updateItem }

  const pendingItems = session.items.filter(isPending)
  const wrongItems = session.items.filter((item) => !item.is_correct && !isPending(item))
  const answeredWrong = wrongItems.filter((item) => item.answered)
  const unanswered = session.items.length - result.answered_count
  const elapsed = session.submitted_at
    ? (parseUtc(session.submitted_at).getTime() - parseUtc(session.started_at).getTime()) / 1000
    : 0
  const visible = useMemo(
    () =>
      session.items.filter((item) =>
        filter === 'all'
          ? true
          : filter === 'pending'
            ? isPending(item)
            : filter === 'wrong'
              ? !item.is_correct && !isPending(item)
              : item.is_correct,
      ),
    [filter, session.items],
  )
  const ratio = result.max_score ? result.score / result.max_score : 0

  return (
    <div className="flex flex-col gap-8">
      <header className="grid gap-6 border-b border-line pb-6 sm:grid-cols-[1fr_auto] sm:items-end">
        <div className="flex flex-col gap-1">
          <span className="eyebrow-hand">
            {session.mode === 'mock' ? '模擬考' : '練習'}・{formatDateTime(session.started_at)}
          </span>
          <h1 className="m-0 font-hand text-xl font-bold [word-break:keep-all] sm:text-2xl">{shortName(session.title)}</h1>
          <dl className="m-0 mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
            <div className="flex gap-1.5">
              <dt>答對</dt>
              <dd className="tabular m-0 text-ink">
                {result.correct_count}／{result.total}
              </dd>
            </div>
            {unanswered > 0 && (
              <div className="flex gap-1.5">
                <dt>未作答</dt>
                <dd className="tabular m-0 text-ink">{unanswered}</dd>
              </div>
            )}
            <div className="flex gap-1.5">
              <dt>用時</dt>
              <dd className="tabular m-0 text-ink">{clock(elapsed)}</dd>
            </div>
          </dl>
        </div>
        {/* 得分：原子筆手寫的分數，下面用螢光筆劃一道 */}
        <div
          className="flex flex-none items-baseline gap-1.5 text-accent sm:mr-2"
          aria-label={`得分 ${score(result.score)}，滿分 ${score(result.max_score)}`}
        >
          <span
            className="marker font-hand text-[64px] font-bold leading-none [&::before]:inset-x-[-6px] [&::before]:top-[55%] [&::before]:bottom-[2%] [&::before]:animate-[swipe_var(--dur-marker)_var(--ease-marker)_both] [&::before]:delay-200"
            style={{ '--marker-color': ratio >= 0.6 ? 'var(--ok-hl)' : 'var(--hl)' } as CSSProperties}
          >
            {score(result.score)}
          </span>
          <span className="font-hand text-lg text-muted">／{score(result.max_score)} 分</span>
        </div>
      </header>

      <div className="flex flex-wrap gap-3">
        {answeredWrong.length > 0 && (
          <Button
            onClick={() =>
              start.mutate({
                mode: 'practice',
                title: `${shortName(session.title).replace(/（.*）$/, '')}・錯題重寫`,
                source: { kind: 'questions', question_ids: answeredWrong.map((item) => item.question_id) },
                shuffle_questions: false,
              })
            }
            disabled={start.isPending}
          >
            <Icon name="refresh" size={18} />
            重寫這次的 {answeredWrong.length} 題錯題
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={() => start.mutate({ ...(session.settings as Partial<SessionCreate>), title: session.title })}
          disabled={start.isPending}
        >
          再寫一次
        </Button>
        <ButtonLink to="/" variant="ghost">
          回今日
        </ButtonLink>
      </div>
      {start.isError && <ErrorState error={start.error} />}
      {result.essay_pending > 0 && (
        <p className="m-0 flex items-start gap-2 rounded-md bg-hl-soft px-4 py-3 text-[15px] text-ink" role="status">
          <Icon name="edit" size={18} className="mt-0.5 flex-none text-accent" />
          還有 {result.essay_pending} 題申論題等你自評：在下面對照參考答案勾選寫到的得分要點，分數才會算進總分、記入錯題本。
        </p>
      )}

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_290px]">
        <section aria-label="逐題檢討" className="min-w-0 rounded-lg bg-sheet px-4 py-6 shadow-sheet sm:px-8">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h2 className="eyebrow-hand m-0">逐題檢討</h2>
            <Segmented
              label="篩選題目"
              value={filter}
              onChange={setFilter}
              className="w-full sm:w-auto sm:min-w-[300px]"
              options={[
                ...(pendingItems.length > 0 ? [{ value: 'pending' as const, label: `待評 ${pendingItems.length}` }] : []),
                { value: 'all', label: `全部 ${session.items.length}` },
                { value: 'wrong', label: `答錯 ${wrongItems.length}` },
                { value: 'right', label: `答對 ${result.correct_count}` },
              ]}
            />
          </div>
          {visible.length === 0 ? (
            <p className="m-0 py-6 text-muted">
              {filter === 'pending' ? '申論題都自評完了。' : filter === 'wrong' ? '沒有答錯的題目，全對！' : '沒有答對的題目。'}
            </p>
          ) : (
            <ol className="m-0 flex list-none flex-col p-0">
              {visible.map((item) => (
                <li key={item.position} id={`item-${item.position}`} className="scroll-mt-24 border-b border-rule py-8 first:pt-0 last:border-b-0">
                  <QuestionBlock item={item} selection={item.response ?? []} onToggle={() => {}} essay={essayProps} />
                </li>
              ))}
            </ol>
          )}
        </section>

        <aside className="flex flex-col gap-4 rounded-lg bg-sheet p-5 shadow-sheet lg:sticky lg:top-24">
          <h2 className="eyebrow-hand m-0">題號一覽</h2>
          <AnswerGrid
            cells={session.items.map((item) => ({
              position: item.position,
              answered: item.answered,
              correct: item.answered ? item.is_correct : null,
            }))}
            onJump={(position) => {
              setFilter('all')
              window.setTimeout(
                () => document.getElementById(`item-${position}`)?.scrollIntoView({ behavior: 'smooth' }),
                30,
              )
            }}
          />
          <div className="flex flex-col gap-1 text-xs text-muted">
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-5 rounded-[var(--radius-marker)] bg-ok-hl" /> 答對
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-5 rounded-[var(--radius-marker)] bg-bad-hl" /> 答錯（已收進錯題本）
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-5 rounded-[var(--radius-marker)] border border-dashed border-muted" /> 未作答
            </span>
          </div>
          <p className="m-0 text-xs text-muted">得分率 {(ratio * 100).toFixed(0)}%</p>
        </aside>
      </div>
    </div>
  )
}
