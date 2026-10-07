/** 一題的完整呈現：題組文章、題幹、附圖、選項（螢光筆劃記）、揭曉後的詳解。 */

import { useState } from 'react'
import { AiTutor } from '@/components/AiTutor'
import { Button } from '@/components/Button'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { NoteControls } from '@/components/NoteControls'
import { type BubbleState, OptionBubble } from '@/components/OptionBubble'
import { QuestionFigure, RichText } from '@/components/RichText'
import { cx } from '@/lib/cx'
import { shortName } from '@/lib/format'
import type { ItemOut } from '@/lib/types'
import { EssayAnswer } from './EssayAnswer'

export const LETTERS = 'ABCDEFGHIJ'

function bubbleState(item: ItemOut, letter: string, selection: string[]): BubbleState {
  if (item.revealed) {
    const chosen = (item.response ?? []).includes(letter)
    const correct = (item.correct ?? []).includes(letter)
    if (chosen) return correct ? 'right' : 'wrong'
    return correct ? 'answer' : 'dimmed'
  }
  return selection.includes(letter) ? 'chosen' : 'idle'
}

interface QuestionBlockProps {
  item: ItemOut
  /** 目前選取（複選題在練習模式確定前是本地狀態） */
  selection: string[]
  onToggle: (letter: string) => void
  /** 複選題練習模式：按「確定」才送出 */
  onConfirmMulti?: () => void
  busy?: boolean
  headingLevel?: 'h2' | 'h3'
  /** 申論題作答需要的資訊 */
  essay?: { sessionId: number; practice: boolean; submitted: boolean; onUpdate: (item: ItemOut) => void }
}

export function QuestionBlock({ item, selection, onToggle, onConfirmMulti, busy, headingLevel = 'h2', essay }: QuestionBlockProps) {
  const [showPage, setShowPage] = useState(false)
  const Heading = headingLevel
  const multiple = item.type === 'multi_choice'
  const isEssay = item.type === 'essay'
  const locked = item.revealed || busy

  return (
    <article className="flex flex-col gap-4" aria-labelledby={`q-${item.position}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <Heading id={`q-${item.position}`} className="m-0 flex items-baseline gap-3">
          <span className="tabular text-2xl font-medium text-accent">{item.position}</span>
          <span className="text-xs font-normal text-muted">
            {item.paper.year && `${item.paper.year} 年`}
            {item.paper.exam_type}｜{shortName(item.paper.subject)}
            {multiple && <span className="ml-2 rounded-sm bg-accent-faint px-1.5 py-0.5 text-accent">複選</span>}
            {isEssay && (
              <span className="ml-2 rounded-sm bg-hl-soft px-1.5 py-0.5 text-ink">
                申論{item.label && ` ${item.label}`}・{item.points} 分
              </span>
            )}
          </span>
        </Heading>
        {item.page_snapshot && (
          <button
            type="button"
            onClick={() => setShowPage(true)}
            className="inline-flex items-center gap-1 text-xs text-muted underline-offset-4 hover:text-accent hover:underline"
          >
            <Icon name="page" size={15} />
            看原始試卷
          </button>
        )}
      </div>

      {item.passage && (
        <details className="group rounded-md border border-rule bg-sheet-tint" open>
          <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-2.5 text-sm text-accent">
            {isEssay ? '題目說明' : '題組文章'}
            <span className="text-xs text-muted group-open:hidden">展開</span>
          </summary>
          <RichText className="max-h-[40vh] overflow-y-auto px-4 pb-4 text-[15px]">{item.passage}</RichText>
        </details>
      )}

      <RichText>{item.stem}</RichText>
      {item.assets.map((asset) => (
        <QuestionFigure key={asset.path} path={asset.path} caption={asset.caption} />
      ))}

      {isEssay ? (
        essay && <EssayAnswer item={item} {...essay} />
      ) : (
        <>
          <div role={multiple ? 'group' : 'radiogroup'} aria-label={`第 ${item.position} 題選項`} className="-mx-3 flex flex-col gap-0.5">
            {item.options.map((option, index) => {
              const letter = LETTERS[index]
              return (
                <OptionBubble
                  key={letter}
                  letter={letter}
                  text={option}
                  multiple={multiple}
                  state={bubbleState(item, letter, selection)}
                  disabled={locked}
                  onSelect={() => onToggle(letter)}
                />
              )
            })}
          </div>

          {multiple && onConfirmMulti && !item.revealed && (
            <div>
              <Button variant="secondary" onClick={onConfirmMulti} disabled={selection.length === 0 || busy}>
                確定答案
              </Button>
            </div>
          )}

          {item.revealed && (
            <div
              className={cx(
                'flex flex-col gap-2 rounded-md border-l-[3px] px-4 py-3 animate-[rise-in_var(--dur)_var(--ease-out)]',
                item.is_correct ? 'border-ok bg-ok-soft/50' : 'border-bad bg-bad-soft/50',
              )}
              aria-live="polite"
            >
              <p className="m-0 font-medium">
                {item.is_correct
                  ? '答對了。'
                  : item.answered
                    ? `答錯了，正確答案是 ${(item.correct ?? []).join('、')}。`
                    : `沒有作答，正確答案是 ${(item.correct ?? []).join('、')}。`}
                {!item.is_correct && item.answered && <span className="ml-1 font-normal text-muted">已收進錯題本。</span>}
              </p>
              {item.explanation && <RichText className="text-[15px]">{item.explanation}</RichText>}
              {item.source_ref && item.paper.origin === 'generated' && (
                <p className="m-0 text-xs text-muted">
                  出處：{item.source_ref.file}
                  {item.source_ref.slide && ` 第 ${item.source_ref.slide} 張投影片`}
                  {item.source_ref.page && ` 第 ${item.source_ref.page} 頁`}
                  {item.source_ref.note && ` ${item.source_ref.note}`}
                </p>
              )}
            </div>
          )}

        </>
      )}

      {item.revealed && !item.explanation && !isEssay && <AiTutor questionId={item.question_id} myAnswer={item.original_response} />}

      <NoteControls questionId={item.question_id} className="-ml-2" />

      {item.page_snapshot && (
        <Dialog open={showPage} onClose={() => setShowPage(false)} title="原始試卷" wide>
          <img
            src={`/api/bank/assets/${item.page_snapshot}`}
            alt={`第 ${item.position} 題所在的原始試卷頁面`}
            className="w-full rounded-sm border border-line bg-white"
          />
        </Dialog>
      )}
    </article>
  )
}
