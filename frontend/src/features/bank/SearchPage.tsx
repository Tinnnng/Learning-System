/** 題目全文搜尋：比對題幹、選項、題組文章、詳解，命中的字用螢光筆標出來，可以直接拿結果出題練習。 */

import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Button } from '@/components/Button'
import { EssayReference } from '@/components/EssayReference'
import { Icon } from '@/components/Icon'
import { NoteControls } from '@/components/NoteControls'
import { OptionBubble } from '@/components/OptionBubble'
import { PageHeader } from '@/components/PageHeader'
import { QuestionFigure, RichText } from '@/components/RichText'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { cx } from '@/lib/cx'
import { plainText, shortName } from '@/lib/format'
import { useStartSession } from '@/lib/sessions'

type SearchResult = components['schemas']['SearchResult']
type SearchHit = components['schemas']['SearchHit']

const LETTERS = 'ABCDEFGHIJ'
const FIELD_LABEL: Record<SearchHit['field'], string | null> = {
  stem: null,
  options: '選項',
  passage: '題組文章',
  explanation: '詳解',
}

/** 題庫頁和搜尋頁共用的搜尋框，送出後到 /bank/search?q= */
export function QuestionSearchForm({ initial = '', className }: { initial?: string; className?: string }) {
  const navigate = useNavigate()
  const [text, setText] = useState(initial)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const q = text.trim()
    if (q) navigate(`/bank/search?q=${encodeURIComponent(q)}`)
  }
  return (
    <form role="search" onSubmit={submit} className={cx('flex gap-2', className)}>
      <div className="relative min-w-0 flex-1">
        <Icon name="search" size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
        <input
          type="search"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="搜尋題目，例如：比例原則、總統 任期"
          aria-label="搜尋題目"
          enterKeyHint="search"
          className="h-11 w-full rounded-md border border-line bg-sheet pl-10 pr-4 text-ink outline-none transition-colors focus:border-ink"
        />
      </div>
      <Button type="submit" variant="secondary" disabled={!text.trim()}>
        搜尋
      </Button>
    </form>
  )
}

