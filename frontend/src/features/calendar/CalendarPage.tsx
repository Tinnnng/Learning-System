/** 行事曆：下一場考試倒數、月曆、接下來的行程；手動新增或拍照讓 AI 辨識（確認後才加入）；匯出 .ics。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { CountUp } from '@/components/CountUp'
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
  type ExtractedEvent,
  extractFromFile,
  fetchCountdown,
  fetchEvents,
  ICS_URL,
  updateEvent,
} from './api'
import { EventForm } from './EventForm'
import { emptyEvent, KIND_LABELS } from './eventDefaults'
import { SubscriptionPanel } from './Subscriptions'

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
const pad = (value: number) => String(value).padStart(2, '0')
const iso = (year: number, month: number, day: number) => `${year}-${pad(month + 1)}-${pad(day)}`
const todayIso = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Taipei' })

function dateLabel(event: Pick<EventOut, 'date' | 'end_date' | 'time'>) {
  const thisYear = Number(todayIso().slice(0, 4))
  const format = (value: string) => {
    const [year, month, day] = value.split('-').map(Number)
    return year === thisYear ? `${month}/${day}` : `${year}/${month}/${day}`
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
      <div className="flex items-baseline gap-2 text-accent">
        <CountUp value={exam.days_until} duration={900} className="font-display text-[64px] font-bold leading-none tabular-nums" />
        <span className="text-lg">天</span>
      </div>
      <div className="flex flex-col gap-1 pb-1">
        <span className="eyebrow">距離下一場考試</span>
        <span className="font-display text-xl font-bold">{exam.title}</span>
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
        <h2 className="m-0 font-display text-lg font-bold">
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
      <div className="grid grid-cols-7 border-b border-accent pb-1 text-center text-xs text-accent">
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
                'flex aspect-square min-h-11 flex-col items-center justify-start gap-1 rounded-sm pt-1.5 text-sm transition-colors hover:bg-accent-faint',
                key === today && 'ring-1 ring-accent',
                hasExam && 'bg-accent-faint',
              )}
            >
              <span className={cx('tabular', key === today ? 'font-medium text-accent' : 'text-ink')}>{day}</span>
              {dayEvents.length > 0 && (
                <span className="flex gap-0.5">
                  {dayEvents.slice(0, 3).map((event) => (
                    <span
                      key={event.id}
                      className={cx('h-[9px] w-[6px] rounded-full', event.kind === 'exam' ? 'bg-accent' : 'bg-ink')}
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

type Draft = ExtractedEvent & { selected: boolean; editing: boolean }

/** 整組勾選：全選／全不選，部分勾選時顯示半勾 */
function GroupCheckbox({ label, drafts, onChange }: { label: string; drafts: Draft[]; onChange: (selected: boolean) => void }) {
  const selected = drafts.filter((draft) => draft.selected).length
  return (
    <label className="flex min-h-11 cursor-pointer items-center gap-3">
      <input
        type="checkbox"
        checked={selected === drafts.length}
        ref={(element) => {
          if (element) element.indeterminate = selected > 0 && selected < drafts.length
        }}
        onChange={(event) => onChange(event.target.checked)}
        className="h-[18px] w-[18px] accent-[var(--ink)]"
      />
      <span className="font-medium text-ink">{label}</span>
      <span className="text-sm text-muted tabular-nums">
        {selected > 0 ? `已選 ${selected}／${drafts.length}` : `${drafts.length} 場`}
      </span>
    </label>
  )
}

