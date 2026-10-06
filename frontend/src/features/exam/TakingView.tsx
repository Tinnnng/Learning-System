/** 作答中：一題一頁或整卷、鍵盤操作、計時、交卷。 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { AnswerGrid } from '@/components/AnswerGrid'
import { Button } from '@/components/Button'
import { Segmented } from '@/components/Controls'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'
import { cx } from '@/lib/cx'
import { shortName } from '@/lib/format'
import type { ItemOut, SessionOut } from '@/lib/types'
import { answerItem, deleteSession, submitSession } from './api'
import { LETTERS, QuestionBlock } from './QuestionBlock'
import { Timer } from './Timer'

type ViewMode = 'single' | 'sheet'
const VIEW_KEY = 'ls-exam-view'

function readView(): ViewMode {
  try {
    return localStorage.getItem(VIEW_KEY) === 'sheet' ? 'sheet' : 'single'
  } catch {
    return 'single'
  }
}

export function TakingView({ session }: { session: SessionOut }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const items = session.items
  const firstOpen = items.find((item) => !item.answered)?.position ?? 1
  const [current, setCurrent] = useState(firstOpen)
  const [view, setView] = useState<ViewMode>(readView)
  const [drafts, setDrafts] = useState<Record<number, string[]>>({})
  const [confirmSubmit, setConfirmSubmit] = useState(false)
  const [confirmAbandon, setConfirmAbandon] = useState(false)
  const [gridOpen, setGridOpen] = useState(false)
  const enteredAt = useRef<Record<number, number>>({})
  const isPractice = session.mode === 'practice'
  const item = items.find((entry) => entry.position === current) ?? items[0]

  useEffect(() => {
    enteredAt.current[current] ??= Date.now()
  }, [current])

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_KEY, view)
    } catch {
      // 不能記住也沒關係
    }
  }, [view])

  const updateItem = useCallback(
    (updated: ItemOut) => {
      queryClient.setQueryData<SessionOut>(['exam', 'session', session.id], (old) => {
        if (!old) return old
        const nextItems = old.items.map((entry) => (entry.position === updated.position ? updated : entry))
        return { ...old, items: nextItems, answered_count: nextItems.filter((entry) => entry.answered).length }
      })
    },
    [queryClient, session.id],
  )

  const answer = useMutation({
    mutationFn: ({ position, response }: { position: number; response: string[] }) => {
      const started = enteredAt.current[position]
      const spent = started ? Math.round((Date.now() - started) / 1000) : undefined
      return answerItem(session.id, position, response, spent)
    },
    onSuccess: updateItem,
  })

  const submit = useMutation({
    mutationFn: () => submitSession(session.id),
    onSuccess: (result) => {
      queryClient.setQueryData(['exam', 'session', session.id], result)
      queryClient.invalidateQueries({ queryKey: ['review'] })
      queryClient.invalidateQueries({ queryKey: ['exam', 'sessions'] })
      window.scrollTo({ top: 0 })
    },
  })

  const abandon = useMutation({
    mutationFn: () => deleteSession(session.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exam', 'sessions'] })
      navigate('/')
    },
  })

  const goTo = useCallback(
    (position: number) => {
      const target = Math.min(Math.max(1, position), items.length)
      setCurrent(target)
      setGridOpen(false)
      if (view === 'sheet') {
        document.getElementById(`item-${target}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      } else {
        window.scrollTo({ top: 0, behavior: 'smooth' })
      }
    },
    [items.length, view],
  )

  const toggle = useCallback(
    (target: ItemOut, letter: string) => {
      if (target.revealed || answer.isPending) return
      setCurrent(target.position)
      if (target.type === 'multi_choice') {
        const base = drafts[target.position] ?? target.response ?? []
        const next = base.includes(letter) ? base.filter((value) => value !== letter) : [...base, letter].sort()
        setDrafts((old) => ({ ...old, [target.position]: next }))
        if (!isPractice) answer.mutate({ position: target.position, response: next })
        return
      }
      const same = (target.response ?? []).includes(letter)
      if (isPractice) {
        answer.mutate({ position: target.position, response: [letter] })
        return
      }
      answer.mutate(
        { position: target.position, response: same ? [] : [letter] },
        {
          // 模擬考一題一頁：選好自動翻下一題
          onSuccess: () => {
            if (!same && view === 'single' && target.position < items.length) {
              window.setTimeout(() => setCurrent(target.position + 1), 280)
            }
          },
        },
      )
    },
    [answer, drafts, isPractice, items.length, view],
  )

  // 鍵盤：1–9 / A–J 選選項，←→ 換題，Enter 下一題
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return
      const target = event.target as HTMLElement
      if (target.closest('input, textarea, select, dialog')) return
      const key = event.key.toUpperCase()
      const index = /^[1-9]$/.test(key) ? Number(key) - 1 : LETTERS.indexOf(key)
      if (index >= 0 && index < item.options.length && key.length === 1) {
        event.preventDefault()
        toggle(item, LETTERS[index])
      } else if (event.key === 'ArrowRight' || (event.key === 'Enter' && target.tagName !== 'BUTTON')) {
        if (current < items.length) goTo(current + 1)
      } else if (event.key === 'ArrowLeft') {
        if (current > 1) goTo(current - 1)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [current, goTo, item, items.length, toggle])

  const selectionFor = (entry: ItemOut) => drafts[entry.position] ?? entry.response ?? []
  const unanswered = items.filter((entry) => !entry.answered).length
  const cells = items.map((entry) => ({
    position: entry.position,
    answered: entry.answered,
    correct: entry.revealed ? entry.is_correct : undefined,
  }))
  const onExpire = useCallback(() => submit.mutate(), [submit])

  const block = (entry: ItemOut) => (
    <QuestionBlock
      item={entry}
      selection={selectionFor(entry)}
      onToggle={(letter) => toggle(entry, letter)}
      onConfirmMulti={
        isPractice ? () => answer.mutate({ position: entry.position, response: selectionFor(entry) }) : undefined
      }
      busy={answer.isPending && answer.variables?.position === entry.position}
    />
  )

  const sidebar = (
    <>
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-muted">
          已作答 <span className="tabular text-ink">{session.answered_count}</span>／{session.total}
        </span>
        {session.remaining_seconds !== null && session.remaining_seconds !== undefined && (
          <Timer remainingSeconds={session.remaining_seconds} onExpire={onExpire} />
        )}
      </div>
      <AnswerGrid cells={cells} current={current} onJump={goTo} />
    </>
  )

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="eyebrow">{isPractice ? '練習・作答後立刻對答案' : '模擬考・交卷才評分'}</span>
          <h1 className="m-0 font-hand text-xl font-bold [word-break:keep-all] sm:text-2xl">{shortName(session.title)}</h1>
        </div>
        <Segmented
          label="顯示方式"
          value={view}
          onChange={setView}
          className="w-full sm:w-auto sm:min-w-[220px]"
          options={[
            { value: 'single', label: '一題一頁' },
            { value: 'sheet', label: '整份試卷' },
          ]}
        />
      </header>

      {/* 手機：進度與計時列 */}
      <div className="sticky top-[calc(env(safe-area-inset-top,0px)+64px)] z-20 -mx-4 flex items-center justify-between gap-3 border-b border-line bg-paper/90 px-4 py-2 backdrop-blur-md lg:hidden">
        <span className="text-sm text-muted">
          <span className="tabular text-ink">{session.answered_count}</span>／{session.total} 已作答
        </span>
        {session.remaining_seconds !== null && session.remaining_seconds !== undefined && (
          <Timer remainingSeconds={session.remaining_seconds} onExpire={onExpire} />
        )}
        <Button size="sm" variant="secondary" onClick={() => setGridOpen(true)}>
          題號
        </Button>
      </div>

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_290px]">
        <section aria-label="題目" className="min-w-0 rounded-lg bg-sheet px-4 py-6 shadow-sheet sm:px-8 sm:py-8">
          {view === 'single' ? (
            <div key={item.position} className="animate-[rise-in_var(--dur)_var(--ease-out)]">
              {block(item)}
              <nav aria-label="換題" className="mt-8 flex items-center justify-between gap-3 border-t border-rule pt-5">
                <Button variant="ghost" onClick={() => goTo(current - 1)} disabled={current <= 1}>
                  <Icon name="back" size={18} />
                  上一題
                </Button>
                <span className="tabular text-sm text-muted">
                  {current}／{items.length}
                </span>
                {current < items.length ? (
                  <Button variant={item.revealed || item.answered ? 'primary' : 'secondary'} onClick={() => goTo(current + 1)}>
                    下一題
                    <Icon name="arrow" size={18} />
                  </Button>
                ) : (
                  <Button onClick={() => setConfirmSubmit(true)}>交卷</Button>
                )}
              </nav>
            </div>
          ) : (
            <ol className="m-0 flex list-none flex-col p-0">
              {items.map((entry) => (
                <li
                  key={entry.position}
                  id={`item-${entry.position}`}
                  className="scroll-mt-32 border-b border-rule py-8 first:pt-0 last:border-b-0"
                >
                  {block(entry)}
                </li>
              ))}
            </ol>
          )}
          {answer.isError && (
            <div className="mt-4">
              <ErrorState error={answer.error} />
            </div>
          )}
        </section>

        <aside className="hidden flex-col gap-5 rounded-lg bg-sheet p-5 shadow-sheet lg:sticky lg:top-24 lg:flex">
          {sidebar}
          <Button size="lg" onClick={() => setConfirmSubmit(true)} disabled={submit.isPending}>
            {isPractice ? '結束練習' : '交卷'}
          </Button>
          <button
            type="button"
            onClick={() => setConfirmAbandon(true)}
            className="text-xs text-muted underline-offset-4 hover:text-bad hover:underline"
          >
            放棄這次測驗
          </button>
          <p className="m-0 text-xs leading-relaxed text-muted">
            鍵盤：<kbd className="tabular">1</kbd>–<kbd className="tabular">4</kbd> 或 <kbd className="tabular">A</kbd>–
            <kbd className="tabular">D</kbd> 選答案，<kbd>←</kbd> <kbd>→</kbd> 換題
          </p>
        </aside>
      </div>

      <Dialog
        open={gridOpen}
        onClose={() => setGridOpen(false)}
        title="題號一覽"
        actions={
          <Button onClick={() => { setGridOpen(false); setConfirmSubmit(true) }}>{isPractice ? '結束練習' : '交卷'}</Button>
        }
      >
        <div className="flex flex-col gap-4">{sidebar}</div>
      </Dialog>

      <Dialog
        open={confirmSubmit}
        onClose={() => setConfirmSubmit(false)}
        title={isPractice ? '結束這次練習？' : '確定要交卷？'}
        actions={
          <>
            <Button variant="ghost" onClick={() => setConfirmSubmit(false)}>
              繼續作答
            </Button>
            <Button
              onClick={() => {
                setConfirmSubmit(false)
                submit.mutate()
              }}
              disabled={submit.isPending}
            >
              {isPractice ? '結束並看結果' : '交卷'}
            </Button>
          </>
        }
      >
        <p className="m-0">
          {unanswered > 0 ? (
            <>
              還有 <span className="tabular font-medium text-accent">{unanswered}</span> 題沒有作答，沒作答的題目計 0 分，但不會收進錯題本。
            </>
          ) : (
            '所有題目都作答了。'
          )}
        </p>
      </Dialog>

      <Dialog
        open={confirmAbandon}
        onClose={() => setConfirmAbandon(false)}
        title="放棄這次測驗？"
        actions={
          <>
            <Button variant="ghost" onClick={() => setConfirmAbandon(false)}>
              取消
            </Button>
            <Button variant="danger" onClick={() => abandon.mutate()} disabled={abandon.isPending}>
              放棄並刪除
            </Button>
          </>
        }
      >
        <p className="m-0">
          這次測驗會被刪除。{isPractice && '練習模式已經作答的題目，結果已經記錄到錯題本，不會被撤銷。'}
        </p>
      </Dialog>

      {submit.isError && <ErrorState error={submit.error} />}
      <div className={cx('lg:hidden', 'h-2')} />
    </div>
  )
}
