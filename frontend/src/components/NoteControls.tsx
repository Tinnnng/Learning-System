/**
 * 題目的收藏（星號）與個人筆記。每題底下都有一塊筆記區，直接寫就好：
 * 停止輸入約 1 秒或離開輸入框就自動儲存。
 * 列表頁可以先用 lib/notes 的 prefetchNotes 一次取多題，避免每題各發一次請求。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { Icon } from '@/components/Icon'
import { api } from '@/lib/api'
import { cx } from '@/lib/cx'
import { type Note, noteKey } from '@/lib/notes'

const SAVE_DELAY_MS = 1000

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
  const save = useMutation({
    mutationFn: (data: { starred: boolean; note: string | null }) => api.put<Note>(`/notes/questions/${questionId}`, data),
    onSuccess: (saved) => {
      queryClient.setQueryData(noteKey(questionId), saved)
      queryClient.invalidateQueries({ queryKey: ['notes', 'list'] })
    },
  })

  const starred = note.data?.starred ?? false
  const text = note.data?.note ?? null
  const value = draft ?? text ?? ''
  const dirty = draft !== null && (draft.trim() || null) !== text

  const commit = () => {
    if (dirty && !save.isPending) save.mutate({ starred, note: draft?.trim() || null })
  }

  useEffect(() => {
    if (!dirty) return
    const timer = window.setTimeout(commit, SAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  })

  const status = save.isPending
    ? '儲存中…'
    : save.isError
      ? '沒有存到，請稍後再試（離開輸入框會再存一次）'
      : dirty
        ? ''
        : save.isSuccess && draft !== null
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
          // 前一次儲存還沒回來時先不送：星號狀態以伺服器回傳為準，連點才不會送出相反的狀態
          aria-disabled={save.isPending || undefined}
          onClick={() => {
            if (!save.isPending) save.mutate({ starred: !starred, note: draft !== null ? draft.trim() || null : text })
          }}
          className={cx(
            'inline-flex h-8 items-center gap-1 rounded-md px-2 text-xs transition-colors',
            starred ? 'text-ink' : 'text-muted hover:bg-sheet-tint hover:text-ink',
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
      </div>
      <textarea
        id={fieldId}
        rows={1}
        value={value}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        maxLength={5000}
        disabled={note.isPending}
        placeholder="在這裡寫筆記：自己的理解、容易錯的地方…"
        className={cx(
          'ml-2 min-h-11 w-[calc(100%-0.5rem)] resize-none rounded-md border border-dashed px-3 py-2 font-display text-[15px] leading-relaxed text-ink',
          'outline-none transition-colors duration-[var(--dur)] [field-sizing:content] placeholder:text-muted',
          value ? 'border-transparent bg-sheet-tint' : 'border-line bg-transparent hover:border-rule',
          'focus:border-accent focus:bg-sheet-tint',
        )}
      />
    </div>
  )
}
