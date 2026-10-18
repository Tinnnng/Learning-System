/**
 * 題目的收藏（星號）與個人筆記。每題底下都有一塊筆記區，直接寫就好：
 * 停止輸入約 1 秒或離開輸入框就自動儲存；換題、收合等讓這塊消失時，還沒存的也會補存。
 * 列表頁可以先用 lib/notes 的 prefetchNotes 一次取多題，避免每題各發一次請求。
 */

import { type QueryClient, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { Icon } from '@/components/Icon'
import { api } from '@/lib/api'
import { cx } from '@/lib/cx'
import { type Note, noteKey } from '@/lib/notes'

const SAVE_DELAY_MS = 1000

/** 只送要改的欄位：按星號不帶筆記、存筆記不帶星號，後端只更新有送的那個 */
type NotePatch = { starred?: boolean; note?: string | null }

// 同一題的儲存排隊依序送出：先送的先寫進資料庫，後送的才不會被先送、晚到的蓋回去。
// 放在模組層級：元件卸載（換題、收合）後還在排隊的照樣送完，重新掛載的元件也接在同一條隊伍後面
const queues = new Map<number, Promise<unknown>>()

function enqueueSave(queryClient: QueryClient, questionId: number, patch: NotePatch) {
  // 先把要存的內容放進快取：畫面馬上反映，下一個動作（連點星號、補打字）也以這個為準
  queryClient.setQueryData<Note>(noteKey(questionId), (old) =>
    old ? { ...old, ...patch } : { question_id: questionId, starred: false, note: null, updated_at: null, ...patch },
  )
  const previous = queues.get(questionId) ?? Promise.resolve()
  const request = previous.catch(() => undefined).then(() => api.put<Note>(`/notes/questions/${questionId}`, patch))
  queues.set(questionId, request)
  return request.then(
    (saved) => {
      const latest = queues.get(questionId) === request
      if (latest) {
        // 後面還有排隊的就不寫回：不然星號會在兩次回應之間閃回舊狀態
        queues.delete(questionId)
        queryClient.setQueryData(noteKey(questionId), saved)
      }
      queryClient.invalidateQueries({ queryKey: ['notes', 'list'] })
      queryClient.invalidateQueries({ queryKey: ['notes', 'batch'] })
      return saved
    },
    (error: unknown) => {
      if (queues.get(questionId) === request) queues.delete(questionId)
      // 沒存到：快取裡先放的內容不可信，重新讀資料庫
      queryClient.invalidateQueries({ queryKey: noteKey(questionId) })
      throw error
    },
  )
}

const normalize = (text: string | null | undefined) => text?.trim() || null

export function NoteControls({ questionId, className }: { questionId: number; className?: string }) {
  const queryClient = useQueryClient()
  const fieldId = useId()
  const note = useQuery({
    queryKey: noteKey(questionId),
    queryFn: () => api.get<Note>(`/notes/questions/${questionId}`),
    staleTime: Infinity,
  })
  // 使用者開始輸入前顯示資料庫的內容；輸入後以草稿為準，避免儲存回來時蓋掉正在打的字
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(0)
  const [failed, setFailed] = useState(false)
  const [saved, setSaved] = useState(false)
  const mounted = useRef(true)

  // 還沒讀到（或讀取失敗）就不能寫：不知道原本的筆記是什麼，存下去可能把它清掉
  const ready = note.isSuccess
  const starred = note.data?.starred ?? false
  const text = note.data?.note ?? null
  const value = draft ?? text ?? ''
  const dirty = ready && draft !== null && normalize(draft) !== text

  const persist = (patch: NotePatch) => {
    setSaving((count) => count + 1)
    setFailed(false)
    enqueueSave(queryClient, questionId, patch).then(
      () => mounted.current && setSaved(true),
      () => mounted.current && setFailed(true),
    ).finally(() => mounted.current && setSaving((count) => count - 1))
  }

  const commit = () => {
    if (dirty) persist({ note: normalize(draft) })
  }

  useEffect(() => {
    if (!dirty || failed) return
    const timer = window.setTimeout(commit, SAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  })

  // 卸載時（換題、收合、模擬考時間到自動交卷）把還沒存的草稿送出
  const pending = useRef<{ dirty: boolean; note: string | null }>({ dirty: false, note: null })
  useEffect(() => {
    pending.current = { dirty, note: normalize(draft) }
  })
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      if (pending.current.dirty) enqueueSave(queryClient, questionId, { note: pending.current.note }).catch(() => undefined)
    }
  }, [queryClient, questionId])

  const status = !ready
    ? note.isError
      ? '筆記讀取失敗'
      : ''
    : saving > 0
      ? '儲存中…'
      : failed
        ? '沒有存到，請稍後再試（離開輸入框會再存一次）'
        : dirty
          ? ''
          : saved && draft !== null
            ? '已儲存'
            : ''

  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-pressed={starred}
          // 名稱固定是「收藏」，狀態交給 aria-pressed；不然會念成「已收藏，切換按鈕，已按下」
          aria-label="收藏"
          // 筆記還沒讀到時不能按：送出去的資料要以資料庫現況為準
          disabled={!ready}
          // 只送星號：連點時依序排隊送出，每次都以畫面上（快取）的最新狀態反轉
          onClick={() => persist({ starred: !starred })}
          className={cx(
            'inline-flex h-8 items-center gap-1 rounded-md px-2 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-50',
            starred ? 'text-ink' : 'text-muted enabled:hover:bg-sheet-tint enabled:hover:text-ink',
          )}
        >
          <Icon
            name="star"
            size={16}
            filled={starred}
            className={cx('transition-transform duration-[var(--dur)]', starred ? 'scale-110 text-star' : '')}
          />
          {starred ? '已收藏' : '收藏'}
        </button>
        <label htmlFor={fieldId} className="inline-flex h-8 items-center gap-1 px-2 text-xs text-muted">
          <Icon name="note" size={16} />
          筆記
        </label>
        <span className="ml-auto text-[11px] text-muted" role="status" aria-live="polite">
          {status}
        </span>
        {note.isError && (
          <button
            type="button"
            onClick={() => note.refetch()}
            className="inline-flex h-8 items-center rounded-md px-2 text-[11px] text-accent hover:bg-sheet-tint"
          >
            重試
          </button>
        )}
      </div>
      <textarea
        id={fieldId}
        rows={1}
        value={value}
        onChange={(event) => {
          setDraft(event.target.value)
          setFailed(false)
        }}
        onBlur={commit}
        maxLength={5000}
        disabled={!ready}
        placeholder={note.isError ? '筆記讀取失敗，按「重試」再讀一次' : '在這裡寫筆記：自己的理解、容易錯的地方…'}
        className={cx(
          'ml-2 min-h-11 w-[calc(100%-0.5rem)] resize-none rounded-md border border-dashed px-3 py-2 font-display text-[15px] leading-relaxed text-ink',
          'outline-none transition-colors duration-[var(--dur)] [field-sizing:content] placeholder:text-muted disabled:cursor-not-allowed',
          value ? 'border-transparent bg-sheet-tint' : 'border-line bg-transparent hover:border-rule',
          'focus:border-accent focus:bg-sheet-tint',
        )}
      />
    </div>
  )
}
