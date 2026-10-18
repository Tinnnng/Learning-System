/**
 * 申論題作答與自評：
 * 1. 打字作答，停止輸入約 1 秒或離開輸入框自動儲存。
 * 2. 練習模式按「寫好了，看參考答案」；模擬考交卷後才揭曉。
 * 3. 對照參考答案勾選寫到的得分要點，加總成分數；可以先「請 AI 評分」，AI 會建議勾哪些並給評語，確認後才算分。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { EssayReference } from '@/components/EssayReference'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'
import { api } from '@/lib/api'
import { cx } from '@/lib/cx'
import { score as formatScore } from '@/lib/format'
import type { ItemOut } from '@/lib/types'
import { fetchRules } from './api'
import { essayDraftFlushers as flushers } from './essayDrafts'

const SAVE_DELAY_MS = 1000

interface EssayAnswerProps {
  item: ItemOut
  sessionId: number
  practice: boolean
  submitted: boolean
  onUpdate: (item: ItemOut) => void
}

export function EssayAnswer({ item, sessionId, practice, submitted, onUpdate }: EssayAnswerProps) {
  const revealed = item.revealed || submitted
  return revealed ? (
    <EssayGrading item={item} sessionId={sessionId} onUpdate={onUpdate} />
  ) : (
    <EssayEditor item={item} sessionId={sessionId} practice={practice} onUpdate={onUpdate} />
  )
}

function EssayEditor({ item, sessionId, practice, onUpdate }: Omit<EssayAnswerProps, 'submitted'>) {
  const fieldId = useId()
  const [draft, setDraft] = useState(item.text ?? '')
  const base = `/exam/sessions/${sessionId}/items/${item.position}`
  const inflight = useRef<Promise<unknown> | null>(null)
  const save = useMutation({
    mutationFn: (text: string) => {
      const request = api.put<ItemOut>(base, { text })
      inflight.current = request
      return request
    },
    onSuccess: onUpdate,
  })

  // 最新的草稿與已存的內容：給交卷前、卸載時的補存用（effect 裡讀，不受 render 時機影響）
  const draftRef = useRef(draft)
  const savedRef = useRef(item.text ?? '')
  useEffect(() => {
    draftRef.current = draft
    savedRef.current = item.text ?? ''
  })
  const flush = useCallback(async () => {
    await inflight.current?.catch(() => undefined)
    const text = draftRef.current
    if (text.trim() === savedRef.current) return
    const updated = await api.put<ItemOut>(base, { text })
    savedRef.current = updated.text ?? ''
    onUpdate(updated)
  }, [base, onUpdate])
  useEffect(() => {
    const key = `${sessionId}-${item.position}`
    flushers.set(key, flush)
    return () => {
      flushers.delete(key)
      void flush().catch(() => undefined)
    }
  }, [flush, item.position, sessionId])
  const reveal = useMutation({
    mutationFn: async () => {
      if (draft.trim() !== (item.text ?? '')) onUpdate(await api.put<ItemOut>(base, { text: draft }))
      return api.post<ItemOut>(`${base}/reveal`)
    },
    onSuccess: onUpdate,
  })
  const dirty = draft.trim() !== (item.text ?? '')

  useEffect(() => {
    if (!dirty || save.isPending) return
    const timer = window.setTimeout(() => save.mutate(draft), SAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  })

  const length = draft.replace(/\s/g, '').length
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={fieldId} className="text-sm text-muted">
          作答（{formatScore(item.points)} 分）
        </label>
        <span className="text-xs text-muted">
          {/* 只念「儲存中／已儲存」；字數放在朗讀區外，不然每打一個字就念一次 */}
          <span role="status">{save.isPending ? '儲存中…' : dirty ? '' : item.text ? '已儲存' : ''}</span>
          <span className="tabular ml-3">{length} 字</span>
        </span>
      </div>
      <textarea
        id={fieldId}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => dirty && !save.isPending && save.mutate(draft)}
        maxLength={20000}
        placeholder="在這裡寫你的答案，和正式考試一樣分點、分段寫清楚…"
        className="min-h-56 w-full resize-y rounded-md border border-line bg-sheet px-4 py-3 text-[16px] leading-[1.9] text-ink outline-none transition-colors duration-[var(--dur)] [field-sizing:content] focus:border-accent"
      />
      {save.isError && <ErrorState error={save.error} />}
      {practice ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => reveal.mutate()} disabled={reveal.isPending}>
            <Icon name="check" size={17} />
            {draft.trim() ? '寫好了，看參考答案' : '不寫了，直接看參考答案'}
          </Button>
          <span className="text-xs text-muted">看參考答案後就不能再改答案。</span>
        </div>
      ) : (
        <p className="m-0 text-xs text-muted">交卷後可以看參考答案，勾選寫到的得分要點自評。</p>
      )}
      {reveal.isError && <ErrorState error={reveal.error} />}
    </div>
  )
}

