/** 編輯題目的對話框：驗證、儲存中狀態、錯誤訊息都在這裡處理，呼叫端只要提供 onSave。 */

import { useState } from 'react'
import { Button } from '@/components/Button'
import { Dialog } from '@/components/Dialog'
import { QuestionEditor } from '@/components/QuestionEditor'
import { ApiError } from '@/lib/api'
import { type QuestionDraft, validateQuestion } from '@/lib/questionEdit'

interface QuestionEditorDialogProps {
  title: string
  /** 開啟時的內容；null 表示關閉 */
  initial: QuestionDraft | null
  onClose: () => void
  onSave: (question: QuestionDraft) => Promise<unknown>
  /** 顯示在編輯器上方的提醒，例如「重新匯入官方試卷時會被覆蓋」 */
  note?: string
}

export function QuestionEditorDialog({ title, initial, onClose, onSave, note }: QuestionEditorDialogProps) {
  // 以 key 重新掛載內層，開啟不同題目時編輯狀態會重設
  return (
    <Dialog open={initial !== null} onClose={onClose} title={title} wide>
      {initial && <EditorBody key={JSON.stringify(initial)} initial={initial} onClose={onClose} onSave={onSave} note={note} />}
    </Dialog>
  )
}

function EditorBody({ initial, onClose, onSave, note }: Omit<QuestionEditorDialogProps, 'title' | 'initial'> & { initial: QuestionDraft }) {
  const [value, setValue] = useState(initial)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    const problem = validateQuestion(value)
    if (problem) {
      setError(problem)
      return
    }
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

  return (
    <div className="flex flex-col gap-5">
      {note && <p className="m-0 rounded-md bg-accent-faint px-4 py-2 text-sm text-ink-soft">{note}</p>}
      <QuestionEditor value={value} onChange={setValue} />
      {error && (
        <p className="m-0 text-sm text-bad" role="alert">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2 border-t border-line pt-4">
        <Button variant="ghost" onClick={onClose}>
          取消
        </Button>
        <Button onClick={save} disabled={saving}>
          {saving ? '儲存中…' : '儲存'}
        </Button>
      </div>
    </div>
  )
}
