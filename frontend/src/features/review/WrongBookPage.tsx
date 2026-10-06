/** 錯題本：在錯題本中／已掌握／曾經答錯的全部，每題顯示「正」字掌握進度與下次複習日。 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button } from '@/components/Button'
import { ChipGroup, Segmented } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { OptionBubble } from '@/components/OptionBubble'
import { PageHeader } from '@/components/PageHeader'
import { QuestionFigure, RichText } from '@/components/RichText'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { ZhengTally } from '@/components/ZhengTally'
import { cx } from '@/lib/cx'
import { formatDateTime, parseUtc, plainText, relativeDay, shortName } from '@/lib/format'
import { useStartSession } from '@/lib/sessions'
import type { WrongQuestionOut } from '@/lib/types'
import { fetchHistory, fetchWrongQuestions, type WrongStatus } from './api'

const LETTERS = 'ABCDEFGHIJ'

function History({ questionId }: { questionId: number }) {
  const history = useQuery({ queryKey: ['review', 'history', questionId], queryFn: () => fetchHistory(questionId) })
  if (!history.data) return null
  return (
    <ol className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label="作答紀錄（新到舊）">
      {history.data.attempts.map((attempt) => (
        <li
          key={attempt.answered_at}
          className={cx(
            'rounded-sm border px-2 py-0.5 text-xs',
            attempt.is_correct ? 'border-ok/40 text-ok' : 'border-bad/40 text-bad',
          )}
          title={formatDateTime(attempt.answered_at)}
        >
          {formatDateTime(attempt.answered_at)}　選 {attempt.response.join('、') || '—'}　{attempt.is_correct ? '對' : '錯'}
        </li>
      ))}
    </ol>
  )
}

function WrongRow({ entry, now }: { entry: WrongQuestionOut; now: number }) {
  const [open, setOpen] = useState(false)
  const { question, progress } = entry
  const due = entry.review_due
  const isDue = due ? parseUtc(due).getTime() <= now : false
  return (
    <li className="border-b border-print-rule last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="grid w-full grid-cols-[1fr_auto] items-start gap-x-6 gap-y-2 px-1 py-5 text-left transition-colors hover:bg-sheet-tint sm:grid-cols-[1fr_auto_auto] sm:px-3"
      >
        <span className="flex min-w-0 flex-col gap-1.5">
          <span className="text-xs text-muted">
            {question.paper.year && `${question.paper.year} 年`}
            {question.paper.exam_type}｜{shortName(question.paper.subject)}　第 {question.number} 題
          </span>
          <span className={cx('font-serif text-[16px] leading-relaxed text-ink', !open && 'line-clamp-2')}>
            {plainText(question.stem)}
          </span>
        </span>
        <span className="row-span-2 sm:row-span-1">
          {progress.in_wrong_book ? (
            <ZhengTally count={progress.correct_streak} target={progress.mastery_target} />
          ) : (
            <ZhengTally count={progress.mastery_target} target={progress.mastery_target} />
          )}
        </span>
        <span className="text-xs text-muted sm:w-24 sm:text-right">
          {progress.in_wrong_book && due ? (
            <span className={cx(isDue && 'font-medium text-print')}>{isDue ? '今天該複習' : `${relativeDay(due)}複習`}</span>
          ) : (
            '已移出錯題本'
          )}
          <br />
          錯 {progress.wrong_count} 次
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-4 px-1 pb-6 animate-[rise-in_var(--dur)_var(--ease-out)] sm:px-3">
          {question.passage && (
            <details className="rounded-md bg-sheet-tint px-4 py-2 text-sm">
              <summary className="cursor-pointer text-print">題組文章</summary>
              <RichText className="mt-2 text-[15px]">{question.passage}</RichText>
            </details>
          )}
          <RichText>{question.stem}</RichText>
          {question.assets.map((asset) => (
            <QuestionFigure key={asset.path} path={asset.path} caption={asset.caption} />
          ))}
          <div className="-mx-3 flex flex-col">
            {question.options.map((option, index) => {
              const letter = LETTERS[index]
              return (
                <OptionBubble
                  key={letter}
                  letter={letter}
                  text={option}
                  disabled
                  state={question.answer.includes(letter) ? 'answer' : 'dimmed'}
                />
              )
            })}
          </div>
          {question.explanation && <RichText className="text-[15px]">{question.explanation}</RichText>}
          <History questionId={question.id} />
        </div>
      )}
    </li>
  )
}

export function WrongBookPage() {
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') as WrongStatus) || 'active'
  const subject = params.get('subject')
  const wrong = useQuery({
    queryKey: ['review', 'wrong', status, subject],
    queryFn: () => fetchWrongQuestions(status, subject),
  })
  const allActive = useQuery({ queryKey: ['review', 'wrong', 'active', null], queryFn: () => fetchWrongQuestions('active', null) })
  const start = useStartSession()
  const [now] = useState(() => Date.now())

  const set = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const entries = wrong.data ?? []
  const subjects = [...new Set((allActive.data ?? []).map((entry) => entry.question.paper.subject))].sort()
  const dueCount = (allActive.data ?? []).filter((entry) => entry.review_due && parseUtc(entry.review_due).getTime() <= now).length
  const activeIds = entries.filter((entry) => entry.progress.in_wrong_book).map((entry) => entry.question.id)

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="錯題本"
        title="答錯過的題目"
        description="答錯的題目會自動收進來，連續答對 5 次（寫滿一個「正」字）才會移出。系統依記憶曲線排好每題的複習日。"
        actions={
          <>
            {dueCount > 0 && (
              <Button
                onClick={() => start.mutate({ mode: 'practice', source: { kind: 'review_due' }, shuffle_questions: false })}
                disabled={start.isPending}
              >
                複習今天到期的 {dueCount} 題
              </Button>
            )}
            {activeIds.length > 0 && (
              <Button
                variant="secondary"
                onClick={() =>
                  start.mutate({
                    mode: 'practice',
                    title: subject ? `${shortName(subject)}・錯題重寫` : '錯題重寫',
                    source: { kind: 'questions', question_ids: activeIds },
                  })
                }
                disabled={start.isPending}
              >
                <Icon name="refresh" size={18} />
                重寫{subject ? '這科' : '全部'} {activeIds.length} 題
              </Button>
            )}
          </>
        }
      />

      <div className="flex flex-col gap-4">
        <Segmented
          label="錯題狀態"
          value={status}
          onChange={(value) => set('status', value === 'active' ? null : value)}
          className="max-w-[480px]"
          options={[
            { value: 'active', label: '還沒掌握' },
            { value: 'mastered', label: '已掌握' },
            { value: 'all', label: '曾經答錯的全部' },
          ]}
        />
        <ChipGroup
          label="科目"
          value={subject}
          options={subjects.map((value) => ({ value, label: shortName(value) }))}
          onChange={(value) => set('subject', value)}
        />
      </div>

      {start.isError && <ErrorState error={start.error} />}
      {wrong.isPending ? (
        <Loading />
      ) : wrong.isError ? (
        <ErrorState error={wrong.error} onRetry={() => wrong.refetch()} />
      ) : entries.length === 0 ? (
        <EmptyState title={status === 'mastered' ? '還沒有掌握的錯題' : '錯題本是空的'}>
          {status === 'mastered'
            ? '錯題連續答對 5 次就會出現在這裡。'
            : '去題庫寫一份考古題吧，答錯的題目會自動收進來。'}
        </EmptyState>
      ) : (
        <section aria-label="錯題列表" className="rounded-lg bg-sheet px-3 shadow-sheet sm:px-5">
          <p className="m-0 border-b border-print py-3 text-sm text-muted">
            共 <span className="tabular text-ink">{entries.length}</span> 題，點題目展開正確答案與作答紀錄
          </p>
          <ul className="m-0 list-none p-0">
            {entries.map((entry) => (
              <WrongRow key={entry.question.id} entry={entry} now={now} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
