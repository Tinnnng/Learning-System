/** 行程表單：新增、編輯，以及拍照辨識後的草稿修改共用。 */

import { useId } from 'react'
import { Segmented } from '@/components/Controls'
import type { EventIn } from './api'
import { KIND_LABELS } from './eventDefaults'

const inputClass =
  'h-10 w-full rounded-md border border-line bg-sheet px-3 text-sm text-ink outline-none transition-colors focus:border-ink'

/** 欄位：children 拿到 id 與提示的 id（有提示時給 aria-describedby，朗讀欄位時一起念出提示） */
function Field({
  label,
  children,
  hint,
}: {
  label: string
  children: (id: string, describedBy: string | undefined) => React.ReactNode
  hint?: string
}) {
  const id = useId()
  const hintId = `${id}-hint`
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs text-muted">
        {label}
      </label>
      {children(id, hint ? hintId : undefined)}
      {hint && (
        <span id={hintId} className="text-[11px] text-muted">
          {hint}
        </span>
      )}
    </div>
  )
}

export function EventForm({ value, onChange }: { value: EventIn; onChange: (value: EventIn) => void }) {
  const set = <K extends keyof EventIn>(key: K, next: EventIn[K]) => onChange({ ...value, [key]: next })
  const text = (next: string) => (next.trim() === '' ? null : next)
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Field label="名稱">
          {(id) => (
            <input id={id} name="title" autoComplete="off" required className={inputClass} value={value.title} onChange={(event) => set('title', event.target.value)} placeholder="例如：115 年高考三級…" />
          )}
        </Field>
      </div>
      <div className="sm:col-span-2">
        <Segmented
          label="類型"
          value={value.kind ?? 'exam'}
          onChange={(kind) => set('kind', kind)}
          options={(Object.keys(KIND_LABELS) as Array<keyof typeof KIND_LABELS>).map((kind) => ({ value: kind, label: KIND_LABELS[kind] }))}
        />
      </div>
      <Field label="日期">
        {(id) => <input id={id} name="date" type="date" required className={inputClass} value={value.date} onChange={(event) => set('date', event.target.value)} />}
      </Field>
      <Field label="時間" hint="不填就是整天">
        {(id, hint) => <input id={id} name="time" type="time" aria-describedby={hint} className={inputClass} value={value.time ?? ''} onChange={(event) => set('time', text(event.target.value))} />}
      </Field>
      <Field label="結束日期" hint="連續好幾天的考試才需要">
        {(id, hint) => (
          <input id={id} name="end_date" type="date" aria-describedby={hint} min={value.date} className={inputClass} value={value.end_date ?? ''} onChange={(event) => set('end_date', text(event.target.value))} />
        )}
      </Field>
      <Field label="地點">
        {(id) => <input id={id} name="location" autoComplete="off" className={inputClass} value={value.location ?? ''} onChange={(event) => set('location', text(event.target.value))} />}
      </Field>
      <div className="sm:col-span-2">
        <Field label="科目">
          {(id) => <input id={id} name="subject" autoComplete="off" className={inputClass} value={value.subject ?? ''} onChange={(event) => set('subject', text(event.target.value))} placeholder="例如：資料結構…" />}
        </Field>
      </div>
      <div className="sm:col-span-2">
        <Field label="備註">
          {(id) => (
            <textarea id={id} name="note" rows={2} className={`${inputClass} h-auto py-2`} value={value.note ?? ''} onChange={(event) => set('note', text(event.target.value))} />
          )}
        </Field>
      </div>
    </div>
  )
}
