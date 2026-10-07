/**
 * 錯題匯出 PDF：專門給列印用的版面，交給瀏覽器「另存為 PDF」（公式、表格、圖片都能保留）。
 * 前半是題目（可以先寫一遍），後半是解答、詳解與自己的筆記。
 */

import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Button } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { QuestionFigure, RichText } from '@/components/RichText'
import { ErrorState, Loading } from '@/components/States'
import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { shortName, todayLabel } from '@/lib/format'
import { fetchWrongQuestions, type WrongStatus } from './api'

type Note = components['schemas']['NoteOut']
const LETTERS = 'ABCDEFGHIJ'

export function PrintPage() {
  const [params] = useSearchParams()
  const status = (params.get('status') as WrongStatus) || 'active'
  const subject = params.get('subject')
  const wrong = useQuery({ queryKey: ['review', 'wrong', status, subject], queryFn: () => fetchWrongQuestions(status, subject) })
  const ids = wrong.data?.map((entry) => entry.question.id) ?? []
  const notes = useQuery({
    queryKey: ['notes', 'batch', ids.join(',')],
    queryFn: () => api.get<Note[]>(`/notes/questions?${ids.map((id) => `ids=${id}`).join('&')}`),
    enabled: ids.length > 0,
  })
  const aiExplanations = useQuery({
    queryKey: ['tutor', 'explanations', ids.join(',')],
    queryFn: () => api.get<Record<string, string>>(`/tutor/explanations?${ids.map((id) => `ids=${id}`).join('&')}`),
    enabled: ids.length > 0,
  })

  const ready = wrong.isSuccess && (ids.length === 0 || (notes.isSuccess && aiExplanations.isSuccess))
  useEffect(() => {
    if (!ready || ids.length === 0) return
    // 等字型與公式排好再開列印視窗
    let cancelled = false
    document.fonts.ready.then(() => {
      if (!cancelled) window.setTimeout(() => window.print(), 300)
    })
    return () => {
      cancelled = true
    }
  }, [ready, ids.length])

  if (wrong.isPending) return <Loading label="整理錯題中" />
  if (wrong.isError) return <ErrorState error={wrong.error} onRetry={() => wrong.refetch()} />
  const entries = wrong.data
  const noteFor = new Map((notes.data ?? []).map((note) => [note.question_id, note.note]))
  // 沒有官方詳解時，用之前問過的 AI 助教詳解（不會在這裡新呼叫 AI）
  const explanationFor = (questionId: number, official: string | null | undefined) =>
    official ? { text: official, ai: false } : aiExplanations.data?.[questionId] ? { text: aiExplanations.data[questionId], ai: true } : null
  const title = `${subject ? shortName(subject) : '全部科目'}・錯題本`

  return (
    <article className="print-sheet mx-auto flex max-w-[780px] flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link to="/review" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
          <Icon name="back" size={16} />
          錯題本
        </Link>
        <Button onClick={() => window.print()} disabled={entries.length === 0}>
          列印／另存 PDF
        </Button>
      </div>
      <p className="m-0 rounded-md bg-hl-soft px-4 py-2 text-sm text-ink-soft print:hidden">
        在列印視窗的「目的地」選「另存為 PDF」就能存成檔案。建議勾選「背景圖形」，螢光筆標示才會印出來。
      </p>

      <header className="flex flex-col gap-1 border-b border-line pb-4">
        <span className="eyebrow">{todayLabel()}</span>
        <h1 className="m-0 font-hand text-[30px] font-bold">{title}</h1>
        <p className="m-0 text-sm text-muted">
          共 {entries.length} 題。前半部是題目，可以先寫一遍；解答與詳解在後半部。
        </p>
      </header>

      {entries.length === 0 ? (
        <p className="m-0 text-muted">目前沒有符合條件的錯題。</p>
      ) : (
        <>
          <section aria-label="題目" className="flex flex-col">
            <h2 className="eyebrow m-0 mb-2">題目</h2>
            <ol className="m-0 list-none p-0">
              {entries.map(({ question }, index) => (
                <li key={question.id} className="print-avoid-break flex flex-col gap-3 border-b border-rule py-5 last:border-b-0">
                  <p className="m-0 flex items-baseline gap-2 text-xs text-muted">
                    <span className="font-hand text-xl text-accent">{index + 1}</span>
                    {question.paper.year && `${question.paper.year} 年`}
                    {question.paper.exam_type}｜{shortName(question.paper.subject)} 第 {question.label ?? question.number} 題
                  </p>
                  {question.passage && <RichText className="rounded-md bg-sheet-tint px-4 py-3 text-[14px]">{question.passage}</RichText>}
                  <RichText>{question.stem}</RichText>
                  {question.assets.map((asset) => (
                    <QuestionFigure key={asset.path} path={asset.path} caption={asset.caption} />
                  ))}
                  <ol className="m-0 grid list-none gap-1 p-0 pl-1">
                    {question.options.map((option, optionIndex) => (
                      <li key={optionIndex} className="flex gap-3 text-[15px]">
                        <span className="font-hand text-accent">({LETTERS[optionIndex]})</span>
                        <RichText inline>{option}</RichText>
                      </li>
                    ))}
                  </ol>
                </li>
              ))}
            </ol>
          </section>

          <section aria-label="解答" className="print-page-break flex flex-col gap-6">
            <div className="flex flex-col gap-3">
              <h2 className="eyebrow m-0">答案一覽</h2>
              <ol className="m-0 grid list-none grid-cols-5 gap-x-4 gap-y-2 p-0">
                {entries.map(({ question }, index) => (
                  <li key={question.id} className="flex items-baseline gap-2 border-b border-rule pb-1">
                    <span className="font-hand text-lg text-accent">{index + 1}</span>
                    <span className="marker font-medium [--marker-color:var(--ok-hl)]">{question.answer.join('、')}</span>
                  </li>
                ))}
              </ol>
            </div>

            {entries.some(({ question }) => explanationFor(question.id, question.explanation) || noteFor.get(question.id)) && (
              <div className="flex flex-col">
                <h2 className="eyebrow m-0 mb-2">詳解與筆記</h2>
                <ol className="m-0 list-none p-0">
                  {entries.map(({ question, progress }, index) => {
                    const note = noteFor.get(question.id)
                    const explanation = explanationFor(question.id, question.explanation)
                    if (!explanation && !note) return null
                    return (
                      <li key={question.id} className="print-avoid-break flex flex-col gap-2 border-b border-rule py-4 last:border-b-0">
                        <p className="m-0 flex flex-wrap items-baseline gap-x-3">
                          <span className="font-hand text-xl text-accent">{index + 1}</span>
                          <span className="marker font-medium [--marker-color:var(--ok-hl)]">答案 {question.answer.join('、')}</span>
                          <span className="text-xs text-muted">
                            錯 {progress.wrong_count} 次・連續答對 {progress.correct_streak}／{progress.mastery_target}
                          </span>
                        </p>
                        {explanation && (
                          <div className="flex flex-col gap-1">
                            {explanation.ai && <span className="text-[11px] text-muted">AI 助教詳解（僅供參考）</span>}
                            <RichText className="text-[14px]">{explanation.text}</RichText>
                          </div>
                        )}
                        {note && (
                          <p className="m-0 rounded-sm bg-hl-soft px-3 py-1.5 font-hand text-[15px] whitespace-pre-wrap">筆記：{note}</p>
                        )}
                      </li>
                    )
                  })}
                </ol>
              </div>
            )}
          </section>
        </>
      )}
    </article>
  )
}
