/** 英文單字：每日複習、錯題單字、單字庫（含匯入）。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useRef, useState } from 'react'
import { NavLink } from 'react-router'
import { Button, ButtonLink } from '@/components/Button'
import { ChipGroup } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { ZhengTally } from '@/components/ZhengTally'
import { cx } from '@/lib/cx'
import { relativeDay, todayLabel } from '@/lib/format'
import type { ImportResult, QuizItem, VocabAnswerResult, WordOut } from '@/lib/types'
import {
  fetchBuiltin,
  fetchDaily,
  fetchQuiz,
  fetchStats,
  fetchWords,
  fetchWrongWords,
  importBuiltin,
  uploadWords,
  type WordStatus,
} from './api'
import { ExtractWordsDialog } from './ExtractWordsDialog'
import { QuizRunner } from './QuizRunner'

function VocabTabs() {
  const tabs = [
    { to: '/vocab', label: '每日複習', end: true },
    { to: '/vocab/wrong', label: '錯題單字', end: false },
    { to: '/vocab/words', label: '單字庫', end: false },
  ]
  return (
    <nav aria-label="單字" className="-mt-2 flex gap-1 border-b border-line">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cx(
              '-mb-px border-b-2 px-3 py-2.5 text-sm transition-colors',
              isActive ? 'border-accent font-medium text-ink' : 'border-transparent text-muted hover:text-ink',
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}

function Sheet({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cx('rounded-lg bg-sheet px-5 py-7 shadow-sheet sm:px-9 sm:py-9', className)}>{children}</section>
}

/** 每日單字寫完後的「再測一組」：第幾組、題目、寫完的結果 */
interface ExtraRound {
  number: number
  items: QuizItem[]
  results: VocabAnswerResult[] | null
}

export function DailyPage() {
  const daily = useQuery({ queryKey: ['vocab', 'daily'], queryFn: fetchDaily, staleTime: Infinity })
  const stats = useQuery({ queryKey: ['vocab', 'stats'], queryFn: fetchStats })
  const [finished, setFinished] = useState(false)
  const [round, setRound] = useState<ExtraRound | null>(null)
  const roundSize = daily.data?.total || 5
  // 再測一組：選字方式和每日一樣（到期 → 新單字 → 隨機），避開今天已經出現過的字
  const nextRound = useMutation({
    mutationFn: () => fetchQuiz('next', roundSize),
    onSuccess: (items) => setRound({ number: (round?.number ?? 0) + 1, items, results: null }),
  })

  const done = daily.data && daily.data.total > 0 && (finished || daily.data.done >= daily.data.total)
  const startNext = () => nextRound.mutate()

  return (
    <div className="flex flex-col gap-8">
      <PageHeader eyebrow={todayLabel()} title="每日單字" description="每天抽 5 個字：先複習該複習的，再補新單字，可以分次寫完。寫完還想背，可以「再測一組」新的字。" />
      <VocabTabs />
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
        <Sheet>
          {daily.isPending ? (
            <Loading />
          ) : daily.isError ? (
            <ErrorState error={daily.error} onRetry={() => daily.refetch()} />
          ) : daily.data.total === 0 ? (
            <EmptyState title="單字庫是空的" action={<ButtonLink to="/vocab/words">匯入單字</ButtonLink>}>
              匯入自己的單字表，或使用內建的多益核心單字。
            </EmptyState>
          ) : round && round.items.length > 0 && !round.results ? (
            <div className="flex flex-col gap-5">
              <span className="eyebrow">再測一組・第 {round.number} 組</span>
              <QuizRunner
                key={round.number}
                items={round.items}
                context="practice"
                onFinish={(results) => setRound({ ...round, results })}
              />
            </div>
          ) : round ? (
            <RoundDone round={round} onNext={startNext} pending={nextRound.isPending} />
          ) : done ? (
            <DailyDone onNext={startNext} pending={nextRound.isPending} />
          ) : (
            <QuizRunner items={daily.data.items} context="daily" onFinish={() => setFinished(true)} />
          )}
          {nextRound.isError && <ErrorState error={nextRound.error} onRetry={startNext} />}
        </Sheet>
        {stats.data && (
          <aside className="flex flex-col gap-4">
            <dl className="m-0 grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-1">
              {[
                ['單字庫', stats.data.total],
                ['學過', stats.data.studied],
                ['錯題單字', stats.data.wrong_list],
                ['今天到期', stats.data.due_today],
              ].map(([label, value]) => (
                <div key={label} className="flex items-baseline justify-between gap-3 border-b border-rule pb-2">
                  <dt className="text-sm text-muted">{label}</dt>
                  <dd className="tabular m-0 text-lg">{value}</dd>
                </div>
              ))}
            </dl>
          </aside>
        )}
      </div>
    </div>
  )
}

