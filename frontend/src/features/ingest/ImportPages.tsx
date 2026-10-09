/** 匯入：列出 data/converted/ 的待匯入檔案、檢查結果，並可逐題對照原始試卷頁面預覽。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { Button } from '@/components/Button'
import { QuestionEditorDialog } from '@/components/QuestionEditorDialog'
import { Icon } from '@/components/Icon'
import { OptionBubble } from '@/components/OptionBubble'
import { PageHeader } from '@/components/PageHeader'
import { QuestionFigure, RichText } from '@/components/RichText'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { cx } from '@/lib/cx'
import { api } from '@/lib/api'
import { shortName } from '@/lib/format'
import { type QuestionDraft, toDraft } from '@/lib/questionEdit'
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
  if (!outcome.result)
    return (
      <p className="m-0 text-sm text-bad" role="alert">
        有錯誤，沒有匯入。按「對照預覽」看是哪幾題、怎麼修。
      </p>
    )
  const result = outcome.result
  return (
    <p className="m-0 text-sm text-ok" role="status">
      已{result.created ? '新增' : '更新'}試卷：新增 {result.questions_created} 題、更新 {result.questions_updated} 題。
    </p>
  )
}

/** 錯誤／提醒不只靠顏色區分，前面加上文字 */
function issueLabel(level: string) {
  return <span className="font-medium">{level === 'error' ? '錯誤：' : '提醒：'}</span>
}

function FileRow({ file }: { file: ConvertedFile }) {
  const run = useImport()
  const report = file.report
  const errors = report?.issues.filter((issue) => issue.level === 'error').length ?? 0
  const warnings = report?.issues.filter((issue) => issue.level === 'warning').length ?? 0
  return (
    <li className="grid gap-3 border-b border-rule py-5 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="flex min-w-0 flex-col gap-1">
        {/* 標題不做成連結：同一列已經有「對照預覽」連到同一頁，Tab 一次就好 */}
        <span className="truncate font-display text-[17px] font-semibold text-ink">
          {report ? shortName(report.subject) : file.name}
        </span>
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
        {run.isError && <ErrorState error={run.error} />}
      </div>
      <div className="flex gap-2">
        <Link
          to={`/import/${encodeURIComponent(file.name)}`}
          className="hit inline-flex h-9 items-center rounded-md px-3 text-sm text-ink-soft hover:bg-accent-faint"
        >
          對照預覽
        </Link>
        <Button
          size="sm"
          variant={file.imported_paper_id ? 'secondary' : 'primary'}
          disabled={!report?.ok || run.isPending}
          onClick={() => run.mutate(file.name)}
          aria-label={`${file.imported_paper_id ? '重新匯入' : '匯入'}「${file.name}」`}
        >
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
          <ul className="stagger m-0 list-none p-0">
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
  const name = useParams().name ?? ''  // React Router 已經解碼過，不能再 decodeURIComponent（檔名有 % 會壞）
  const bundle = useQuery({ queryKey: ['ingest', 'bundle', name], queryFn: () => fetchBundle(name) })
  const files = useQuery({ queryKey: ['ingest', 'files'], queryFn: fetchConverted })
  const [index, setIndex] = useState(0)
  const [editing, setEditing] = useState(false)
  const run = useImport()
  const queryClient = useQueryClient()

  if (bundle.isPending) return <Loading />
  if (bundle.isError) return <ErrorState error={bundle.error} onRetry={() => bundle.refetch()} />
  const data = bundle.data
  const report = files.data?.find((file) => file.name === name)?.report
  const question = data.questions[index]
  const editable = name.toLowerCase().endsWith('.json')
  const saveEdit = async (draft: QuestionDraft) => {
    // 只換掉可編輯的欄位，圖片、頁面截圖、答案來源等保留
    const questions = data.questions.map((item, position) => (position === index ? { ...item, ...draft } : item))
    await api.put(`/ingest/files/${encodeURIComponent(name)}`, { ...data, questions })
    await queryClient.invalidateQueries({ queryKey: ['ingest'] })
  }
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
      {run.isError && <ErrorState error={run.error} />}
      {paperIssues.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 rounded-md bg-accent-faint px-4 py-3 text-sm">
          {paperIssues.map((issue) => (
            <li key={issue.message} className={issue.level === 'error' ? 'text-bad' : 'text-ink-soft'}>
              {issueLabel(issue.level)}
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
              aria-label={`第 ${entry.number} 題${
                issues.some((issue) => issue.level === 'error') ? '，有錯誤' : issues.length > 0 ? '，有提醒' : ''
              }`}
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
            <div className="flex items-center justify-between gap-3">
              <h2 className="eyebrow m-0">解析結果・{question.label ?? `第 ${question.number} 題`}</h2>
              {editable && (
                <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
                  <Icon name="edit" size={16} />
                  修改這題
                </Button>
              )}
            </div>
            {issuesFor(question.number).map((issue) => (
              <p key={issue.message} className={cx('m-0 text-sm', issue.level === 'error' ? 'text-bad' : 'text-accent')}>
                {issueLabel(issue.level)}
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
                    readOnly
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
                width={1240}
                height={1754}
                className="h-auto w-full rounded-md border border-line bg-white shadow-sheet"
              />
            ) : (
              <p className="m-0 text-sm text-muted">這份檔案沒有原始頁面截圖。</p>
            )}
          </section>
        </div>
      )}
      {question && (
        <QuestionEditorDialog
          title={`修改第 ${question.number} 題`}
          initial={editing ? toDraft(question) : null}
          onClose={() => setEditing(false)}
          onSave={saveEdit}
          note="修改會直接寫回匯入檔，存檔後會重新檢查；確認沒問題再按「確認並匯入」。"
        />
      )}
    </div>
  )
}