const percentLabel = (ratio: number) => `${Math.round(ratio * 100)}%`

function EssayGrading({ item, sessionId, onUpdate }: Omit<EssayAnswerProps, 'practice' | 'submitted'>) {
  const queryClient = useQueryClient()
  const rules = useQuery({ queryKey: ['review', 'rules'], queryFn: fetchRules, staleTime: Infinity }).data
  const passRatio = rules?.essay_pass_ratio ?? 0.8
  const wrongRatio = rules?.essay_wrong_ratio ?? 0.6
  const rubric = item.rubric ?? []
  const [hits, setHits] = useState<number[]>(() => item.rubric_hits ?? item.ai_hits ?? [])
  const [editing, setEditing] = useState(!item.graded)
  const base = `/exam/sessions/${sessionId}/items/${item.position}`

  const grade = useMutation({
    mutationFn: () => api.post<ItemOut>(`${base}/grade`, { hits }),
    onSuccess: (updated) => {
      onUpdate(updated)
      setEditing(false)
      // 總分與錯題本都變了
      queryClient.invalidateQueries({ queryKey: ['exam', 'session', sessionId] })
      queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
  const aiGrade = useMutation({
    mutationFn: () => api.post<ItemOut>(`${base}/ai-grade`),
    onSuccess: (updated) => {
      onUpdate(updated)
      setHits(updated.ai_hits ?? [])
      queryClient.invalidateQueries({ queryKey: ['ai', 'status'] })
    },
  })

  // 只顯示最近一次動作的錯誤：AI 評分失敗後改手動評分成功，舊的錯誤不該留著
  const lastAction = (grade.submittedAt ?? 0) >= (aiGrade.submittedAt ?? 0) ? grade : aiGrade
  const total = rubric.reduce((sum, point, index) => sum + (hits.includes(index) ? point.points : 0), 0)
  const toggle = (index: number) =>
    setHits((old) => (old.includes(index) ? old.filter((value) => value !== index) : [...old, index].sort((a, b) => a - b)))
  const ratio = item.score !== null && item.score !== undefined && item.points ? item.score / item.points : null

  return (
    <div className="flex flex-col gap-5">
      <section aria-label="我的答案" className="flex flex-col gap-2">
        <h3 className="m-0 text-sm font-normal text-muted">我的答案</h3>
        {item.text ? (
          <p className="m-0 rounded-md border border-rule bg-sheet-tint px-4 py-3 text-[15px] leading-[1.9] whitespace-pre-wrap text-ink">
            {item.text}
          </p>
        ) : (
          <p className="m-0 text-sm text-muted">沒有作答{item.graded && '，計 0 分'}。</p>
        )}
      </section>

      <EssayReference explanation={item.explanation} rubric={[]} open />

      {rubric.length > 0 && (
        <section aria-label="自評" className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h3 className="m-0 font-hand text-lg font-bold">
              {editing ? '勾選你寫到的得分要點' : '得分要點'}
            </h3>
            {item.graded && ratio !== null && !editing && (
              <span
                className={cx(
                  'marker font-hand text-2xl font-bold text-ink [--marker-scale:1]',
                  ratio >= passRatio
                    ? '[--marker-color:var(--ok-hl)]'
                    : ratio < wrongRatio && item.text
                      ? '[--marker-color:var(--bad-hl)]'
                      : '[--marker-color:var(--hl)]',
                )}
              >
                {formatScore(item.score ?? 0)}／{formatScore(item.points)} 分
              </span>
            )}
          </div>

          <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
            {rubric.map((point, index) => {
              const checked = hits.includes(index)
              const suggested = (item.ai_hits ?? []).includes(index)
              return (
                <li key={index}>
                  <label
                    className={cx(
                      'flex min-h-11 items-start gap-3 rounded-md px-3 py-2.5 transition-colors duration-[var(--dur)]',
                      editing ? 'cursor-pointer hover:bg-sheet-tint' : 'cursor-default',
                      checked && 'bg-ok-soft/60',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={!editing}
                      onChange={() => toggle(index)}
                      className="mt-1 h-4 w-4 flex-none accent-[var(--ok)]"
                    />
                    <span className="flex-1 text-[15px] text-ink">
                      {point.text}
                      {suggested && item.ai_feedback !== null && (
                        <span className="ml-2 rounded-sm bg-accent-faint px-1.5 py-0.5 text-[11px] text-accent">AI 認為有寫到</span>
                      )}
                    </span>
                    <span className="tabular flex-none text-sm text-muted">{formatScore(point.points)} 分</span>
                  </label>
                </li>
              )
            })}
          </ul>

          {item.ai_feedback && (
            <div className="flex gap-2 rounded-md bg-sheet-tint px-4 py-3 text-[15px]">
              <Icon name="spark" size={17} className="mt-1 flex-none text-accent" />
              <p className="m-0 leading-relaxed">
                <span className="text-sm text-accent">AI 評語：</span>
                {item.ai_feedback}
              </p>
            </div>
          )}

          {editing ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => grade.mutate()} disabled={grade.isPending}>
                確定得分 {formatScore(total)}／{formatScore(item.points)}
              </Button>
              {item.text && (
                <Button variant="secondary" onClick={() => aiGrade.mutate()} disabled={aiGrade.isPending}>
                  <Icon name="spark" size={16} />
                  {aiGrade.isPending ? 'AI 評分中…' : item.ai_feedback ? '請 AI 再評一次' : '請 AI 評分'}
                </Button>
              )}
              {item.graded && (
                <button
                  type="button"
                  onClick={() => {
                    // 取消修改：勾選回到上次確定的得分要點
                    setHits(item.rubric_hits ?? [])
                    setEditing(false)
                    grade.reset()
                  }}
                  className="h-11 text-sm text-muted hover:text-ink"
                >
                  取消
                </button>
              )}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
              <span>
                {!item.text
                  ? '沒有作答，不收進錯題本。'
                  : ratio !== null && ratio < wrongRatio
                    ? `低於 ${percentLabel(wrongRatio)}，已收進錯題本。`
                    : ratio !== null && ratio >= passRatio
                      ? `達 ${percentLabel(passRatio)} 以上，答得好！`
                      : `及格但未達 ${percentLabel(passRatio)}。`}
              </span>
              {item.text && (
                <button type="button" onClick={() => setEditing(true)} className="h-11 text-accent hover:underline">
                  修改自評
                </button>
              )}
            </div>
          )}
          {editing && item.text && !item.ai_feedback && (
            <p className="m-0 text-xs text-muted">AI 會依得分要點建議要勾哪些並給評語（約 10 秒），你確認後才算分。</p>
          )}
          {lastAction.isError && <ErrorState error={lastAction.error} />}
        </section>
      )}
    </div>
  )
}
