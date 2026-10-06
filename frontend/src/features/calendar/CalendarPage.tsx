/** 行事曆：下一場考試倒數、月曆、接下來的行程；手動新增或拍照讓 AI 辨識（確認後才加入）；匯出 .ics。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { Switch } from '@/components/Controls'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { ApiError } from '@/lib/api'
import { cx } from '@/lib/cx'
import {
  createEvent,
  deleteEvent,
  type EventIn,
  type EventOut,
  extractFromFile,
  fetchCountdown,
  fetchEvents,
  ICS_URL,
  updateEvent,
} from './api'
import { EventForm } from './EventForm'
import { emptyEvent, KIND_LABELS } from './eventDefaults'

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
const pad = (value: number) => String(value).padStart(2, '0')
const iso = (year: number, month: number, day: number) => `${year}-${pad(month + 1)}-${pad(day)}`
const todayIso = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Taipei' })

function dateLabel(event: Pick<EventOut, 'date' | 'end_date' | 'time'>) {
  const format = (value: string) => {
    const [, month, day] = value.split('-').map(Number)
    return `${month}/${day}`
  }
  const weekday = WEEKDAYS[new Date(`${event.date}T00:00:00`).getDay()]
  return `${format(event.date)}（${weekday}）${event.end_date ? `～${format(event.end_date)}` : ''}${event.time ? ` ${event.time}` : ''}`
}

function daysText(days: number) {
  if (days === 0) return '今天'
  if (days === 1) return '明天'
  return days > 0 ? `${days} 天後` : `${-days} 天前`
}

function Countdown() {
  const countdown = useQuery({ queryKey: ['calendar', 'countdown'], queryFn: fetchCountdown })
  const exam = countdown.data?.next_exam
  if (!exam) return null
  return (
    <section aria-label="下一場考試" className="flex flex-wrap items-end gap-x-8 gap-y-3 rounded-lg bg-sheet px-6 py-6 shadow-sheet sm:px-8">
      <div className="flex items-baseline gap-2 text-print">
        <span className="font-serif text-[64px] font-bold leading-none tabular-nums">{exam.days_until}</span>
        <span className="text-lg">天</span>
      </div>
      <div className="flex flex-col gap-1 pb-1">
        <span className="eyebrow">距離下一場考試</span>
        <span className="font-serif text-xl font-bold">{exam.title}</span>
        <span className="text-sm text-muted">
          {dateLabel(exam)}
          {exam.location && `・${exam.location}`}
        </span>
      </div>
    </section>
  )
}

function MonthGrid({ events, onPick }: { events: EventOut[]; onPick: (date: string) => void }) {
  const today = todayIso()
  const [cursor, setCursor] = useState(() => {
    const [year, month] = today.split('-').map(Number)
    return { year, month: month - 1 }
  })
  const first = new Date(cursor.year, cursor.month, 1)
  const daysInMonth = new Date(cursor.year, cursor.month + 1, 0).getDate()
  const cells = [...Array(first.getDay()).fill(null), ...Array.from({ length: daysInMonth }, (_, index) => index + 1)]
  const byDay = new Map<string, EventOut[]>()
  for (const event of events) {
    const start = new Date(`${event.date}T00:00:00`)
    const end = new Date(`${event.end_date ?? event.date}T00:00:00`)
    for (const day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) {
      const key = iso(day.getFullYear(), day.getMonth(), day.getDate())
      byDay.set(key, [...(byDay.get(key) ?? []), event])
    }
  }
  const move = (delta: number) => {
    const next = new Date(cursor.year, cursor.month + delta, 1)
    setCursor({ year: next.getFullYear(), month: next.getMonth() })
  }

  return (
    <section aria-label="月曆" className="flex flex-col gap-3 rounded-lg bg-sheet p-4 shadow-sheet sm:p-6">
      <div className="flex items-center justify-between">
        <h2 className="m-0 font-serif text-lg font-bold">
          {cursor.year} 年 {cursor.month + 1} 月
        </h2>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={() => move(-1)} aria-label="上個月">
            <Icon name="left" size={18} />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => move(1)} aria-label="下個月">
            <Icon name="right" size={18} />
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-7 border-b border-print pb-1 text-center text-xs text-print">
        {WEEKDAYS.map((day) => (
          <span key={day}>{day}</span>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, index) => {
          if (day === null) return <span key={`blank-${index}`} />
          const key = iso(cursor.year, cursor.month, day)
          const dayEvents = byDay.get(key) ?? []
          const hasExam = dayEvents.some((event) => event.kind === 'exam')
          return (
            <button
              key={key}
              type="button"
              onClick={() => onPick(key)}
              aria-label={`${cursor.month + 1} 月 ${day} 日${dayEvents.length ? `，${dayEvents.map((event) => event.title).join('、')}` : ''}`}
              className={cx(
                'flex aspect-square min-h-11 flex-col items-center justify-start gap-1 rounded-sm pt-1.5 text-sm transition-colors hover:bg-print-faint',
                key === today && 'ring-1 ring-print',
                hasExam && 'bg-print-faint',
              )}
            >
              <span className={cx('tabular', key === today ? 'font-medium text-print' : 'text-ink')}>{day}</span>
              {dayEvents.length > 0 && (
                <span className="flex gap-0.5">
                  {dayEvents.slice(0, 3).map((event) => (
                    <span
                      key={event.id}
                      className={cx('h-[9px] w-[6px] rounded-full', event.kind === 'exam' ? 'bg-print' : 'bg-ink')}
                    />
                  ))}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </section>
  )
}

function PhotoImport({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Array<EventIn & { selected: boolean }>>([])
  const [examsOnly, setExamsOnly] = useState(true)
  const extract = useMutation({
    mutationFn: (file: File) => extractFromFile(file, examsOnly),
    onSuccess: (result) => setDrafts(result.drafts.map((draft) => ({ ...draft, selected: true }))),
  })
  const save = useMutation({
    mutationFn: async () => {
      for (const { selected, ...draft } of drafts) {
        if (selected) await createEvent(draft, 'photo')
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
      close()
    },
  })
  const close = () => {
    setDrafts([])
    setPreview(null)
    extract.reset()
    onClose()
  }
  const selectedCount = drafts.filter((draft) => draft.selected).length

  return (
    <Dialog
      open={open}
      onClose={close}
      title="從照片或 PDF 加入考試日期"
      wide
      actions={
        drafts.length > 0 ? (
          <>
            <Button variant="ghost" onClick={close}>
              取消
            </Button>
            <Button onClick={() => save.mutate()} disabled={selectedCount === 0 || save.isPending}>
              加入 {selectedCount} 個行程
            </Button>
          </>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-5">
        <p className="m-0 text-sm text-muted">
          上傳考試公告、准考證或學校行事曆，AI 會找出日期，確認後才會加入行事曆。學校行事曆請優先用學校網站的
          PDF：比截圖清楚得多，而且幾秒就辨識完。
        </p>
        <Switch
          label="只找考試日期"
          description="學校行事曆事項很多，只挑期中考、期末考等考試"
          checked={examsOnly}
          onChange={setExamsOnly}
        />
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,image/png,image/jpeg,image/webp,image/gif"
          capture="environment"
          className="sr-only"
          id="calendar-photo"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (!file) return
            setDrafts([])
            setPreview(file.type === 'application/pdf' ? null : URL.createObjectURL(file))
            extract.mutate(file)
          }}
        />
        <div className="flex flex-wrap items-start gap-4">
          <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={extract.isPending}>
            <Icon name="camera" size={18} />
            {extract.isIdle ? '選擇照片或 PDF' : '換一個檔案'}
          </Button>
          {preview && <img src={preview} alt="上傳的照片" className="max-h-40 rounded-sm border border-line" />}
        </div>
        {extract.isPending && (
          <p className="m-0 text-sm text-muted" role="status">
            AI 正在辨識，PDF 約 5 秒、照片約 10～20 秒…
          </p>
        )}
        {extract.isError && (
          <ErrorState error={extract.error instanceof ApiError ? extract.error : new ApiError(500, 'AI 辨識失敗')} />
        )}
        {extract.data?.warnings.map((warning) => (
          <p key={warning} className="m-0 text-sm text-print">
            {warning}
          </p>
        ))}
        {drafts.map((draft, index) => (
          <fieldset
            key={index}
            className={cx(
              'm-0 flex flex-col gap-3 rounded-md border px-4 py-4 transition-opacity',
              draft.selected ? 'border-print-rule' : 'border-line opacity-55',
            )}
          >
            <label className="flex items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={draft.selected}
                onChange={(event) =>
                  setDrafts(drafts.map((item, position) => (position === index ? { ...item, selected: event.target.checked } : item)))
                }
                className="h-4 w-4 accent-[var(--ink)]"
              />
              加入這個行程
            </label>
            <EventForm
              value={draft}
              onChange={(next) => setDrafts(drafts.map((item, position) => (position === index ? { ...item, ...next } : item)))}
            />
          </fieldset>
        ))}
        {save.isError && <ErrorState error={save.error} />}
      </div>
    </Dialog>
  )
}

export function CalendarPage() {
  const queryClient = useQueryClient()
  const [range] = useState(() => {
    const now = new Date()
    return {
      start: iso(now.getFullYear() - 1, now.getMonth(), 1),
      end: iso(now.getFullYear() + 2, now.getMonth(), 1),
    }
  })
  const events = useQuery({ queryKey: ['calendar', 'events', range], queryFn: () => fetchEvents(range.start, range.end) })
  const [editing, setEditing] = useState<{ id: number | null; value: EventIn } | null>(null)
  const [photoOpen, setPhotoOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<EventOut | null>(null)
  const [today] = useState(todayIso)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['calendar'] })
  const save = useMutation({
    mutationFn: () => (editing!.id ? updateEvent(editing!.id, editing!.value) : createEvent(editing!.value)),
    onSuccess: () => {
      refresh()
      setEditing(null)
    },
  })
  const remove = useMutation({
    mutationFn: (id: number) => deleteEvent(id),
    onSuccess: () => {
      refresh()
      setConfirmDelete(null)
    },
  })

  const all = events.data ?? []
  const upcoming = all.filter((event) => (event.end_date ?? event.date) >= today)
  const past = all.filter((event) => (event.end_date ?? event.date) < today).reverse().slice(0, 5)

  const row = (event: EventOut) => (
    <li key={event.id} className="grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-print-rule py-4 last:border-b-0">
      <span
        className={cx(
          'tabular w-16 text-right text-sm',
          event.kind === 'exam' && event.days_until >= 0 ? 'font-medium text-print' : 'text-muted',
        )}
      >
        {daysText(event.days_until)}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="flex items-center gap-2">
          <span className="truncate font-medium">{event.title}</span>
          <span className="flex-none rounded-sm bg-print-faint px-1.5 text-[11px] text-print">{KIND_LABELS[event.kind ?? 'exam']}</span>
          {event.source === 'photo' && <Icon name="camera" size={14} className="flex-none text-muted" label="拍照加入" />}
        </span>
        <span className="text-xs text-muted">
          {dateLabel(event)}
          {event.location && `・${event.location}`}
          {event.subject && `・${event.subject}`}
        </span>
      </span>
      <span className="flex gap-1">
        <Button variant="ghost" size="sm" aria-label={`編輯 ${event.title}`} onClick={() => setEditing({ id: event.id, value: { ...event } })}>
          <Icon name="edit" size={16} />
        </Button>
        <Button variant="ghost" size="sm" aria-label={`刪除 ${event.title}`} onClick={() => setConfirmDelete(event)}>
          <Icon name="trash" size={16} />
        </Button>
      </span>
    </li>
  )

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="行事曆"
        title="考試日期"
        description="記下考試與報名期限，首頁會顯示倒數。可以匯出成 .ics 檔，匯入 Google 日曆或手機行事曆，考試前一天會提醒。"
        actions={
          <>
            <Button onClick={() => setEditing({ id: null, value: emptyEvent(today) })}>
              <Icon name="plus" size={18} />
              新增
            </Button>
            <Button variant="secondary" onClick={() => setPhotoOpen(true)}>
              <Icon name="camera" size={18} />
              照片／PDF 加入
            </Button>
            {all.length > 0 && (
              <a
                href={ICS_URL}
                download
                className="inline-flex h-11 items-center gap-2 rounded-md px-4 text-sm font-medium text-ink-soft transition-colors hover:bg-print-faint hover:text-ink"
              >
                <Icon name="import" size={18} />
                匯出 .ics
              </a>
            )}
          </>
        }
      />

      <Countdown />

      {events.isPending ? (
        <Loading />
      ) : events.isError ? (
        <ErrorState error={events.error} onRetry={() => events.refetch()} />
      ) : (
        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <MonthGrid events={all} onPick={(date) => setEditing({ id: null, value: emptyEvent(date) })} />
          <section aria-label="接下來的行程" className="flex flex-col gap-2">
            <h2 className="eyebrow m-0">接下來</h2>
            {upcoming.length === 0 ? (
              <EmptyState title="還沒有行程">新增考試日期，或拍下考試公告讓 AI 幫你找出日期。</EmptyState>
            ) : (
              <ul className="m-0 list-none rounded-lg bg-sheet px-4 p-0 shadow-sheet sm:px-6">{upcoming.map(row)}</ul>
            )}
            {past.length > 0 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm text-muted">已經過去的行程</summary>
                <ul className="m-0 mt-2 list-none p-0 opacity-70">{past.map(row)}</ul>
              </details>
            )}
          </section>
        </div>
      )}

      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing?.id ? '編輯行程' : '新增行程'}
        wide
        actions={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              取消
            </Button>
            <Button onClick={() => save.mutate()} disabled={!editing?.value.title.trim() || !editing?.value.date || save.isPending}>
              儲存
            </Button>
          </>
        }
      >
        {editing && <EventForm value={editing.value} onChange={(value) => setEditing({ ...editing, value })} />}
        {save.isError && (
          <div className="mt-4">
            <ErrorState error={save.error} />
          </div>
        )}
      </Dialog>

      <Dialog
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        title="刪除這個行程？"
        actions={
          <>
            <Button variant="ghost" onClick={() => setConfirmDelete(null)}>
              取消
            </Button>
            <Button variant="danger" onClick={() => confirmDelete && remove.mutate(confirmDelete.id)} disabled={remove.isPending}>
              刪除
            </Button>
          </>
        }
      >
        <p className="m-0">「{confirmDelete?.title}」會從行事曆移除。</p>
      </Dialog>

      <PhotoImport open={photoOpen} onClose={() => setPhotoOpen(false)} />
    </div>
  )
}
