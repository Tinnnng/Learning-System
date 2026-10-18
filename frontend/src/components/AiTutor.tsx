/**
 * AI 助教：題目揭曉答案後才出現。打開後由使用者決定要不要請 AI 詳解（約 10 秒），
 * 也可以不看詳解直接發問。詳解存在資料庫，同一題再看不花用量。可以追問、回報解釋有誤、重新產生。
 * 追問不限次數，但會顯示這題與本月已用的額度；送出後可以按「中斷」（終止 AI，避免誤按浪費用量）。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { RichText } from '@/components/RichText'
import { api, ApiError, apiRequest } from '@/lib/api'
import { cx } from '@/lib/cx'
import { usd } from '@/lib/format'
import type { components } from '@/lib/api-types'

type Thread = components['schemas']['TutorThread']
type AiStatus = components['schemas']['AiStatus']

const fetchThread = (id: number) => api.get<Thread>(`/tutor/questions/${id}`)
const fetchStatus = () => api.get<AiStatus>('/ai/status')

function isCancelled(error: unknown) {
  return (error instanceof DOMException && error.name === 'AbortError') || (error instanceof ApiError && error.status === 409)
}

function errorText(error: unknown) {
  if (isCancelled(error)) return '已中斷，這次沒有產生內容。'
  if (error instanceof ApiError && typeof error.detail === 'string') return error.detail
  return 'AI 暫時無法使用，請稍後再試。'
}

// 手機用 dev:lan（http）連線時不是安全環境，沒有 crypto.randomUUID
const requestId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`


interface Running {
  id: string
  controller: AbortController
}

interface AiTutorProps {
  questionId: number
  /** 使用者的作答（原始選項字母），追問時讓 AI 針對錯誤說明 */
  myAnswer?: string[] | null
  className?: string
}