function NextRoundButton({ onNext, pending, primary }: { onNext: () => void; pending: boolean; primary?: boolean }) {
  return (
    <Button variant={primary ? 'primary' : 'secondary'} onClick={onNext} disabled={pending}>
      <Icon name="refresh" size={17} />
      {pending ? '抽題中…' : '再測一組'}
    </Button>
  )
}

/** 再測一組寫完：這組的成績，可以繼續下一組 */
function RoundDone({ round, onNext, pending }: { round: ExtraRound; onNext: () => void; pending: boolean }) {
  if (round.items.length === 0) {
    return (
      <div className="flex flex-col items-start gap-4 animate-[rise-in_var(--dur)_var(--ease-out)]">
        <span className="eyebrow">再測一組</span>
        <p className="m-0 font-display text-2xl font-bold">今天把單字庫的字都測過了</p>
        <p className="m-0 text-muted">可以到單字庫匯入更多單字，或明天再來。</p>
        <div className="flex flex-wrap gap-2">
          <ButtonLink to="/vocab/words">匯入單字</ButtonLink>
          <ButtonLink to="/" variant="secondary">
            回今日
          </ButtonLink>
        </div>
      </div>
    )
  }
  const results = round.results ?? []
  const correct = results.filter((result) => result.is_correct).length
  return (
    <div className="flex flex-col items-start gap-4 animate-[rise-in_var(--dur)_var(--ease-out)]">
      <span className="eyebrow">第 {round.number} 組完成</span>
      <p className="m-0 font-display text-2xl font-bold">
        {results.length} 個單字答對 <span className="tabular text-accent">{correct}</span> 個
      </p>
      <p className="m-0 text-muted">
        {correct < results.length ? '答錯的字已經收進錯題單字。' : '全對！'}這組的字也會依記憶曲線排進之後的複習。
      </p>
      <div className="flex flex-wrap gap-2">
        <NextRoundButton onNext={onNext} pending={pending} primary />
        {correct < results.length && (
          <ButtonLink to="/vocab/wrong" variant="secondary">
            複習錯題單字
          </ButtonLink>
        )}
        <ButtonLink to="/" variant="ghost">
          回今日
        </ButtonLink>
      </div>
    </div>
  )
}

function DailyDone({ onNext, pending }: { onNext: () => void; pending: boolean }) {
  const daily = useQuery({ queryKey: ['vocab', 'daily'], queryFn: fetchDaily })
  const correct = daily.data?.items.filter((item) => item.is_correct).length ?? 0
  const total = daily.data?.total ?? 0
  return (
    <div className="flex flex-col items-start gap-4 animate-[rise-in_var(--dur)_var(--ease-out)]">
      <span className="eyebrow">今天完成了</span>
      <p className="m-0 font-display text-2xl font-bold">
        {total} 個單字答對 <span className="tabular text-accent">{correct}</span> 個
      </p>
      <p className="m-0 text-muted">
        {correct < total ? '答錯的字已經收進錯題單字，明天會優先再出現。' : '全對！'}還想多背幾個，可以再測一組新的字。
      </p>
      <div className="flex flex-wrap gap-2">
        <NextRoundButton onNext={onNext} pending={pending} primary />
        {correct < total && (
          <ButtonLink to="/vocab/wrong" variant="secondary">
            複習錯題單字
          </ButtonLink>
        )}
        <ButtonLink to="/" variant="ghost">
          回今日
        </ButtonLink>
      </div>
    </div>
  )
}