/** 把關鍵字用螢光筆標出來 */
function Highlighted({ text, words }: { text: string; words: string[] }) {
  if (words.length === 0) return <>{text}</>
  const pattern = new RegExp(`(${words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  return (
    <>
      {text.split(pattern).map((part, index) =>
        index % 2 === 1 ? (
          <mark key={index} className="marker bg-transparent text-ink [--marker-scale:1]">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  )
}

function SearchRow({ hit, words }: { hit: SearchHit; words: string[] }) {
  const [open, setOpen] = useState(false)
  const { question } = hit
  const field = FIELD_LABEL[hit.field]
  return (
    <li className="border-b border-rule last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full flex-col gap-1.5 px-1 py-5 text-left transition-colors hover:bg-sheet-tint sm:px-3"
      >
        <span className="text-xs text-muted">
          {question.paper.year && `${question.paper.year} 年`}
          {question.paper.exam_type}｜{shortName(question.paper.subject)}　{question.label ?? `第 ${question.number} 題`}
          {question.type === 'essay' && <span className="ml-2 rounded-sm bg-hl-soft px-1.5 py-0.5 text-ink">申論</span>}
          {field && <span className="ml-2 rounded-sm bg-sheet-tint px-1.5 py-0.5">命中{field}</span>}
        </span>
        <span className={cx('text-[16px] leading-relaxed text-ink', !open && 'line-clamp-2')}>
          <Highlighted text={plainText(hit.field === 'stem' && open ? question.stem : hit.snippet)} words={words} />
        </span>
        {hit.field !== 'stem' && !open && (
          <span className="line-clamp-1 text-sm text-muted">{plainText(question.stem)}</span>
        )}
      </button>
      {open && (
        <div className="flex flex-col gap-4 px-1 pb-6 animate-[rise-in_var(--dur)_var(--ease-out)] sm:px-3">
          {question.passage && (
            <details className="rounded-md bg-sheet-tint px-4 py-2 text-sm" open={hit.field === 'passage'}>
              <summary className="cursor-pointer text-accent">題組文章</summary>
              <RichText className="mt-2 text-[15px]">{question.passage}</RichText>
            </details>
          )}
          {hit.field !== 'stem' && <RichText>{question.stem}</RichText>}
          {question.assets.map((asset) => (
            <QuestionFigure key={asset.path} path={asset.path} caption={asset.caption} />
          ))}
          <div className="-mx-3 flex flex-col">
            {question.options.map((option, index) => (
              <OptionBubble
                key={LETTERS[index]}
                letter={LETTERS[index]}
                text={option}
                disabled
                state={question.answer.includes(LETTERS[index]) ? 'answer' : 'dimmed'}
              />
            ))}
          </div>
          {question.type === 'essay' ? (
            <EssayReference explanation={question.explanation} rubric={question.rubric} />
          ) : (
            question.explanation && <RichText className="text-[15px]">{question.explanation}</RichText>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <NoteControls questionId={question.id} className="-ml-2" />
            <Link to={`/bank/papers/${question.paper.id}`} className="inline-flex h-11 items-center gap-1 text-sm text-accent hover:underline">
              看整份試卷
              <Icon name="arrow" size={16} />
            </Link>
          </div>
        </div>
      )}
    </li>
  )
}

export function SearchPage() {
  const [params] = useSearchParams()
  const q = params.get('q')?.trim() ?? ''
  const words = q.split(/\s+/).filter(Boolean)
  const search = useQuery({
    queryKey: ['bank', 'search', q],
    queryFn: () => api.get<SearchResult>(`/bank/search?q=${encodeURIComponent(q)}`),
    enabled: q.length > 0,
  })
  const start = useStartSession()
  const result = search.data

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow={
          <Link to="/bank" className="inline-flex items-center gap-1 hover:underline">
            <Icon name="back" size={14} />
            題庫
          </Link>
        }
        title="搜尋題目"
        description="比對題幹、選項、題組文章和詳解；用空白分隔多個關鍵字時，每個都要出現。"
        actions={
          result && result.total > 0 ? (
            <Button
              onClick={() =>
                start.mutate({ mode: 'practice', source: { kind: 'questions', question_ids: result.question_ids }, shuffle_questions: true })
              }
              disabled={start.isPending}
            >
              <Icon name="play" size={16} />
              練習這 {result.total} 題
            </Button>
          ) : undefined
        }
      />
      {/* key 讓網址的關鍵字改變時（例如上一頁）搜尋框跟著更新 */}
      <QuestionSearchForm key={q} initial={q} className="max-w-[640px]" />
      {start.isError && <ErrorState error={start.error} />}

      {!q ? (
        <EmptyState title="輸入關鍵字開始搜尋">例如「比例原則」「TCP」或「總統 任期」。</EmptyState>
      ) : search.isPending ? (
        <Loading />
      ) : search.isError ? (
        <ErrorState error={search.error} onRetry={() => search.refetch()} />
      ) : !result || result.total === 0 ? (
        <EmptyState title={`找不到「${q}」`}>換個說法，或減少關鍵字再試一次。</EmptyState>
      ) : (
        <section aria-label="搜尋結果" className="flex flex-col gap-3">
          <p className="m-0 text-sm text-muted" role="status">
            找到 {result.total} 題{result.total > result.items.length && `，先顯示前 ${result.items.length} 題`}
          </p>
          <div className="rounded-lg bg-sheet px-3 shadow-sheet sm:px-5">
            <ul className="m-0 list-none p-0">
              {result.items.map((hit) => (
                <SearchRow key={hit.question.id} hit={hit} words={words} />
              ))}
            </ul>
          </div>
        </section>
      )}
    </div>
  )
}
