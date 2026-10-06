/**
 * AI 助教：題目揭曉答案後才出現。第一次點會請 AI 依官方答案解釋（約 10 秒），
 * 之後同一題直接讀資料庫，不再花用量。可以追問、回報解釋有誤、重新產生。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Button } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { RichText } from '@/components/RichText'
import { api, ApiError } from '@/lib/api'
import { cx } from '@/lib/cx'
import type { components } from '@/lib/api-types'

type Thread = components['schemas']['TutorThread']
type AiStatus = components['schemas']['AiStatus']

const fetchThread = (id: number) => api.get<Thread>(`/tutor/questions/${id}`)
const fetchStatus = () => api.get<AiStatus>('/ai/status')

function errorText(error: unknown) {
  if (error instanceof ApiError && typeof error.detail === 'string') return error.detail
  return 'AI 暫時無法使用，請稍後再試。'
}

interface AiTutorProps {
  questionId: number
  /** 使用者的作答（原始選項字母），讓 AI 針對錯誤說明 */
  myAnswer?: string[] | null
  className?: string
}

export function AiTutor({ questionId, myAnswer, className }: AiTutorProps) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const key = ['tutor', questionId]
  const thread = useQuery({ queryKey: key, queryFn: () => fetchThread(questionId), enabled: open })
  const status = useQuery({ queryKey: ['ai', 'status'], queryFn: fetchStatus, enabled: open })

  const onThread = (data: Thread) => {
    queryClient.setQueryData(key, data)
    queryClient.invalidateQueries({ queryKey: ['ai', 'status'] })
  }
  const explain = useMutation({
    mutationFn: (regenerate: boolean) =>
      api.post<Thread>(`/tutor/questions/${questionId}/explain`, { regenerate, my_answer: myAnswer ?? null }),
    onSuccess: onThread,
  })
  const ask = useMutation({
    mutationFn: (content: string) => api.post<Thread>(`/tutor/questions/${questionId}/messages`, { content }),
    onSuccess: (data) => {
      onThread(data)
      setDraft('')
    },
  })
  const flag = useMutation({
    mutationFn: (messageId: number) => api.post<Thread>(`/tutor/messages/${messageId}/flag`),
    onSuccess: onThread,
  })

  const messages = thread.data?.messages ?? []
  const hasExplanation = messages.some((message) => message.kind === 'explanation')
  const busy = explain.isPending || ask.isPending
  const error = explain.error ?? ask.error

  const start = () => {
    setOpen(true)
    if (!thread.data) {
      fetchThread(questionId).then((data) => {
        queryClient.setQueryData(key, data)
        if (!data.messages.some((message) => message.kind === 'explanation')) explain.mutate(false)
      })
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (draft.trim() && !busy) ask.mutate(draft.trim())
  }

  if (!open) {
    return (
      <div className={className}>
        <Button variant="secondary" size="sm" onClick={start}>
          <Icon name="spark" size={17} />
          問 AI 助教
        </Button>
      </div>
    )
  }

  return (
    <section
      aria-label="AI 助教"
      className={cx('flex flex-col gap-4 rounded-md border border-print-rule bg-sheet-tint px-4 py-4 sm:px-5', className)}
    >
      <header className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5 text-sm font-medium text-print">
          <Icon name="spark" size={17} />
          AI 助教
          <span className="font-normal text-muted">・僅供參考，以官方答案為準</span>
        </span>
        <button type="button" onClick={() => setOpen(false)} className="text-xs text-muted hover:text-ink">
          收合
        </button>
      </header>

      {messages.length === 0 && busy && (
        <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
          <span className="h-3 w-2 animate-pulse rounded-full border border-print" />
          AI 正在看這一題，大約 10 秒…
        </p>
      )}

      <ol className="m-0 flex list-none flex-col gap-4 p-0">
        {messages.map((message) =>
          message.role === 'user' ? (
            <li key={message.id} className="self-end rounded-md bg-ink px-3 py-2 text-sm text-paper sm:max-w-[80%]">
              {message.content}
            </li>
          ) : (
            <li key={message.id} className="flex flex-col gap-2 animate-[rise-in_var(--dur)_var(--ease-out)]">
              <RichText className="text-[15px]">{message.content}</RichText>
              <div className="flex flex-wrap gap-3 text-xs text-muted">
                {message.flagged ? (
                  <span className="text-bad">已回報有誤</span>
                ) : (
                  <button type="button" className="hover:text-bad" onClick={() => flag.mutate(message.id)}>
                    這段解釋有誤
                  </button>
                )}
                {message.kind === 'explanation' && (
                  <button type="button" className="hover:text-ink" onClick={() => explain.mutate(true)} disabled={busy}>
                    重新產生
                  </button>
                )}
              </div>
            </li>
          ),
        )}
      </ol>

      {busy && messages.length > 0 && (
        <p className="m-0 text-sm text-muted" role="status">
          AI 回覆中…
        </p>
      )}
      {error && (
        <p className="m-0 text-sm text-bad" role="alert">
          {errorText(error)}
          {!hasExplanation && (
            <button type="button" className="ml-2 underline" onClick={() => explain.mutate(false)}>
              再試一次
            </button>
          )}
        </p>
      )}

      {hasExplanation && (thread.data?.remaining_questions ?? 0) > 0 && (
        <form onSubmit={submit} className="flex gap-2">
          <label htmlFor={`ask-${questionId}`} className="sr-only">
            追問 AI 助教
          </label>
          <input
            id={`ask-${questionId}`}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={500}
            placeholder="還有哪裡不懂？例如：為什麼 (B) 不對？"
            className="h-10 min-w-0 flex-1 rounded-md border border-line bg-sheet px-3 text-sm text-ink outline-none focus:border-ink"
          />
          <Button type="submit" size="sm" disabled={!draft.trim() || busy} aria-label="送出">
            <Icon name="send" size={16} />
          </Button>
        </form>
      )}

      {status.data && (
        <p className="m-0 text-[11px] text-muted">
          {hasExplanation && `還可以追問 ${thread.data?.remaining_questions ?? 0} 次・`}
          本月 AI 用量 ${status.data.month_cost_usd.toFixed(2)}／${status.data.month_budget_usd.toFixed(0)}（{status.data.model}）
        </p>
      )}
    </section>
  )
}