function PhotoImport({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [examsOnly, setExamsOnly] = useState(true)
  const extract = useMutation({
    mutationFn: (file: File) => extractFromFile(file, examsOnly),
    // 只有一類（例如學校的期中考）就預設全選；國家考試計畫表有很多類，讓使用者自己勾要考的
    onSuccess: (result) =>
      // 已經在行事曆的不勾，避免重複加入
      setDrafts(
        result.drafts.map((draft) => ({ ...draft, selected: !draft.exists && result.groups.length <= 1, editing: false })),
      ),
  })
  const update = (index: number, change: Partial<Draft>) =>
    setDrafts((current) => current.map((item, position) => (position === index ? { ...item, ...change } : item)))
  const save = useMutation({
    mutationFn: async () => {
      for (const { selected, editing: _editing, group: _group, ...draft } of drafts) {
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
              加入 {selectedCount} 個考試
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
          <p key={warning} className="m-0 text-sm text-accent">
            {warning}
          </p>
        ))}
        {drafts.length > 0 && (
          <p className="m-0 text-sm text-ink-soft">
            找到 {drafts.length} 場考試，勾選要加入行事曆的（可以整類勾選，也可以逐場挑）。
          </p>
        )}
        {(extract.data?.groups ?? []).map((group) => {
          const members = drafts.map((draft, index) => ({ draft, index })).filter(({ draft }) => draft.group === group)
          if (members.length === 0) return null
          return (
            <fieldset key={group} className="m-0 flex flex-col rounded-md border border-line p-0">
              <legend className="sr-only">{group}</legend>
              <div className="border-b border-line px-4">
                <GroupCheckbox
                  label={group}
                  drafts={members.map(({ draft }) => draft)}
                  onChange={(selected) =>
                    setDrafts((current) => current.map((item) => (item.group === group ? { ...item, selected } : item)))
                  }
                />
              </div>
              <ul className="m-0 flex list-none flex-col p-0">
                {members.map(({ draft, index }) => (
                  <li key={index} className="flex flex-col gap-3 border-b border-line px-4 py-2 last:border-b-0">
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        id={`draft-${index}`}
                        checked={draft.selected}
                        onChange={(event) => update(index, { selected: event.target.checked })}
                        className="mt-[3px] h-[18px] w-[18px] shrink-0 accent-[var(--ink)]"
                      />
                      <label htmlFor={`draft-${index}`} className="flex min-w-0 flex-1 cursor-pointer flex-col gap-0.5">
                        <span className={cx('text-[15px] leading-snug', draft.selected ? 'text-ink' : 'text-ink-soft')}>
                          {draft.title}
                        </span>
                        <span className="text-sm text-muted tabular-nums">
                          {dateLabel(draft)}
                          {draft.location && `・${draft.location}`}
                          {draft.exists && <span className="ml-2 text-accent">已在行事曆</span>}
                        </span>
                      </label>
                      <button
                        type="button"
                        onClick={() => update(index, { editing: !draft.editing })}
                        aria-expanded={draft.editing}
                        className="min-h-11 shrink-0 px-1 text-sm text-muted hover:text-ink"
                      >
                        {draft.editing ? '收合' : '修改'}
                      </button>
                    </div>
                    {draft.editing && <EventForm value={draft} onChange={(next) => update(index, next)} />}
                  </li>
                ))}
              </ul>
            </fieldset>
          )
        })}
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
    <li key={event.id} className="grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-rule py-4 last:border-b-0">
      <span
        className={cx(
          'tabular w-16 text-right text-sm',
          event.kind === 'exam' && event.days_until >= 0 ? 'font-medium text-accent' : 'text-muted',
        )}
      >
        {daysText(event.days_until)}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="flex items-center gap-2">
          <span className="truncate font-medium">{event.title}</span>
          <span className="flex-none rounded-sm bg-accent-faint px-1.5 text-[11px] text-accent">{KIND_LABELS[event.kind ?? 'exam']}</span>
          {event.source === 'photo' && <Icon name="camera" size={14} className="flex-none text-muted" label="拍照加入" />}
          {event.subscription_name && (
            <span className="flex-none truncate text-[11px] text-muted" title="訂閱的行程，隨來源更新">
              訂閱・{event.subscription_name}
            </span>
          )}
        </span>
        <span className="text-xs text-muted">
          {dateLabel(event)}
          {event.location && `・${event.location}`}
          {event.subject && `・${event.subject}`}
        </span>
      </span>
      <span className={cx('flex gap-1', event.subscription_id != null && 'invisible')}>
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
                className="inline-flex h-11 items-center gap-2 rounded-md px-4 text-sm font-medium text-ink-soft transition-colors hover:bg-accent-faint hover:text-ink"
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
              <ul className="stagger m-0 list-none rounded-lg bg-sheet px-4 p-0 shadow-sheet sm:px-6">{upcoming.map(row)}</ul>
            )}
            <div className="mt-6">
              <SubscriptionPanel />
            </div>
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
