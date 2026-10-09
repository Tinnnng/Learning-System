/** 編輯題目的對話框：驗證、儲存中狀態、錯誤訊息都在這裡處理，呼叫端只要提供 onSave。 */

import { useCallback, useId, useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { Dialog } from '@/components/Dialog'
import { QuestionEditor } from '@/components/QuestionEditor'
import { ApiError } from '@/lib/api'
import { findProblem, type QuestionDraft, type QuestionProblem } from '@/lib/questionEdit'

interface QuestionEditorDialogProps {
  title: string
  /** 開啟時的內容；null 表示關閉 */
  initial: QuestionDraft | null
  onClose: () => void
  onSave: (question: QuestionDraft) => Promise<unknown>
  /** 顯示在編輯器上方的提醒，例如「重新匯入官方試卷時會被覆蓋」 */
  note?: string
}

const DISCARD_MESSAGE = '這題有還沒儲存的修改，確定要關閉嗎？'

export function QuestionEditorDialog({ title, initial, onClose, onSave, note }: QuestionEditorDialogProps) {
  // 內層回報有沒有改過；關閉（Esc、點背景、取消）前有修改就先確認
  const dirty = useRef(false)
  const confirmClose = useCallback(() => !dirty.current || window.confirm(DISCARD_MESSAGE), [])
  const close = () => {
    dirty.current = false
    onClose()
  }
  // 以 key 重新掛載內層，開啟不同題目時編輯狀態會重設
  return (
    <Dialog open={initial !== null} onClose={close} confirmClose={confirmClose} title={title} wide>
      {initial && (
        <EditorBody
          key={JSON.stringify(initial)}
          initial={initial}
          onClose={close}
          onCancel={() => confirmClose() && close()}
          onDirty={(value) => (dirty.current = value)}
          onSave={onSave}
          note={note}
        />
      )}
    </Dialog>
  )
}

function EditorBody({
  initial,
  onClose,
  onCancel,
  onDirty,
  onSave,
  note,
}: Omit<QuestionEditorDialogProps, 'title' | 'initial'> & {
  initial: QuestionDraft
  onCancel: () => void
  onDirty: (dirty: boolean) => void
}) {
  const [value, setValue] = useState(initial)
  const [problem, setProblem] = useState<QuestionProblem | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const errorId = useId()
  const bodyRef = useRef<HTMLDivElement>(null)

  const change = (next: QuestionDraft) => {
    setValue(next)
    onDirty(JSON.stringify(next) !== JSON.stringify(initial))
    // 改到出錯的地方後重新檢查，修好了就拿掉錯誤標記
    if (problem) setProblem(findProblem(next))
  }

  const save = async () => {
    const found = findProblem(value)
    if (found) {
      setProblem(found)
      setError(null)
      // 焦點移到出錯的欄位（標了 aria-invalid 的那一個；沒有就移到同類欄位的第一個）
      window.setTimeout(() => {
        const body = bodyRef.current
        const target =
          body?.querySelector<HTMLElement>(`[data-field="${found.field}"][aria-invalid="true"]`) ??
          body?.querySelector<HTMLElement>(`[data-field="${found.field}"]`)
        target?.focus()
      }, 0)
      return
    }
    setProblem(null)
    setSaving(true)
    setError(null)
    try {
      await onSave(value)
      onClose()
    } catch (caught) {
      setError(caught instanceof ApiError && typeof caught.detail === 'string' ? caught.detail : '儲存失敗，請再試一次')
    } finally {
      setSaving(false)
    }
  }

  const message = problem?.message ?? error
  return (
    <div ref={bodyRef} className="flex flex-col gap-5">
      {note && <p className="m-0 rounded-md bg-accent-faint px-4 py-2 text-sm text-ink-soft">{note}</p>}
      <QuestionEditor value={value} onChange={change} problem={problem} errorId={errorId} />
      <p id={errorId} className="m-0 text-sm text-bad empty:hidden" role="alert">
        {message}
      </p>
      <div className="flex justify-end gap-2 border-t border-line pt-4">
        <Button variant="ghost" onClick={onCancel}>
          取消
        </Button>
        <Button onClick={save} disabled={saving}>
          {saving ? '儲存中…' : '儲存'}
        </Button>
      </div>
    </div>
  )
}
