import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { AiTutor } from '@/components/AiTutor'
import { Icon } from '@/components/Icon'
import { OptionBubble } from '@/components/OptionBubble'
import { PageHeader } from '@/components/PageHeader'
import { QuestionFigure, RichText } from '@/components/RichText'
import { ErrorState, Loading } from '@/components/States'
import { Switch } from '@/components/Controls'
import { shortName } from '@/lib/format'
import type { QuestionOut } from '@/lib/types'
import { fetchPaper } from './api'
import { StartPanel } from './StartPanel'

const LETTERS = 'ABCDEFGHIJ'

function QuestionPreview({ question, showAnswer }: { question: QuestionOut; showAnswer: boolean }) {
  return (
    <li className="grid grid-cols-[2.25rem_1fr] gap-x-3 border-b border-rule py-6 last:border-b-0">
      <span className="tabular pt-1 text-right text-sm text-accent">{question.number}</span>
      <div className="flex min-w-0 flex-col gap-3">
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
          {question.options.map((option, index) => {
            const letter = LETTERS[index]
            const correct = question.answer.includes(letter)
            return (
              <OptionBubble
                key={letter}
                letter={letter}
                text={option}
                disabled
                state={showAnswer ? (correct ? 'answer' : 'dimmed') : 'idle'}
              />
            )
          })}
        </div>
        {showAnswer && question.answer_source === 'MOD' && (
          <p className="m-0 text-xs text-muted">此題答案經考選部更正。</p>
        )}
        {showAnswer &&
          (question.explanation ? (
            <RichText className="text-[15px]">{question.explanation}</RichText>
          ) : (
            question.type !== 'essay' && <AiTutor questionId={question.id} />
          ))}
      </div>
    </li>
  )
}

export function PaperPage() {
  const id = Number(useParams().paperId)
  const paper = useQuery({ queryKey: ['bank', 'paper', id], queryFn: () => fetchPaper(id) })
  const [showAnswer, setShowAnswer] = useState(false)

  if (paper.isPending) return <Loading />
  if (paper.isError) return <ErrorState error={paper.error} onRetry={() => paper.refetch()} />
  const data = paper.data
  const choiceCount = data.questions.filter((q) => q.type !== 'essay').length

  return (
    <div className="flex flex-col gap-8">
      <Link to="/bank" className="inline-flex w-fit items-center gap-1.5 text-sm text-muted hover:text-ink">
        <Icon name="back" size={16} />
        題庫
      </Link>
      <PageHeader
        eyebrow={[data.year && `${data.year} 年`, data.exam_type, data.categories.join('、')].filter(Boolean).join('　')}
        title={shortName(data.subject)}
        description={[
          `${choiceCount} 題選擇題`,
          data.duration_minutes && `考試時間 ${data.duration_minutes} 分鐘`,
          data.paper_code && `試題代號 ${data.paper_code}`,
        ]
          .filter(Boolean)
          .join('・')}
      />

      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1.6fr)_minmax(300px,1fr)]">
        <section aria-label="題目" className="order-2 rounded-lg bg-sheet px-4 shadow-sheet sm:px-7 lg:order-1">
          <div className="flex items-center justify-between gap-4 border-b border-line pb-3 pt-5">
            <h2 className="eyebrow m-0">試題預覽</h2>
            <Switch label="顯示答案" checked={showAnswer} onChange={setShowAnswer} />
          </div>
          {data.answer_note && showAnswer && (
            <p className="m-0 mt-4 rounded-md bg-accent-faint px-4 py-2 text-sm text-ink-soft">更正備註：{data.answer_note}</p>
          )}
          <ol className="m-0 list-none p-0">
            {data.questions.map((question) => (
              <QuestionPreview key={question.id} question={question} showAnswer={showAnswer} />
            ))}
          </ol>
        </section>

        <aside className="order-1 rounded-lg bg-sheet p-5 shadow-sheet sm:p-6 lg:sticky lg:top-24 lg:order-2">
          <h2 className="m-0 mb-5 font-hand text-lg font-bold">開始寫這份試卷</h2>
          <StartPanel
            filter={{ paper_ids: [data.id] }}
            questionCount={choiceCount}
            durationMinutes={data.duration_minutes}
            title={data.title ?? data.subject}
          />
        </aside>
      </div>
    </div>
  )
}
