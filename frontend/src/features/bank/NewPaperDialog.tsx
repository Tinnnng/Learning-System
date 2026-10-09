/** 自建題組：期中考自己出題、整理筆記題目。建立後進入試卷頁一題一題新增。 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/Button'
import { Dialog } from '@/components/Dialog'
import { ErrorState } from '@/components/States'
import { api } from '@/lib/api'
import type { PaperDetail } from '@/lib/types'

const field = 'h-10 w-full rounded-md border border-line bg-sheet px-3 text-sm text-ink outline-none focus:border-accent'

export function NewPaperDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [subject, setSubject] = useState('')
  const [examType, setExamType] = useState('期中考')
  const [year, setYear] = useState('')
  const create = useMutation({
    mutationFn: () =>
      api.post<PaperDetail>('/bank/papers', {
        subject: subject.trim(),
        exam_type: examType.trim() || '期中考',
        year: year ? Number(year) : null,
      }),
    onSuccess: (paper) => {
      queryClient.invalidateQueries({ queryKey: ['bank'] })
      onClose()
      navigate(`/bank/papers/${paper.id}`)
    },
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (subject.trim()) create.mutate()
  }

  return (
    <Dialog open={open} onClose={onClose} title="自建題組">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <p className="m-0 text-sm text-muted">
          適合自己出題或整理上課重點。建立後可以一題一題新增，也能用來練習與模擬考。整份教材想交給 AI 出題的話，請 Claude Code 照
          docs/ingest-lecture.md 處理。
        </p>
        <label className="flex flex-col gap-1.5 text-xs text-muted">
          科目
          <input required className={field} value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="例如：程式設計…" />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1.5 text-xs text-muted">
            考試類型
            <input className={field} value={examType} onChange={(event) => setExamType(event.target.value)} />
          </label>
          <label className="flex flex-col gap-1.5 text-xs text-muted">
            年度（民國，可不填）
            <input className={field} inputMode="numeric" value={year} onChange={(event) => setYear(event.target.value.replace(/\D/g, ''))} placeholder="115" />
          </label>
        </div>
        {create.isError && <ErrorState error={create.error} />}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button type="submit" disabled={!subject.trim() || create.isPending}>
            建立
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
