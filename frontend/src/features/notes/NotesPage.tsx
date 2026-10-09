/** 收藏與筆記：收藏的題目、寫過筆記的題目，可以直接拿收藏的題目來練習。 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button } from '@/components/Button'
import { Segmented } from '@/components/Controls'
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
import { noteKey } from '@/lib/notes'
import { useStartSession } from '@/lib/sessions'

type NotedQuestion = components['schemas']['NotedQuestion']
type Which = 'all' | 'starred' | 'noted'
const LETTERS = 'ABCDEFGHIJ'

function NotedRow({ entry }: { entry: NotedQuestion }) {
  const [open, setOpen] = useState(false)
  const { question, note } = entry
  return (
    <li className="border-b border-rule last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="grid w-full grid-cols-[auto_1fr] items-start gap-x-3 gap-y-1 px-1 py-5 text-left transition-colors hover:bg-sheet-tint sm:px-3"
      >
        <Icon
          name="star"
          size={18}
          filled={note.starred}
          label={note.starred ? '已收藏' : undefined}
          className={cx('mt-0.5', note.starred ? 'text-star' : 'text-line')}
        />
        <span className="flex min-w-0 flex-col gap-1.5">
          <span className="text-xs text-muted">
            {question.paper.year && `${question.paper.year} 年`}
            {question.paper.exam_type}｜{shortName(question.paper.subject)}　{question.label ?? `第 ${question.number} 題`}
          </span>
          <span className={cx('text-[16px] leading-relaxed text-ink', !open && 'line-clamp-2')}>{plainText(question.stem)}</span>
          {note.note && !open && (
            <span className="mt-1 w-fit max-w-full truncate border-l-2 border-accent bg-sheet-tint py-0.5 pr-2 pl-2.5 text-sm text-ink-soft">{note.note}</span>
          )}
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-4 px-1 pb-6 animate-[rise-in_var(--dur)_var(--ease-out)] sm:px-3 sm:pl-10">
          {question.passage && (
            <details className="rounded-md bg-sheet-tint px-4 py-2 text-sm">
              <summary className="cursor-pointer text-accent">題組文章</summary>
              <RichText className="mt-2 text-[15px]">{question.passage}</RichText>
            </details>
          )}
          <RichText>{question.stem}</RichText>
          {question.assets.map((asset) => (
            <QuestionFigure key={asset.path} path={asset.path} caption={asset.caption} />
          ))}
          <div className="-mx-3 flex flex-col">
            {question.options.map((option, index) => (
              <OptionBubble
                key={LETTERS[index]}
                letter={LETTERS[index]}
                text={option}
                readOnly
                state={question.answer.includes(LETTERS[index]) ? 'answer' : 'dimmed'}
              />
            ))}
          </div>
          {question.type === 'essay' ? (
            <EssayReference explanation={question.explanation} rubric={question.rubric} />
          ) : (
            question.explanation && <RichText className="text-[15px]">{question.explanation}</RichText>
          )}
          <NoteControls questionId={question.id} className="-ml-2" />
        </div>
      )}
    </li>
  )
}

export function NotesPage() {
  const queryClient = useQueryClient()
  // 篩選放在網址（?which=starred）：重新整理、上一頁回來都還在
  const [params, setParams] = useSearchParams()
  const which: Which = (['all', 'starred', 'noted'] as const).find((value) => value === params.get('which')) ?? 'all'
  const setWhich = (value: Which) => setParams(value === 'all' ? {} : { which: value }, { replace: true })
  const list = useQuery({ queryKey: ['notes', 'list', which], queryFn: () => api.get<NotedQuestion[]>(`/notes/list?which=${which}`) })
  const start = useStartSession()
  const entries = list.data ?? []
  const starredCount = entries.filter((entry) => entry.note.starred).length

  useEffect(() => {
    // 列表已經帶了每題的收藏與筆記，直接放進快取，展開時不用再查
    for (const entry of list.data ?? []) queryClient.setQueryData(noteKey(entry.question.id), entry.note)
  }, [list.data, queryClient])

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="收藏"
        title="收藏與筆記"
        description="作答時點星號收藏想再看的題目，或寫下自己的筆記；它們都會集中在這裡。"
        actions={
          starredCount > 0 && which !== 'noted' ? (
            <Button
              onClick={() => start.mutate({ mode: 'practice', source: { kind: 'starred' }, shuffle_questions: true })}
              disabled={start.isPending}
            >
              <Icon name="play" size={16} />
              練習收藏的題目
            </Button>
          ) : undefined
        }
      />
      <Segmented
        label="顯示"
        value={which}
        onChange={setWhich}
        className="max-w-[420px]"
        options={[
          { value: 'all', label: '全部' },
          { value: 'starred', label: '收藏' },
          { value: 'noted', label: '有筆記' },
        ]}
      />
      {start.isError && <ErrorState error={start.error} />}
      {list.isPending ? (
        <Loading />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => list.refetch()} />
      ) : entries.length === 0 ? (
        <EmptyState title={which === 'noted' ? '還沒有筆記' : '還沒有收藏'}>
          作答、看錯題或瀏覽試卷時，點題目下方的「收藏」或「寫筆記」。
        </EmptyState>
      ) : (
        <section aria-label="收藏與筆記列表" className="rounded-lg bg-sheet px-3 shadow-sheet sm:px-5">
          <ul className="stagger m-0 list-none p-0">
            {entries.map((entry) => (
              <NotedRow key={entry.question.id} entry={entry} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
