/**
 * 自己上傳、轉檔（2026-10-12 使用者決定「兩種都做」）：
 * - 題目文字檔：上傳後直接出現在下方「待匯入」。
 * - 高普考 PDF：「自動轉檔」（不用 AI）或「AI 校對後轉檔」（一頁一次 AI 呼叫）；也可以交給 Claude Code 離線轉。
 * - 教材：「AI 出題」讓系統內 AI 讀教材出選擇題。
 * 不管哪一種，轉好都要到匯入預覽頁逐題確認後才匯入。會花用量的按鈕都先顯示預估，可以中斷。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/Button'
import { Segmented } from '@/components/Controls'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'
import { api, ApiError } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { cx } from '@/lib/cx'
import { fileSize, shortName, usd } from '@/lib/format'

type UploadKind = 'gaopu' | 'lecture' | 'text'
type UploadResult = components['schemas']['UploadResult']
type PendingSources = components['schemas']['PendingSources']
type PendingPaper = components['schemas']['PendingPaper']
type PendingLecture = components['schemas']['PendingLecture']
type ConvertResult = components['schemas']['ConvertResult']

/** 每次 AI 呼叫的大約花費（Haiku＋一張圖片或幾千字教材），只用來顯示預估 */
const COST_PER_CALL = 0.01

const ACCEPT: Record<UploadKind, string> = {
  gaopu: '.pdf',
  lecture: '.pptx,.docx,.pdf,.ppt,.doc',
  text: '.txt,.md,.json',
}

const fetchPending = () => api.get<PendingSources>('/ingest/uploads')
const requestId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
const cancelRequest = (id: string) => void api.post(`/ai/requests/${id}/cancel`).catch(() => undefined)

function errorText(error: unknown) {
  return error instanceof ApiError && typeof error.detail === 'string' ? error.detail : '發生錯誤，請再試一次'
}

