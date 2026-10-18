import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { NoteControls } from './NoteControls'

type Body = { starred?: boolean; note?: string | null }

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
const sleep = (ms: number) => act(async () => new Promise((resolve) => setTimeout(resolve, ms)))

/** 假的後端：GET 回 load 指定的狀態，PUT 依序記錄並照部分更新的規則合併 */
function mockServer(load: 'pending' | 'error' | 'ok', putDelay = 0) {
  const stored = { question_id: 1, starred: false, note: '我的重要筆記' as string | null, updated_at: '2026-01-01T00:00:00' }
  const puts: Body[] = []
  let inFlight = 0
  let maxInFlight = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === 'PUT') {
        const body = JSON.parse(String(init.body)) as Body
        puts.push(body)
        inFlight += 1
        maxInFlight = Math.max(maxInFlight, inFlight)
        if (putDelay) await new Promise((resolve) => setTimeout(resolve, putDelay))
        inFlight -= 1
        Object.assign(stored, body)
        return new Response(JSON.stringify(stored), { status: 200 })
      }
      if (load === 'pending') return new Promise<Response>(() => {})
      if (load === 'error') return new Response(JSON.stringify({ detail: 'boom' }), { status: 500 })
      return new Response(JSON.stringify(stored), { status: 200 })
    }),
  )
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <NoteControls questionId={1} />
    </QueryClientProvider>,
  )
  return { puts, stored, view, queryClient, maxInFlight: () => maxInFlight }
}

test('筆記還沒讀到時不能收藏或打字，不會送出清掉筆記的請求', async () => {
  const { puts } = mockServer('pending')
  expect(screen.getByRole('button', { name: '收藏' })).toBeDisabled()
  expect(screen.getByRole('textbox')).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '收藏' }))
  await sleep(20)
  expect(puts).toEqual([])
})

test('筆記讀取失敗時維持停用，並提供重試', async () => {
  const { puts } = mockServer('error')
  await screen.findByText('筆記讀取失敗')
  expect(screen.getByRole('textbox')).toBeDisabled()
  expect(screen.getByRole('button', { name: '收藏' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '重試' })).toBeInTheDocument()
  expect(puts).toEqual([])
})

test('按星號只送收藏狀態，不帶筆記', async () => {
  const { puts, stored } = mockServer('ok')
  await screen.findByDisplayValue('我的重要筆記')
  fireEvent.click(screen.getByRole('button', { name: '收藏' }))
  await waitFor(() => expect(puts).toEqual([{ starred: true }]))
  expect(stored.note).toBe('我的重要筆記')
})

test('連點星號依序送出、每次反轉最新狀態，不會兩個請求同時在路上', async () => {
  const { puts, stored, maxInFlight } = mockServer('ok', 100)
  await screen.findByDisplayValue('我的重要筆記')
  const star = screen.getByRole('button', { name: '收藏' })
  fireEvent.click(star)
  fireEvent.click(star)
  fireEvent.click(star)
  await sleep(500)
  expect(puts).toEqual([{ starred: true }, { starred: false }, { starred: true }])
  expect(maxInFlight()).toBe(1)
  expect(stored.starred).toBe(true)
  expect(star).toHaveAttribute('aria-pressed', 'true')
})

test('自動儲存還在路上時補打的字，換題卸載後仍會存到', async () => {
  const { puts, view, stored } = mockServer('ok', 400)
  const box = await screen.findByDisplayValue('我的重要筆記')
  fireEvent.change(box, { target: { value: '第一段' } })
  await sleep(1100) // 停 1 秒，自動儲存送出、還在路上
  fireEvent.change(box, { target: { value: '第一段，第二段' } })
  fireEvent.blur(box)
  view.unmount()
  await sleep(1000)
  expect(puts.map((body) => body.note)).toEqual(['第一段', '第一段，第二段'])
  expect(stored.note).toBe('第一段，第二段')
})

test('打字後 1 秒內卸載（沒有離開輸入框）也會把草稿存起來', async () => {
  const { puts, view } = mockServer('ok')
  const box = await screen.findByDisplayValue('我的重要筆記')
  fireEvent.change(box, { target: { value: '考試時間到前寫的筆記' } })
  await sleep(300)
  view.unmount()
  await sleep(100)
  expect(puts).toEqual([{ note: '考試時間到前寫的筆記' }])
})

test('儲存後讓列印頁的批次筆記快取失效', async () => {
  const { queryClient } = mockServer('ok')
  queryClient.setQueryData(['notes', 'batch', '1'], [{ question_id: 1, note: '我的重要筆記' }])
  const box = await screen.findByDisplayValue('我的重要筆記')
  fireEvent.change(box, { target: { value: '新筆記' } })
  fireEvent.blur(box)
  await waitFor(() => expect(queryClient.getQueryState(['notes', 'batch', '1'])?.isInvalidated).toBe(true))
})
