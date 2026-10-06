/** 匯入：列出 data/converted/ 的待匯入檔案、檢查結果，並可逐題對照原始試卷頁面預覽。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { Button } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { OptionBubble } from '@/components/OptionBubble'
import { PageHeader } from '@/components/PageHeader'
import { QuestionFigure, RichText } from '@/components/RichText'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { cx } from '@/lib/cx'
import { shortName } from '@/lib/format'
import type { ConvertedFile, ImportOutcome } from '@/lib/types'
import { fetchBundle, fetchConverted, importFile } from './api'

const LETTERS = 'ABCDEFGHIJ'

function useImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: importFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ingest'] })
      queryClient.invalidateQueries({ queryKey: ['bank'] })
    },
  })
}

function OutcomeNote({ outcome }: { outcome: ImportOutcome }) {
  if (!outcome.result) return <p className="m-0 text-sm text-bad">有錯誤，沒有匯入。</p>
  const result = outcome.result
  return (
    <p className="m-0 text-sm text-ok" role="status">
      已{result.created ? '新增' : '更新'}試卷：新增 {result.questions_created} 題、更新 {result.questions_updated} 題。
    </p>
  )
}

function FileRow({ file }: { file: ConvertedFile }) {
  const run = useImport()
  const report = file.report
  const errors = report?.issues.filter((issue) => issue.level === 'error').length ?? 0
  const warnings = report?.issues.filter((issue) => issue.level === 'warning').length ?? 0
  return (
    <li className="grid gap-3 border-b border-rule py-5 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="flex min-w-0 flex-col gap-1">
        <Link to={`/import/${encodeURIComponent(file.name)}`} className="truncate font-hand text-[17px] font-semibold text-ink hover:text-accent">
          {report?.subject ?? file.name}
        </Link>
        <span className="flex flex-wrap gap-x-3 text-xs text-muted">
          <span className="font-mono">{file.name}</span>
          {report && <span>{report.question_count} 題</span>}
          {errors > 0 && <span className="text-bad">{errors} 個錯誤</span>}
          {warnings > 0 && <span className="text-accent">{warnings} 個提醒</span>}
          {file.imported_paper_id && (
            <Link to={`/bank/papers/${file.imported_paper_id}`} className="text-ok underline underline-offset-2">
              已在題庫
            </Link>
          )}
        </span>
        {file.error && <span className="text-xs text-bad">格式錯誤：{file.error.split('\n')[0]}</span>}
        {run.data && <OutcomeNote outcome={run.data} />}
      </div>
      <div className="flex gap-2">
        <Link
          to={`/import/${encodeURIComponent(file.name)}`}
          className="inline-flex h-9 items-center rounded-md px-3 text-sm text-ink-soft hover:bg-accent-faint"
        >
          對照預覽
        </Link>
        <Button size="sm" variant={file.imported_paper_id ? 'secondary' : 'primary'} disabled={!report?.ok || run.isPending} onClick={() => run.mutate(file.name)}>
          {file.imported_paper_id ? '重新匯入' : '匯入'}
        </Button>
      </div>
    </li>
  )
}

export function ImportListPage() {
  const files = useQuery({ queryKey: ['ingest', 'files'], queryFn: fetchConverted })
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="匯入"
        title="待匯入的題目"
        description="把試卷 PDF、教材或題目文字檔交給 Claude Code 轉檔，轉好的檔案會出現在這裡（data/converted/）。匯入前可以逐題對照原始試卷。重新匯入同一份試卷會更新題目，作答紀錄會保留。"
      />
      {files.isPending ? (
        <Loading />
      ) : files.isError ? (
        <ErrorState error={files.error} onRetry={() => files.refetch()} />
      ) : files.data.length === 0 ? (
        <EmptyState title="沒有待匯入的檔案">
          在 Claude Code 說「幫我把 data/inbox 裡的試卷轉檔」，流程說明在 docs/ingest-gaopu.md、docs/ingest-lecture.md。
        </EmptyState>
      ) : (
        <section className="rounded-lg bg-sheet px-5 shadow-sheet sm:px-7">
          <ul className="m-0 list-none p-0">
            {files.data.map((file) => (
              <FileRow key={file.name} file={file} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export function ImportPreviewPage() {
  const name = decodeURIComponent(useParams().name ?? '')
  const bundle = useQuery({ queryKey: ['ingest', 'bundle', name], queryFn: () => fetchBundle(name) })
  const files = useQuery({ queryKey: ['ingest', 'files'], queryFn: fetchConverted })
  const [index, setIndex] = useState(0)
  const run = useImport()

  if (bundle.isPending) return <Loading />
  if (bundle.isError) return <ErrorState error={bundle.error} onRetry={() => bundle.refetch()} />
  const data = bundle.data
  const report = files.data?.find((file) => file.name === name)?.report
  const question = data.questions[index]
  const issuesFor = (number: number) => report?.issues.filter((issue) => issue.question === number) ?? []
  const paperIssues = report?.issues.filter((issue) => issue.question === null) ?? []

  return (
    <div className="flex flex-col gap-6">
      <Link to="/import" className="inline-flex w-fit items-center gap-1.5 text-sm text-muted hover:text-ink">
        <Icon name="back" size={16} />
        待匯入的題目
      </Link>
      <PageHeader
        eyebrow={[data.paper.year && `${data.paper.year} 年`, data.paper.exam_type, data.paper.categories?.join('、')].filter(Boolean).join('　')}
        title={shortName(data.paper.subject)}
        description={`${data.questions.length} 題・${name}`}
        actions={
          <Button onClick={() => run.mutate(name)} disabled={!report?.ok || run.isPending}>
            {run.isPending ? '匯入中…' : '確認並匯入'}
          </Button>
        }
      />
      {run.data && <OutcomeNote outcome={run.data} />}
      {paperIssues.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 rounded-md bg-accent-faint px-4 py-3 text-sm">
          {paperIssues.map((issue) => (
            <li key={issue.message} className={issue.level === 'error' ? 'text-bad' : 'text-ink-soft'}>
              {issue.message}
            </li>
          ))}
        </ul>
      )}

      <nav aria-label="選擇題號" className="flex flex-wrap gap-1">
        {data.questions.map((entry, position) => {
          const issues = issuesFor(entry.number)
          return (
            <button
              key={entry.number}
              type="button"
              onClick={() => setIndex(position)}
              aria-current={position === index ? 'true' : undefined}
              className={cx(
                'tabular h-8 min-w-8 rounded-sm border px-1.5 text-xs transition-colors',
                position === index ? 'border-ink bg-ink text-paper' : 'border-line bg-sheet hover:border-rule',
                issues.some((issue) => issue.level === 'error') && position !== index && 'border-bad text-bad',
                issues.length > 0 && issues.every((issue) => issue.level === 'warning') && position !== index && 'border-accent text-accent',
              )}
            >
              {entry.number}
            </button>
          )
        })}
      </nav>

      {question && (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <section aria-label="解析結果" className="flex flex-col gap-4 rounded-lg bg-sheet px-5 py-6 shadow-sheet sm:px-7">
            <h2 className="eyebrow m-0">解析結果・第 {question.number} 題</h2>
            {issuesFor(question.number).map((issue) => (
              <p key={issue.message} className={cx('m-0 text-sm', issue.level === 'error' ? 'text-bad' : 'text-accent')}>
                {issue.message}
              </p>
            ))}
            {question.passage && (
              <details className="rounded-md bg-sheet-tint px-4 py-2 text-sm">
                <summary className="cursor-pointer text-accent">題組文章</summary>
                <RichText className="mt-2 text-[15px]">{question.passage}</RichText>
              </details>
            )}
            <RichText>{question.stem}</RichText>
            {question.assets?.map((asset) => <QuestionFigure key={asset.path} path={asset.path} caption={asset.caption} />)}
            <div className="-mx-3 flex flex-col">
              {question.options?.map((option, position) => {
                const letter = LETTERS[position]
                return (
                  <OptionBubble
                    key={letter}
                    letter={letter}
                    text={option}
                    disabled
                    state={question.answer?.includes(letter) ? 'answer' : 'dimmed'}
                  />
                )
              })}
            </div>
            <p className="m-0 text-xs text-muted">
              答案來源：{question.answer_source}
              {question.points !== null && question.points !== undefined && `・配分 ${question.points}`}
              {question.tags && question.tags.length > 0 && `・標籤 ${question.tags.join('、')}`}
            </p>
            <div className="flex justify-between border-t border-rule pt-4">
              <Button variant="ghost" size="sm" onClick={() => setIndex(Math.max(0, index - 1))} disabled={index === 0}>
                <Icon name="back" size={16} />
                上一題
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIndex(Math.min(data.questions.length - 1, index + 1))}
                disabled={index === data.questions.length - 1}
              >
                下一題
                <Icon name="arrow" size={16} />
              </Button>
            </div>
          </section>
          <section aria-label="原始試卷" className="flex flex-col gap-3 lg:sticky lg:top-24">
            <h2 className="eyebrow m-0">原始試卷{question.source_ref?.page && `・第 ${question.source_ref.page} 頁`}</h2>
            {question.page_snapshot ? (
              <img
                src={`/api/bank/assets/${question.page_snapshot}`}
                alt="原始試卷頁面"
                className="w-full rounded-md border border-line bg-white shadow-sheet"
              />
            ) : (
              <p className="m-0 text-sm text-muted">這份檔案沒有原始頁面截圖。</p>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
