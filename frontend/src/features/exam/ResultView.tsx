/** 交卷後：得分、答案卡對錯一覽、每題詳解、錯題重寫。 */

import { useMemo, useState } from 'react'
import { AnswerGrid } from '@/components/AnswerGrid'
import { Button, ButtonLink } from '@/components/Button'
import { Segmented } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'
import { clock, formatDateTime, parseUtc, score, shortName } from '@/lib/format'
import { useStartSession } from '@/lib/sessions'
import type { SessionCreate, SessionOut } from '@/lib/types'
import { QuestionBlock } from './QuestionBlock'

type Filter = 'all' | 'wrong' | 'right'

export function ResultView({ session }: { session: SessionOut }) {
  const result = session.result!
  // 有答錯就先只看答錯的題目，檢討比較快
  const [filter, setFilter] = useState<Filter>(() => (session.items.some((item) => !item.is_correct) ? 'wrong' : 'all'))
  const start = useStartSession()

  const wrongItems = session.items.filter((item) => !item.is_correct)
  const answeredWrong = wrongItems.filter((item) => item.answered)
  const unanswered = session.items.length - result.answered_count
  const elapsed = session.submitted_at
    ? (parseUtc(session.submitted_at).getTime() - parseUtc(session.started_at).getTime()) / 1000
    : 0
  const visible = useMemo(
    () =>
      session.items.filter((item) =>
        filter === 'all' ? true : filter === 'wrong' ? !item.is_correct : item.is_correct,
      ),
    [filter, session.items],
  )
  const ratio = result.max_score ? result.score / result.max_score : 0

  return (
    <div className="flex flex-col gap-8">
      <header className="grid gap-6 border-b border-print pb-6 sm:grid-cols-[1fr_auto] sm:items-end">
        <div className="flex flex-col gap-1">
          <span className="eyebrow">
            {session.mode === 'mock' ? '模擬考' : '練習'}・{formatDateTime(session.started_at)}
          </span>
          <h1 className="m-0 font-serif text-xl font-bold sm:text-2xl">{shortName(session.title)}</h1>
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
        {/* 得分：像老師用紅筆寫在試卷上的分數 */}
        <div
          className="flex h-28 w-36 flex-none flex-col items-center justify-center rounded-[50%] border-[2.5px] border-print text-print animate-[stamp_520ms_var(--ease-out)_both] sm:mr-4"
          style={{ transform: 'rotate(-4deg)' }}
          aria-label={`得分 ${score(result.score)}，滿分 ${score(result.max_score)}`}
        >
          <span className="font-serif text-4xl font-bold leading-none">{score(result.score)}</span>
          <span className="tabular mt-1 text-xs">／{score(result.max_score)} 分</span>
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

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_290px]">
        <section aria-label="逐題檢討" className="min-w-0 rounded-lg bg-sheet px-4 py-6 shadow-sheet sm:px-8">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h2 className="eyebrow m-0">逐題檢討</h2>
            <Segmented
              label="篩選題目"
              value={filter}
              onChange={setFilter}
              className="w-full sm:w-auto sm:min-w-[300px]"
              options={[
                { value: 'all', label: `全部 ${session.items.length}` },
                { value: 'wrong', label: `答錯 ${wrongItems.length}` },
                { value: 'right', label: `答對 ${result.correct_count}` },
              ]}
            />
          </div>
          {visible.length === 0 ? (
            <p className="m-0 py-6 text-muted">{filter === 'wrong' ? '沒有答錯的題目，全對！' : '沒有答對的題目。'}</p>
          ) : (
            <ol className="m-0 flex list-none flex-col p-0">
              {visible.map((item) => (
                <li key={item.position} id={`item-${item.position}`} className="scroll-mt-24 border-b border-print-rule py-8 first:pt-0 last:border-b-0">
                  <QuestionBlock item={item} selection={item.response ?? []} onToggle={() => {}} />
                </li>
              ))}
            </ol>
          )}
        </section>

        <aside className="flex flex-col gap-4 rounded-lg bg-sheet p-5 shadow-sheet lg:sticky lg:top-24">
          <h2 className="eyebrow m-0">答案卡</h2>
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
              <span className="h-[13px] w-[9px] rounded-full bg-ok" /> 答對
            </span>
            <span className="flex items-center gap-2">
              <span className="h-[13px] w-[9px] rounded-full bg-bad" /> 答錯（已收進錯題本）
            </span>
            <span className="flex items-center gap-2">
              <span className="h-[13px] w-[9px] rounded-full border border-print" /> 未作答
            </span>
          </div>
          <p className="m-0 text-xs text-muted">得分率 {(ratio * 100).toFixed(0)}%</p>
        </aside>
      </div>
    </div>
  )
}