export function AiTutor({ questionId, myAnswer, className }: AiTutorProps) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  // 打開後焦點移進助教區塊、收合後回到「AI 助教」按鈕（只在使用者按了之後移，第一次顯示不搶焦點）
  const toggled = useRef(false)
  const sectionRef = useRef<HTMLElement>(null)
  const openRef = useRef<HTMLButtonElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const toggle = (next: boolean) => {
    toggled.current = true
    setOpen(next)
  }
  useEffect(() => {
    if (!toggled.current) return
    if (open) sectionRef.current?.focus({ preventScroll: true })
    else openRef.current?.focus()
  }, [open])
  const [draft, setDraft] = useState('')
  // AI 回覆後念出來（「AI 回覆中…」消失後螢幕閱讀器原本不會知道有新內容）
  const [announcement, setAnnouncement] = useState('')
  const announceReply = (data: Thread) => {
    const reply = [...data.messages].reverse().find((message) => message.role === 'assistant')
    if (reply) setAnnouncement(`AI 已回覆：${reply.content.slice(0, 120)}`)
  }
  const key = ['tutor', questionId]
  const running = useRef<Running | null>(null)
  const thread = useQuery({ queryKey: key, queryFn: () => fetchThread(questionId), enabled: open })
  const status = useQuery({ queryKey: ['ai', 'status'], queryFn: fetchStatus, enabled: open })

  const onThread = (data: Thread) => {
    queryClient.setQueryData(key, data)
    queryClient.invalidateQueries({ queryKey: ['ai', 'status'] })
  }

  /** 送出會花用量的請求：附上 request_id，之後可以中斷 */
  const send = (path: string, body: Record<string, unknown>) => {
    const current = { id: requestId(), controller: new AbortController() }
    running.current = current
    return apiRequest<Thread>(path, {
      method: 'POST',
      body: JSON.stringify({ ...body, request_id: current.id }),
      signal: current.controller.signal,
    }).finally(() => {
      if (running.current === current) running.current = null
    })
  }
  const stop = () => {
    const current = running.current
    if (!current) return
    // 先請後端終止 AI 程序（不再花用量），再放棄等待回應
    void api.post(`/ai/requests/${current.id}/cancel`).catch(() => undefined)
    current.controller.abort()
  }

  // 詳解是這題共用的（題庫、錯題本都看同一份），不帶個人作答；個人作答只放在追問
  // 兩個動作的錯誤只留最近一次：開始其中一個就清掉另一個的錯誤，避免成功後還掛著舊的「已中斷」或逾時訊息
  const explain = useMutation({
    mutationFn: (regenerate: boolean) => send(`/tutor/questions/${questionId}/explain`, { regenerate }),
    onMutate: (): void => ask.reset(),
    onSuccess: (data) => {
      onThread(data)
      announceReply(data)
    },
  })
  const ask = useMutation({
    mutationFn: (content: string) =>
      send(`/tutor/questions/${questionId}/messages`, { content, my_answer: myAnswer ?? null }),
    onMutate: (): void => explain.reset(),
    onSuccess: (data) => {
      onThread(data)
      announceReply(data)
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
  const cancelled = isCancelled(error)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (draft.trim() && !busy) ask.mutate(draft.trim())
  }

  if (!open) {
    return (
      <div className={className}>
        <Button ref={openRef} variant="secondary" size="sm" onClick={() => toggle(true)}>
          <Icon name="spark" size={17} />
          AI 助教
        </Button>
      </div>
    )
  }

  return (
    <section
      ref={sectionRef}
      tabIndex={-1}
      aria-label="AI 助教"
      className={cx('flex flex-col gap-4 rounded-md border border-rule bg-sheet-tint px-4 py-4 outline-none sm:px-5', className)}
    >
      <header className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5 text-sm font-medium text-accent">
          <Icon name="spark" size={17} />
          AI 助教
          <span className="font-normal text-muted">・僅供參考，以官方答案為準</span>
        </span>
        <button type="button" ref={closeRef} onClick={() => toggle(false)} className="hit text-xs text-muted hover:text-ink">
          收合
        </button>
      </header>

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
      {thread.isPending && <p className="m-0 text-sm text-muted">載入中…</p>}
      {thread.isError && <p className="m-0 text-sm text-bad">{errorText(thread.error)}</p>}

      {thread.data && !hasExplanation && !explain.isPending && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <Button size="sm" onClick={() => explain.mutate(false)} disabled={busy}>
            <Icon name="spark" size={16} />
            請 AI 詳解這題
          </Button>
          <span className="text-xs text-muted">約 10 秒；只想問某個地方，也可以直接在下面發問。</span>
        </div>
      )}

      {explain.isPending && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
            <span className="h-3 w-2 animate-pulse rounded-full border border-accent" />
            {hasExplanation ? 'AI 重新產生中…' : 'AI 正在看這一題，大約 10 秒…'}
          </p>
          <StopButton onClick={stop} />
        </div>
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
                  <button type="button" className="hit hover:text-bad" onClick={() => flag.mutate(message.id)}>
                    這段解釋有誤
                  </button>
                )}
                {message.kind === 'explanation' && (
                  <button type="button" className="hit hover:text-ink" onClick={() => explain.mutate(true)} disabled={busy}>
                    重新產生
                  </button>
                )}
              </div>
            </li>
          ),
        )}
      </ol>

      {ask.isPending && (
        <p className="m-0 text-sm text-muted" role="status">
          AI 回覆中…
        </p>
      )}
      {error && !busy && (
        <p className={cx('m-0 text-sm', cancelled ? 'text-muted' : 'text-bad')} role={cancelled ? 'status' : 'alert'}>
          {errorText(error)}
          {explain.isError && !hasExplanation && !cancelled && (
            <button type="button" className="hit ml-2 underline" onClick={() => explain.mutate(false)}>
              再試一次
            </button>
          )}
        </p>
      )}

      {thread.data && (
        <form onSubmit={submit} className="flex gap-2">
          <label htmlFor={`ask-${questionId}`} className="sr-only">
            追問 AI 助教
          </label>
          <input
            id={`ask-${questionId}`}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={500}
            placeholder={hasExplanation ? '還有哪裡不懂？例如：為什麼 (B) 不對？' : '直接問，例如：為什麼 (B) 不對？'}
            className="h-10 min-w-0 flex-1 rounded-md border border-line bg-sheet px-3 text-sm text-ink outline-none focus:border-ink"
          />
          {ask.isPending ? (
            <StopButton onClick={stop} />
          ) : (
            <Button type="submit" size="sm" disabled={!draft.trim() || busy} aria-label="送出">
              <Icon name="send" size={16} />
            </Button>
          )}
        </form>
      )}

      {status.data && (
        <p className="m-0 text-[11px] text-muted">
          {thread.data && `這題已用 ${usd(thread.data.cost_usd)}・`}
          本月已用 {usd(status.data.month_cost_usd)}（{status.data.month_calls} 次，{status.data.model}）
        </p>
      )}
    </section>
  )
}

function StopButton({ onClick }: { onClick: () => void }) {
  return (
    <Button type="button" variant="danger" size="sm" onClick={onClick}>
      <Icon name="stop" size={16} />
      中斷
    </Button>
  )
}
