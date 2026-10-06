/**
 * 題目的收藏（星號）與個人筆記。筆記像貼在題目旁的便條紙，離開輸入框時自動儲存。
 * 列表頁可以先用 lib/notes 的 prefetchNotes 一次取多題，避免每題各發一次請求。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Icon } from '@/components/Icon'
import { api } from '@/lib/api'
import { cx } from '@/lib/cx'
import { type Note, noteKey } from '@/lib/notes'

export function NoteControls({ questionId, className }: { questionId: number; className?: string }) {
  const queryClient = useQueryClient()
  const note = useQuery({
    queryKey: noteKey(questionId),
    queryFn: () => api.get<Note>(`/notes/questions/${questionId}`),
    staleTime: Infinity,
  })
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const save = useMutation({
    mutationFn: (data: { starred: boolean; note: string | null }) => api.put<Note>(`/notes/questions/${questionId}`, data),
    onSuccess: (saved) => {
      queryClient.setQueryData(noteKey(questionId), saved)
      queryClient.invalidateQueries({ queryKey: ['notes', 'list'] })
    },
  })

  const current = note.data
  const starred = current?.starred ?? false
  const text = current?.note ?? null

  const commit = () => {
    setEditing(false)
    const next = draft.trim() || null
    if (next !== text) save.mutate({ starred, note: next })
  }

  return (
    <div className={cx('flex flex-col gap-2', className)}>
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-pressed={starred}
          onClick={() => save.mutate({ starred: !starred, note: text })}
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
        <button
          type="button"
          onClick={() => {
            setDraft(text ?? '')
            setEditing(true)
          }}
          className="inline-flex h-8 items-center gap-1 rounded-md px-2 text-xs text-muted transition-colors hover:bg-sheet-tint hover:text-ink"
        >
          <Icon name="note" size={16} />
          {text ? '編輯筆記' : '寫筆記'}
        </button>
      </div>

      {editing ? (
        <textarea
          autoFocus
          rows={3}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setEditing(false)
          }}
          maxLength={5000}
          placeholder="寫下自己的理解、容易錯的地方…（離開輸入框自動儲存）"
          aria-label="題目筆記"
          className="w-full rounded-md border border-line bg-hl-soft px-3 py-2 font-hand text-[15px] leading-relaxed text-ink outline-none focus:border-accent"
        />
      ) : (
        text && (
          <button
            type="button"
            onClick={() => {
              setDraft(text)
              setEditing(true)
            }}
            className="w-full -rotate-[0.4deg] rounded-md bg-hl-soft px-3 py-2 text-left font-hand text-[15px] leading-relaxed whitespace-pre-wrap text-ink shadow-[0_1px_0_rgb(0_0_0/0.06)] transition-transform hover:rotate-0"
          >
            {text}
          </button>
        )
      )}
    </div>
  )
}