export function UploadPanel() {
  const queryClient = useQueryClient()
  const pending = useQuery({ queryKey: ['ingest', 'uploads'], queryFn: fetchPending })
  const [kind, setKind] = useState<UploadKind>('gaopu')
  const [examType, setExamType] = useState<'高考' | '普考'>('普考')
  const [category, setCategory] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const categoryId = useId()
  const upload = useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData()
      form.append('kind', kind)
      if (kind === 'gaopu') {
        form.append('exam_type', examType)
        form.append('category', category.trim())
      }
      for (const file of files) form.append('files', file)
      return api.postForm<UploadResult>('/ingest/uploads', form)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ingest'] }),
  })
  const needsCategory = kind === 'gaopu' && !category.trim()

  const papers = pending.data?.papers ?? []
  const lectures = pending.data?.lectures ?? []

  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="upload-title" className="flex flex-col gap-4 rounded-lg bg-sheet px-5 py-6 shadow-sheet sm:px-7">
        <h2 id="upload-title" className="m-0 font-display text-lg font-bold">
          上傳新檔案
        </h2>
        <Segmented
          label="檔案種類"
          value={kind}
          onChange={(next) => {
            setKind(next)
            upload.reset()
          }}
          options={[
            { value: 'gaopu', label: '高普考試卷', hint: '題目＋答案 PDF' },
            { value: 'lecture', label: '期中考教材', hint: 'PPT／Word／PDF' },
            { value: 'text', label: '題目文字檔', hint: '.txt／.md／.json' },
          ]}
        />
        {kind === 'gaopu' && (
          <div className="grid gap-3 sm:grid-cols-[200px_minmax(0,1fr)]">
            <Segmented
              label="考試"
              value={examType}
              onChange={setExamType}
              options={[
                { value: '普考', label: '普考' },
                { value: '高考', label: '高考' },
              ]}
            />
            <div className="flex flex-col gap-1.5">
              <label htmlFor={categoryId} className="text-xs text-muted">
                類科（同一份試卷會依類科分組）
              </label>
              <input
                id={categoryId}
                name="category"
                autoComplete="off"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                placeholder="例如：一般行政…"
                className="h-11 rounded-md border border-line bg-sheet px-3 text-ink outline-none focus:border-ink"
              />
            </div>
          </div>
        )}
        <p className="m-0 text-sm text-muted">
          {kind === 'gaopu'
            ? '一次選題目 PDF 和答案 PDF（ANS 開頭是標準答案、MOD 開頭是更正答案），檔名請維持考選部下載的原檔名。'
            : kind === 'lecture'
              ? '上傳後可以讓系統內 AI 出選擇題，或交給 Claude Code 出題（品質最好）。'
              : '格式見 docs/text-question-format.md；上傳後直接出現在下方「待匯入」，不需要 AI。'}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={ACCEPT[kind]}
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              const files = Array.from(event.target.files ?? [])
              if (files.length) upload.mutate(files)
              event.target.value = ''
            }}
          />
          <Button onClick={() => fileRef.current?.click()} disabled={upload.isPending || needsCategory}>
            <Icon name="import" size={17} />
            {upload.isPending ? '上傳中…' : '選擇檔案上傳'}
          </Button>
          {needsCategory && <span className="text-xs text-muted">先填類科</span>}
        </div>
        <div aria-live="polite" className="empty:hidden">
          {upload.data && (
            <p className="m-0 rounded-md bg-ok-soft/60 px-4 py-2 text-sm">
              已上傳 {upload.data.saved.join('、')}。
              {(upload.data.warnings ?? []).map((warning) => (
                <span key={warning} className="block text-accent">
                  提醒：{warning}
                </span>
              ))}
            </p>
          )}
        </div>
        {upload.isError && <ErrorState error={upload.error} />}
      </section>

      {(papers.length > 0 || lectures.length > 0) && (
        <section aria-labelledby="pending-title" className="rounded-lg bg-sheet px-5 py-5 shadow-sheet sm:px-7">
          <h2 id="pending-title" className="m-0 font-display text-lg font-bold">
            等著轉檔
          </h2>
          <p className="m-0 mt-1 text-sm text-muted">
            轉好會出現在下方「待匯入」，一定要到「對照預覽」逐題確認再匯入。也可以在 Claude Code 說「幫我轉 data/inbox 裡新上傳的檔案」，離線轉的品質最好。
          </p>
          <ul className="m-0 mt-3 list-none p-0">
            {papers.map((paper) => (
              <PaperRow key={paper.source_key} paper={paper} />
            ))}
            {lectures.map((item) => (
              <LectureRow key={item.name} lecture={item} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function useAiRun<T>(run: (id: string) => Promise<T>) {
  const queryClient = useQueryClient()
  const current = useRef<string | null>(null)
  const mutation = useMutation({
    mutationFn: () => {
      const id = requestId()
      current.current = id
      return run(id)
    },
    onSettled: () => {
      current.current = null
      queryClient.invalidateQueries({ queryKey: ['ingest'] })
      queryClient.invalidateQueries({ queryKey: ['ai', 'status'] })
    },
  })
  const stop = () => current.current && cancelRequest(current.current)
  return { mutation, stop }
}

function ConvertDone({ result }: { result: ConvertResult }) {
  return (
    <p className="m-0 text-sm text-ok">
      轉好了（{result.report.question_count} 題
      {result.calls > 0 && `，呼叫 AI ${result.calls} 次、約 ${usd(result.cost_usd)}`}）。
      <Link to={`/import/${encodeURIComponent(result.file)}`} className="ml-1 font-medium text-accent underline underline-offset-2">
        去對照預覽
      </Link>
    </p>
  )
}

function PaperRow({ paper }: { paper: PendingPaper }) {
  const [confirmAi, setConfirmAi] = useState(false)
  const convert = (useAi: boolean) => (id: string) =>
    api.post<ConvertResult>(`/ingest/uploads/papers/${paper.source_key}/convert`, { use_ai: useAi, request_id: id })
  const plain = useAiRun(convert(false))
  const withAi = useAiRun(convert(true))
  const busy = plain.mutation.isPending || withAi.mutation.isPending
  const blocked = !paper.has_question || !paper.has_answer || paper.kind === 'essay' || paper.reviewed
  const result = withAi.mutation.data ?? plain.mutation.data
  const error = withAi.mutation.error ?? plain.mutation.error
  const status = paper.reviewed
    ? '已經有 Claude Code 逐題校對過的版本，不用再轉，直接在下方「待匯入」匯入'
    : !paper.has_question
    ? '只有答案，還缺題目 PDF'
    : !paper.has_answer
      ? '還缺答案 PDF（ANS／MOD）'
      : paper.kind === 'essay'
        ? '申論題：系統內 AI 不寫參考答案，請交給 Claude Code'
        : paper.kind === 'mixed'
          ? '有申論題：只轉選擇題，申論題請交給 Claude Code'
          : null

  return (
    <li className="flex flex-col gap-2 border-t border-rule py-4 first:border-t-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="font-medium text-ink">
          {paper.year} 年{paper.exam_type}　{shortName(paper.subject)}
          <span className="ml-2 text-xs font-normal text-muted">{paper.categories.join('、')}・{paper.pages} 頁</span>
        </span>
        {paper.converted && !paper.reviewed && <span className="text-xs text-ok">已轉過，再轉會覆蓋</span>}
      </div>
      {status && (
        <p className={cx('m-0 text-sm', paper.reviewed ? 'text-ok' : blocked ? 'text-bad' : 'text-accent')}>
          {paper.reviewed ? '' : blocked ? '無法轉檔：' : '提醒：'}
          {status}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" disabled={blocked || busy} onClick={() => plain.mutation.mutate()}>
          {plain.mutation.isPending ? '轉檔中…' : '自動轉檔（不用 AI）'}
        </Button>
        <Button size="sm" disabled={blocked || busy} onClick={() => setConfirmAi(true)}>
          <Icon name="spark" size={16} />
          {withAi.mutation.isPending ? `AI 校對中（約 ${paper.estimated_calls} 次）…` : 'AI 校對後轉檔'}
        </Button>
        {withAi.mutation.isPending && (
          <Button size="sm" variant="danger" onClick={withAi.stop}>
            <Icon name="stop" size={16} />
            中斷
          </Button>
        )}
      </div>
      <div aria-live="polite" className="empty:hidden">
        {result && <ConvertDone result={result} />}
      </div>
      {error && <p className="m-0 text-sm text-bad">{errorText(error)}</p>}
      <Dialog
        open={confirmAi}
        onClose={() => setConfirmAi(false)}
        title="用 AI 校對這份試卷？"
        actions={
          <>
            <Button variant="ghost" onClick={() => setConfirmAi(false)}>
              取消
            </Button>
            <Button
              onClick={() => {
                setConfirmAi(false)
                withAi.mutation.mutate()
              }}
            >
              開始校對
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3 text-[15px]">
          <p className="m-0">
            程式先抽出題目，再讓系統內 AI（Haiku）對照每一頁的圖片修正底線、上下標和公式。共 {paper.pages} 頁，大約呼叫{' '}
            {paper.estimated_calls} 次、{usd(paper.estimated_calls * COST_PER_CALL)}，每頁 10～20 秒，會用到你的 Claude 額度。
          </p>
          <p className="m-0 text-sm text-muted">AI 也可能看錯；轉好之後仍要在對照預覽逐題確認。</p>
        </div>
      </Dialog>
    </li>
  )
}

function LectureRow({ lecture }: { lecture: PendingLecture }) {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(15)
  const [subject, setSubject] = useState('')
  const countId = useId()
  const subjectId = useId()
  const estimate = useQuery({
    queryKey: ['ingest', 'estimate', lecture.name],
    queryFn: () => api.get<{ calls: number }>(`/ingest/uploads/lectures/${encodeURIComponent(lecture.name)}/estimate`),
    enabled: open,
    staleTime: Infinity,
  })
  const generate = useAiRun((id) =>
    api.post<ConvertResult>(`/ingest/uploads/lectures/${encodeURIComponent(lecture.name)}/generate`, {
      count,
      subject: subject.trim() || null,
      request_id: id,
    }),
  )
  const calls = estimate.data?.calls

  return (
    <li className="flex flex-col gap-2 border-t border-rule py-4 first:border-t-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="font-medium text-ink">
          {lecture.name}
          <span className="ml-2 text-xs font-normal text-muted">教材・{fileSize(lecture.size_bytes)}</span>
        </span>
        {lecture.converted && <span className="text-xs text-ok">出過題了，再出會覆蓋</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => setOpen(true)} disabled={generate.mutation.isPending}>
          <Icon name="spark" size={16} />
          {generate.mutation.isPending ? 'AI 出題中…' : 'AI 出題'}
        </Button>
        {generate.mutation.isPending && (
          <Button size="sm" variant="danger" onClick={generate.stop}>
            <Icon name="stop" size={16} />
            中斷
          </Button>
        )}
      </div>
      <div aria-live="polite" className="empty:hidden">
        {generate.mutation.data && <ConvertDone result={generate.mutation.data} />}
      </div>
      {generate.mutation.error && <p className="m-0 text-sm text-bad">{errorText(generate.mutation.error)}</p>}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="讓 AI 依教材出題"
        actions={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button
              disabled={!calls}
              onClick={() => {
                setOpen(false)
                generate.mutation.mutate()
              }}
            >
              開始出題
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4 text-[15px]">
          <div className="grid gap-3 sm:grid-cols-[120px_minmax(0,1fr)]">
            <div className="flex flex-col gap-1.5">
              <label htmlFor={countId} className="text-xs text-muted">
                題數
              </label>
              <input
                id={countId}
                name="count"
                type="number"
                min={1}
                max={60}
                value={count}
                onChange={(event) => setCount(Math.min(60, Math.max(1, Number(event.target.value) || 1)))}
                className="tabular h-11 rounded-md border border-line bg-sheet px-3 text-ink outline-none focus:border-ink"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={subjectId} className="text-xs text-muted">
                科目名稱（題庫裡顯示的名稱，可留空用檔名）
              </label>
              <input
                id={subjectId}
                name="subject"
                autoComplete="off"
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                placeholder="例如：程式設計-JAVA…"
                className="h-11 rounded-md border border-line bg-sheet px-3 text-ink outline-none focus:border-ink"
              />
            </div>
          </div>
          <p className="m-0" aria-live="polite">
            {estimate.isPending
              ? '正在讀教材、估算用量…'
              : estimate.isError
                ? errorText(estimate.error)
                : `教材分成 ${calls} 段送給系統內 AI（Haiku），大約呼叫 ${calls} 次、${usd((calls ?? 0) * COST_PER_CALL)}，每次 10～30 秒，會用到你的 Claude 額度。`}
          </p>
          <p className="m-0 text-sm text-muted">每題都會附詳解和出處（第幾張投影片／第幾頁）；出好後到對照預覽逐題確認答案再匯入。</p>
        </div>
      </Dialog>
    </li>
  )
}
