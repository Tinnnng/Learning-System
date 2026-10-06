/** 訂閱考試行事曆（iCal）：從清單選考試類別，或貼上 iCal 網址／Google 日曆 ID。同步不需要 AI。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button } from '@/components/Button'
import { Switch } from '@/components/Controls'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'
import { cx } from '@/lib/cx'
import { formatDateTime } from '@/lib/format'
import { fetchPresets, fetchSubscriptions, subscribe, type SyncResult, syncSubscription, unsubscribe } from './api'

function SyncNote({ result }: { result: SyncResult }) {
  return (
    <p className="m-0 text-sm text-ok" role="status">
      已同步「{result.subscription.name}」：新增 {result.added}、更新 {result.updated}
      {result.removed > 0 && `、移除 ${result.removed}`} 個行程。
    </p>
  )
}

function AddSubscription({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const presets = useQuery({ queryKey: ['calendar', 'presets'], queryFn: fetchPresets, enabled: open })
  const [search, setSearch] = useState('')
  const [url, setUrl] = useState('')
  const [includeDeadlines, setIncludeDeadlines] = useState(true)
  const add = useMutation({
    mutationFn: subscribe,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['calendar'] }),
  })
  const close = () => {
    add.reset()
    setUrl('')
    setSearch('')
    onClose()
  }
  const list = (presets.data?.calendars ?? []).filter((preset) => preset.name.includes(search.trim()))

  return (
    <Dialog open={open} onClose={close} title="訂閱考試行事曆" wide actions={<Button variant="ghost" onClick={close}>完成</Button>}>
      <div className="flex flex-col gap-5">
        <p className="m-0 text-sm text-muted">
          訂閱後會自動匯入今天以後的考試日期，之後按「更新」就能同步最新日期。這種匯入不需要 AI，也不會用到 Claude 額度。
        </p>
        <Switch
          label="包含報名開始、截止等期限"
          description="關掉就只匯入考試日期"
          checked={includeDeadlines}
          onChange={setIncludeDeadlines}
        />

        <section className="flex flex-col gap-3" aria-label="考試類別">
          <div className="relative">
            <Icon name="search" size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜尋考試，例如：普通、高等、銀行"
              aria-label="搜尋考試類別"
              className="h-10 w-full rounded-md border border-line bg-sheet pl-9 pr-3 text-sm text-ink outline-none focus:border-ink"
            />
          </div>
          <ul className="m-0 grid max-h-64 list-none grid-cols-2 gap-2 overflow-y-auto p-0 sm:grid-cols-3">
            {list.map((preset) => (
              <li key={preset.url}>
                <button
                  type="button"
                  disabled={preset.subscribed || add.isPending}
                  onClick={() => add.mutate({ url: preset.url, name: preset.name, include_deadlines: includeDeadlines })}
                  className={cx(
                    'flex h-11 w-full items-center justify-between gap-2 rounded-md border px-3 text-left text-sm transition-colors',
                    preset.subscribed
                      ? 'border-ok/40 bg-ok-soft/40 text-ok'
                      : 'border-line bg-sheet text-ink hover:border-rule hover:bg-accent-faint',
                  )}
                >
                  <span className="truncate">{preset.name}</span>
                  {preset.subscribed ? <Icon name="check" size={16} /> : <Icon name="plus" size={16} className="text-accent" />}
                </button>
              </li>
            ))}
          </ul>
          {presets.data && <p className="m-0 text-[11px] leading-relaxed text-muted">{presets.data.source}</p>}
        </section>

        <form
          className="flex flex-col gap-2 border-t border-rule pt-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (url.trim()) add.mutate({ url: url.trim(), include_deadlines: includeDeadlines })
          }}
        >
          <label htmlFor="ical-url" className="text-sm text-ink">
            或貼上其他 iCal 網址
          </label>
          <div className="flex gap-2">
            <input
              id="ical-url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://…/calendar.ics、webcal://…，或 Google 日曆 ID"
              className="h-10 min-w-0 flex-1 rounded-md border border-line bg-sheet px-3 text-sm text-ink outline-none focus:border-ink"
            />
            <Button type="submit" size="sm" variant="secondary" disabled={!url.trim() || add.isPending}>
              訂閱
            </Button>
          </div>
        </form>

        {add.isPending && (
          <p className="m-0 text-sm text-muted" role="status">
            下載行事曆中…
          </p>
        )}
        {add.isError && <ErrorState error={add.error} />}
        {add.data && <SyncNote result={add.data} />}
      </div>
    </Dialog>
  )
}

export function SubscriptionPanel() {
  const queryClient = useQueryClient()
  const subscriptions = useQuery({ queryKey: ['calendar', 'subscriptions'], queryFn: fetchSubscriptions })
  const [adding, setAdding] = useState(false)
  const [removing, setRemoving] = useState<{ id: number; name: string } | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['calendar'] })
  const sync = useMutation({ mutationFn: syncSubscription, onSettled: refresh })
  const remove = useMutation({
    mutationFn: unsubscribe,
    onSuccess: () => {
      refresh()
      setRemoving(null)
    },
  })
  const list = subscriptions.data ?? []

  return (
    <section aria-labelledby="subscriptions-title" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h2 id="subscriptions-title" className="eyebrow m-0">
          訂閱的考試行事曆
        </h2>
        <Button variant="secondary" size="sm" onClick={() => setAdding(true)}>
          <Icon name="plus" size={16} />
          訂閱
        </Button>
      </div>
      {list.length === 0 ? (
        <p className="m-0 text-sm text-muted">
          還沒有訂閱。訂閱「普通考試」「高等考試」等行事曆，報名與考試日期會自動加入。
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {list.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-line bg-sheet px-4 py-3">
              <span className="flex min-w-0 flex-col">
                <span className="font-medium">{item.name}</span>
                <span className={cx('text-xs', item.last_error ? 'text-bad' : 'text-muted')}>
                  {item.last_error
                    ? `上次更新失敗：${item.last_error}`
                    : `接下來 ${item.upcoming_count} 個行程${item.include_deadlines ? '' : '（只有考試）'}・${
                        item.last_synced_at ? `${formatDateTime(item.last_synced_at)} 更新` : '尚未更新'
                      }`}
                </span>
              </span>
              <span className="flex gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => sync.mutate(item.id)}
                  disabled={sync.isPending && sync.variables === item.id}
                  aria-label={`更新 ${item.name}`}
                >
                  <Icon name="refresh" size={16} />
                  更新
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setRemoving({ id: item.id, name: item.name })} aria-label={`取消訂閱 ${item.name}`}>
                  <Icon name="trash" size={16} />
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {sync.isError && <ErrorState error={sync.error} />}
      {sync.data && <SyncNote result={sync.data} />}

      <AddSubscription open={adding} onClose={() => setAdding(false)} />
      <Dialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title="取消訂閱？"
        actions={
          <>
            <Button variant="ghost" onClick={() => setRemoving(null)}>
              保留
            </Button>
            <Button variant="danger" onClick={() => removing && remove.mutate(removing.id)} disabled={remove.isPending}>
              取消訂閱
            </Button>
          </>
        }
      >
        <p className="m-0">「{removing?.name}」匯入的所有行程都會從行事曆移除。之後可以再訂閱。</p>
      </Dialog>
    </section>
  )
}