function WordLine({ word, extra }: { word: WordOut; extra?: ReactNode }) {
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-b border-rule py-3.5 last:border-b-0">
      <span className="flex min-w-0 flex-wrap items-baseline gap-x-3">
        <span className="font-mono text-lg">{word.term}</span>
        {word.part_of_speech && <span className="text-xs text-accent">{word.part_of_speech}</span>}
        <span className="text-sm text-ink-soft">{word.meaning}</span>
      </span>
      {extra}
    </li>
  )
}

export function WrongWordsPage() {
  const wrong = useQuery({ queryKey: ['vocab', 'wrong'], queryFn: fetchWrongWords })
  const [quiz, setQuiz] = useState<QuizItem[] | null>(null)
  const startQuiz = useMutation({ mutationFn: () => fetchQuiz('wrong', 20), onSuccess: setQuiz })

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="錯題單字"
        title="答錯過的單字"
        description="連續答對 5 次（寫滿一個「正」字）才會移出。集中複習一次最多 20 個，題型隨機。"
        actions={
          wrong.data && wrong.data.length > 0 && !quiz ? (
            <Button onClick={() => startQuiz.mutate()} disabled={startQuiz.isPending}>
              <Icon name="play" size={16} />
              集中複習
            </Button>
          ) : undefined
        }
      />
      <VocabTabs />
      {quiz ? (
        <Sheet>
          {quiz.length === 0 ? (
            <p className="m-0 text-muted">沒有錯題單字了。</p>
          ) : (
            <QuizRunner items={quiz} context="wrong" onFinish={() => setQuiz(null)} />
          )}
        </Sheet>
      ) : wrong.isPending ? (
        <Loading />
      ) : wrong.isError ? (
        <ErrorState error={wrong.error} onRetry={() => wrong.refetch()} />
      ) : wrong.data.length === 0 ? (
        <EmptyState title="沒有錯題單字">每日複習答錯的單字會收進這裡。</EmptyState>
      ) : (
        <section className="rounded-lg bg-sheet px-5 shadow-sheet sm:px-7">
          <ul className="stagger m-0 list-none p-0">
            {wrong.data.map((word) => (
              <WordLine
                key={word.id}
                word={word}
                extra={
                  word.progress && (
                    <ZhengTally count={word.progress.correct_streak} target={word.progress.mastery_target} size={26} showLabel={false} />
                  )
                }
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

const STATUS_LABELS: Record<WordStatus, string> = { new: '沒學過', learning: '學習中', wrong: '錯題', mastered: '已掌握' }

function ImportPanel() {
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [extracting, setExtracting] = useState(false)
  const builtin = useQuery({ queryKey: ['vocab', 'builtin'], queryFn: fetchBuiltin })
  const onDone = (data: ImportResult) => {
    setResult(data)
    queryClient.invalidateQueries({ queryKey: ['vocab'] })
  }
  const upload = useMutation({ mutationFn: uploadWords, onSuccess: onDone })
  const builtinImport = useMutation({ mutationFn: importBuiltin, onSuccess: onDone })

  return (
    <aside className="flex flex-col gap-5 rounded-lg bg-sheet p-5 shadow-sheet sm:p-6 lg:sticky lg:top-24">
      <h2 className="m-0 font-display text-lg font-bold">匯入單字</h2>
      <div className="flex flex-col gap-2">
        <p className="m-0 text-sm text-muted">
          CSV 或 Excel，第一列放欄位名稱：<span className="text-ink">單字、中文</span> 必填，可加 詞性、例句、例句翻譯、標籤（或分類）。單字庫已經有的字會合併中文意思，原本的詞性、例句與作答進度保留。
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx"
          className="sr-only"
          id="word-file"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) upload.mutate(file)
            event.target.value = ''
          }}
        />
        <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
          <Icon name="import" size={18} />
          {upload.isPending ? '匯入中…' : '選擇檔案'}
        </Button>
      </div>
      {builtin.data && builtin.data.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-rule pt-4">
          <span className="text-sm text-muted">內建單字表</span>
          {builtin.data.map((list) => (
            <Button
              key={list.name}
              variant="ghost"
              className="justify-between"
              onClick={() => builtinImport.mutate(list.name)}
              disabled={builtinImport.isPending}
            >
              {list.title}
              <span className="tabular text-sm text-muted">{list.count} 字</span>
            </Button>
          ))}
        </div>
      )}
      <div className="flex flex-col gap-2 border-t border-rule pt-4">
        <span className="text-sm text-muted">從考古題找生字</span>
        <Button variant="secondary" onClick={() => setExtracting(true)}>
          <Icon name="spark" size={17} />
          讓 AI 從英文題挑生字
        </Button>
      </div>
      <ExtractWordsDialog open={extracting} onClose={() => setExtracting(false)} />
      {(upload.isError || builtinImport.isError) && <ErrorState error={upload.error ?? builtinImport.error} />}
      {result && (
        <p className="m-0 rounded-md bg-ok-soft/60 px-3 py-2 text-sm" role="status">
          新增 {result.created} 個{result.updated > 0 && `；${result.updated} 個已經在單字庫，意思已合併（原本的例句與詞性保留）`}{result.skipped > 0 && `；略過 ${result.skipped} 列`}。
          {result.errors.slice(0, 3).map((error) => (
            <span key={error} className="block text-xs text-muted">
              {error}
            </span>
          ))}
        </p>
      )}
    </aside>
  )
}

export function WordsPage() {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<WordStatus | null>(null)
  const [limit, setLimit] = useState(40)
  const words = useQuery({
    queryKey: ['vocab', 'words', search, status, limit],
    queryFn: () => fetchWords({ search, status, limit }),
    placeholderData: (previous) => previous,
  })

  return (
    <div className="flex flex-col gap-8">
      <PageHeader eyebrow="單字庫" title="所有單字" />
      <VocabTabs />
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex flex-col gap-4">
          <div className="relative">
            <Icon name="search" size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜尋英文或中文"
              aria-label="搜尋單字"
              className="h-11 w-full rounded-md border border-line bg-sheet pl-10 pr-4 text-ink outline-none transition-colors focus:border-ink"
            />
          </div>
          <ChipGroup
            label="狀態"
            value={status}
            onChange={setStatus}
            options={(Object.keys(STATUS_LABELS) as WordStatus[]).map((value) => ({ value, label: STATUS_LABELS[value] }))}
          />
          {words.isPending ? (
            <Loading />
          ) : words.isError ? (
            <ErrorState error={words.error} onRetry={() => words.refetch()} />
          ) : words.data.total === 0 ? (
            <EmptyState title={search || status ? '找不到符合的單字' : '單字庫是空的'}>
              {search || status ? '換個關鍵字試試。' : '從右邊匯入單字表，或使用內建的多益核心單字。'}
            </EmptyState>
          ) : (
            <section className="rounded-lg bg-sheet px-5 shadow-sheet sm:px-7">
              <p className="m-0 border-b border-accent py-3 text-sm text-muted">
                共 <span className="tabular text-ink">{words.data.total}</span> 個單字
              </p>
              <ul className="stagger m-0 list-none p-0">
                {words.data.items.map((word) => (
                  <WordLine
                    key={word.id}
                    word={word}
                    extra={
                      <span className="text-right text-xs text-muted">
                        {STATUS_LABELS[word.status]}
                        {word.review_due && (
                          <>
                            <br />
                            {relativeDay(word.review_due)}複習
                          </>
                        )}
                      </span>
                    }
                  />
                ))}
              </ul>
              {words.data.total > words.data.items.length && (
                <div className="flex justify-center border-t border-rule py-4">
                  <Button variant="ghost" onClick={() => setLimit(limit + 40)}>
                    再顯示 40 個
                  </Button>
                </div>
              )}
            </section>
          )}
        </div>
        <ImportPanel />
      </div>
    </div>
  )
}
