/** 備份與還原：資料庫＋題目圖片打包成 zip，每天第一次啟動自動備份，也能手動備份、下載、還原。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { cx } from '@/lib/cx'
import { fileSize, formatDateTime, relativeDay } from '@/lib/format'

type BackupStatus = components['schemas']['BackupStatus']
type Snapshot = components['schemas']['SnapshotOut']
type RestoreResult = components['schemas']['RestoreResult']
type RestoreTarget = { kind: 'snapshot'; snapshot: Snapshot } | { kind: 'file'; file: File }

const KIND_LABEL: Record<Snapshot['kind'], string> = {
  auto: '自動',
  manual: '手動',
  'before-restore': '還原前',
}

function SnapshotRow({
  snapshot,
  latest,
  onRestore,
  onDelete,
}: {
  snapshot: Snapshot
  latest: boolean
  onRestore: () => void
  onDelete: () => void
}) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-rule py-4 last:border-b-0">
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex flex-wrap items-baseline gap-x-2">
          <span className={cx('text-[17px] text-ink', latest && 'font-medium underline decoration-accent decoration-2 underline-offset-[6px]')}>{relativeDay(snapshot.created_at)}
            {latest && <span className="sr-only">（最新）</span>}
          </span>
          <span className="font-mono text-sm text-muted">{formatDateTime(snapshot.created_at)}</span>
        </span>
        <span className="flex items-center gap-2 text-xs text-muted">
          <span
            className={cx(
              'rounded-sm px-1.5 py-0.5',
              snapshot.kind === 'before-restore' ? 'bg-bad-soft text-ink' : snapshot.kind === 'manual' ? 'bg-accent-faint text-accent-strong' : 'bg-sheet-tint',
            )}
          >
            {KIND_LABEL[snapshot.kind]}
          </span>
          {fileSize(snapshot.size_bytes)}
        </span>
      </span>
      <span className="flex items-center gap-1">
        <a
          href={`/api/backup/snapshots/${encodeURIComponent(snapshot.name)}`}
          download={snapshot.name}
          aria-label={`下載 ${formatDateTime(snapshot.created_at)} 的備份`}
          className="inline-flex h-11 items-center gap-1.5 rounded-md px-3 text-sm text-ink-soft transition-colors hover:bg-accent-faint hover:text-ink"
        >
          <Icon name="import" size={17} />
          下載
        </a>
        <Button variant="ghost" size="sm" className="h-11" onClick={onRestore} aria-label={`還原 ${formatDateTime(snapshot.created_at)} 的備份`}>
          <Icon name="refresh" size={17} />
          還原
        </Button>
        <Button variant="ghost" size="sm" className="h-11 w-11 px-0" onClick={onDelete} aria-label={`刪除 ${formatDateTime(snapshot.created_at)} 的備份`}>
          <Icon name="trash" size={17} />
        </Button>
      </span>
    </li>
  )
}

export function BackupPage() {
  const queryClient = useQueryClient()
  const status = useQuery({ queryKey: ['backup'], queryFn: () => api.get<BackupStatus>('/backup/snapshots') })
  const [restoreTarget, setRestoreTarget] = useState<RestoreTarget | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Snapshot | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const create = useMutation({
    mutationFn: () => api.post<Snapshot>('/backup/snapshots'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['backup'] }),
  })
  const remove = useMutation({
    mutationFn: (snapshot: Snapshot) => api.delete(`/backup/snapshots/${encodeURIComponent(snapshot.name)}`),
    onSuccess: () => {
      setDeleteTarget(null)
      return queryClient.invalidateQueries({ queryKey: ['backup'] })
    },
  })
  const restore = useMutation({
    mutationFn: (target: RestoreTarget) => {
      if (target.kind === 'snapshot') {
        return api.post<RestoreResult>(`/backup/snapshots/${encodeURIComponent(target.snapshot.name)}/restore`)
      }
      const form = new FormData()
      form.append('file', target.file)
      return api.postForm<RestoreResult>('/backup/restore', form)
    },
    onSuccess: () => {
      setRestoreTarget(null)
      // 整個資料庫都換了，所有畫面的資料都要重新讀
      return queryClient.invalidateQueries()
    },
  })

  const snapshots = status.data?.snapshots ?? []
  const latest = snapshots[0]

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="資料"
        title="備份與還原"
        description="題庫、作答紀錄、錯題本、單字進度、行事曆和題目圖片會打包成一個 zip；換電腦或資料出問題時，用它還原。"
        actions={
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            <Icon name="archive" size={17} />
            {create.isPending ? '備份中…' : '立即備份'}
          </Button>
        }
      />

      {/* 朗讀區一直存在、完成後才填字，螢幕閱讀器才念得出來 */}
      <p className="sr-only" aria-live="polite">
        {create.data ? `已備份：${create.data.name}` : ''}
      </p>
      {create.isError && <ErrorState error={create.error} />}
      {restore.data && (
        <p className="m-0 rounded-md bg-ok-soft/60 px-4 py-3 text-[15px]" role="status">
          已還原{restore.data.restored_from && `到 ${formatDateTime(restore.data.restored_from)} 的資料`}（含 {restore.data.assets} 張圖片）。
          還原前的資料另外備份成「還原前」，還原錯了可以用它再換回來。
        </p>
      )}

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section aria-label="備份列表" className="rounded-lg bg-sheet px-4 shadow-sheet sm:px-6">
          {status.isPending ? (
            <Loading className="py-10" />
          ) : status.isError ? (
            <div className="py-6">
              <ErrorState error={status.error} onRetry={() => status.refetch()} />
            </div>
          ) : snapshots.length === 0 ? (
            <div className="py-6">
              <EmptyState title="還沒有備份">按「立即備份」建立第一份；之後每天第一次開啟系統也會自動備份。</EmptyState>
            </div>
          ) : (
            <ul className="stagger m-0 list-none p-0">
              {snapshots.map((snapshot) => (
                <SnapshotRow
                  key={snapshot.name}
                  snapshot={snapshot}
                  latest={snapshot === latest}
                  onRestore={() => setRestoreTarget({ kind: 'snapshot', snapshot })}
                  onDelete={() => setDeleteTarget(snapshot)}
                />
              ))}
            </ul>
          )}
        </section>

        <aside className="flex flex-col gap-6">
          <section className="flex flex-col gap-3 rounded-lg border border-rule px-5 py-5">
            <h2 className="m-0 font-display text-lg font-bold">從檔案還原</h2>
            <p className="m-0 text-sm text-muted">選之前下載的備份 zip（例如從另一台電腦帶過來的）。</p>
            <input
              ref={fileInput}
              type="file"
              accept=".zip,application/zip"
              className="sr-only"
              tabIndex={-1}
              aria-label="選擇備份 zip 檔"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) setRestoreTarget({ kind: 'file', file })
                event.target.value = ''
              }}
            />
            <Button variant="secondary" onClick={() => fileInput.current?.click()}>
              <Icon name="page" size={17} />
              選擇備份檔
            </Button>
          </section>
          {status.data && (
            <section className="flex flex-col gap-2 px-1 text-sm text-muted">
              <h2 className="m-0 text-sm font-medium text-ink">自動備份</h2>
              <p className="m-0">
                {status.data.auto_hours > 0
                  ? `距離上次備份超過 ${status.data.auto_hours} 小時，開啟系統時就自動備份一次，保留最近 ${status.data.keep} 份；手動和還原前的備份不會自動刪除。`
                  : '自動備份已關閉（LS_BACKUP_AUTO_HOURS=0）。'}
              </p>
              <p className="m-0 break-all font-mono text-xs">{status.data.folder}</p>
            </section>
          )}
        </aside>
      </div>

      <Dialog
        open={restoreTarget !== null}
        onClose={() => !restore.isPending && setRestoreTarget(null)}
        title="用這份備份還原？"
        actions={
          <>
            <Button variant="ghost" onClick={() => setRestoreTarget(null)} disabled={restore.isPending}>
              取消
            </Button>
            <Button variant="danger" onClick={() => restoreTarget && restore.mutate(restoreTarget)} disabled={restore.isPending}>
              {restore.isPending ? '還原中…' : '覆蓋目前的資料'}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3 text-[15px]">
          {restoreTarget && (
            <p className="m-0 rounded-md bg-sheet-tint px-3 py-2 font-mono text-sm">
              {restoreTarget.kind === 'snapshot'
                ? `${formatDateTime(restoreTarget.snapshot.created_at)}（${KIND_LABEL[restoreTarget.snapshot.kind]}）`
                : restoreTarget.file.name}
            </p>
          )}
          <p className="m-0">目前所有的題庫、作答紀錄、錯題、單字進度和行事曆都會換成這份備份的內容。</p>
          <p className="m-0 text-muted">還原前會先自動備份目前的資料，萬一選錯了，可以再用那份換回來。</p>
          {restore.isError && <ErrorState error={restore.error} />}
        </div>
      </Dialog>

      <Dialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="刪除這份備份？"
        actions={
          <>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button variant="danger" onClick={() => deleteTarget && remove.mutate(deleteTarget)} disabled={remove.isPending}>
              刪除
            </Button>
          </>
        }
      >
        <p className="m-0 text-[15px]">
          {deleteTarget && `${formatDateTime(deleteTarget.created_at)} 的備份會從電腦上刪除，無法復原。`}
        </p>
        {remove.isError && <ErrorState error={remove.error} />}
      </Dialog>
    </div>
  )
}
