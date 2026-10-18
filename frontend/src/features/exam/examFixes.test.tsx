/** 2026-10-17 全服務稽核找到的 exam 前端 bug 回歸測試，以及「時間到只提醒、不自動交卷」 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import type { ItemOut, SessionOut } from '@/lib/types'
import { EssayAnswer } from './EssayAnswer'
import { ExamPage } from './ExamPage'
import { ResultView } from './ResultView'

const RULES = { mastery_streak: 5, essay_mastery_streak: 2, essay_pass_ratio: 0.8, essay_wrong_ratio: 0.6 }

const choice = (position: number, overrides: Partial<ItemOut> = {}): ItemOut => ({
  position,
  question_id: position,
  type: 'single_choice',
  label: null,
  passage: null,
  stem: `題幹 ${position}`,
  options: ['甲', '乙', '丙', '丁'],
  assets: [],
  page_snapshot: null,
  source_ref: null,
  tags: [],
  paper: { id: 1, exam_type: '普考', subject: '科目', year: 115 } as never,
  points: 2,
  response: null,
  answered: false,
  revealed: false,
  is_correct: null,
  correct: null,
  explanation: null,
  original_response: null,
  time_spent_seconds: null,
  text: null,
  rubric: null,
  graded: false,
  rubric_hits: null,
  score: null,
  ai_hits: null,
  ai_feedback: null,
  ...overrides,
})

const essay = (position: number, overrides: Partial<ItemOut> = {}): ItemOut =>
  choice(position, {
    type: 'essay',
    options: [],
    points: 10,
    rubric: [
      { text: '要點一', points: 7 },
      { text: '要點二', points: 3 },
    ],
    ...overrides,
  })

const session = (overrides: Partial<SessionOut> = {}): SessionOut => ({
  id: 1,
  mode: 'mock',
  title: '測試（模擬考）',
  settings: {},
  started_at: '2026-10-17T00:00:00',
  submitted_at: null,
  duration_minutes: 60,
  remaining_seconds: 3600,
  total: 1,
  answered_count: 0,
  max_score: 2,
  result: null,
  items: [choice(1)],
  ...overrides,
})

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })
const client = () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: false, refetchOnWindowFocus: false } } })

function examPage(queryClient: QueryClient) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/exam/1']}>
        <Routes>
          <Route path="/exam/:sessionId" element={<ExamPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// jsdom 沒有實作 <dialog> 的 showModal／close
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
  }
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('模擬考計時', () => {
  it('離開作答頁幾分鐘再回來，倒數從截止時刻算，不從快取的剩餘秒數重來', async () => {
    let now = 1_000_000
    vi.spyOn(Date, 'now').mockImplementation(() => now)
    vi.stubGlobal('fetch', vi.fn(async () => json(session())))
    const queryClient = client()
    const first = render(examPage(queryClient))
    expect((await screen.findAllByRole('timer'))[0]).toHaveTextContent('1:00:00')
    first.unmount()

    now += 3 * 60 * 1000
    render(examPage(queryClient))
    expect((await screen.findAllByRole('timer'))[0]).toHaveTextContent('57:00')
  })

  it('時間到只提醒、不自動交卷，計時器改成顯示已超時', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => json(session({ remaining_seconds: -125 })))
    vi.stubGlobal('fetch', fetchMock)
    render(examPage(client()))
    expect(await screen.findByRole('alert')).toHaveTextContent('考試時間到了。可以繼續作答')
    expect(screen.getAllByRole('timer')[0]).toHaveTextContent('超時+2:05')
    const submits = fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'POST')
    expect(submits).toHaveLength(0)
    fireEvent.click(screen.getByText('知道了'))
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('作答', () => {
  it('整份試卷模式：上一題還在送出時，點別題照樣送出', async () => {
    localStorage.setItem('ls-exam-view', 'sheet')
    const puts: string[] = []
    const releases: (() => void)[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === 'PUT') {
          puts.push(String(url))
          const position = Number(String(url).split('/').pop())
          await new Promise<void>((resolve) => releases.push(resolve))
          return json(choice(position, { response: ['A'], answered: true }))
        }
        return json(session({ total: 2, items: [choice(1), choice(2)] }))
      }),
    )
    render(examPage(client()))
    await screen.findByText('題幹 2')
    fireEvent.click(screen.getAllByText('甲')[0])
    fireEvent.click(screen.getAllByText('甲')[1])
    await waitFor(() => expect(puts).toHaveLength(2))
    expect(puts.map((url) => url.split('/').pop())).toEqual(['1', '2'])
    await act(async () => releases.forEach((release) => release()))
    localStorage.removeItem('ls-exam-view')
  })

  it('申論題停止輸入不到 1 秒就交卷：先把草稿存起來再交卷', async () => {
    const calls: { method: string; url: string; body?: string }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ method: init?.method ?? 'GET', url: String(url), body: init?.body as string | undefined })
        if (init?.method === 'PUT') return json(essay(1, { text: '剛打的字', answered: true }))
        if (init?.method === 'POST') {
          const result = { score: 0, max_score: 10, correct_count: 0, answered_count: 1, total: 1, essay_pending: 1 }
          return json(session({ submitted_at: '2026-10-17T01:00:00', items: [essay(1, { text: '剛打的字' })], result }))
        }
        return json(session({ items: [essay(1)], max_score: 10 }))
      }),
    )
    render(examPage(client()))
    fireEvent.change(await screen.findByPlaceholderText(/在這裡寫你的答案/), { target: { value: '剛打的字' } })
    fireEvent.click(screen.getAllByRole('button', { name: '交卷' })[0])
    fireEvent.click(screen.getAllByRole('button', { name: '交卷' }).at(-1)!)
    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true))
    const put = calls.findIndex((call) => call.method === 'PUT' && call.body?.includes('剛打的字'))
    const post = calls.findIndex((call) => call.method === 'POST')
    expect(put).toBeGreaterThanOrEqual(0)
    expect(put).toBeLessThan(post)
  })
})

describe('申論題自評與結果', () => {
  it('修改自評後按「取消」，勾選回到上次確定的要點', () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(RULES)))
    const item = essay(1, { revealed: true, answered: true, text: '我的答案', graded: true, rubric_hits: [0], score: 7, is_correct: false })
    render(
      <QueryClientProvider client={client()}>
        <EssayAnswer item={item} sessionId={1} practice={false} submitted onUpdate={() => {}} />
      </QueryClientProvider>,
    )
    fireEvent.click(screen.getByText('修改自評'))
    fireEvent.click(screen.getAllByRole('checkbox')[1])
    fireEvent.click(screen.getByText('取消'))
    expect(screen.getAllByRole('checkbox').map((box) => (box as HTMLInputElement).checked)).toEqual([true, false])
    fireEvent.click(screen.getByText('修改自評'))
    expect(screen.getByText(/確定得分/)).toHaveTextContent('確定得分 7／10')
  })

  it('申論題拿 60%～80%：結果頁不算答錯，也不出現在「重寫錯題」', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(RULES)))
    const partial = essay(1, { answered: true, revealed: true, text: '答案', graded: true, rubric_hits: [0], score: 7, is_correct: false })
    const done = session({
      submitted_at: '2026-10-17T01:00:00',
      items: [partial],
      max_score: 10,
      result: { score: 7, max_score: 10, correct_count: 0, answered_count: 1, total: 1, essay_pending: 0 },
    })
    render(
      <QueryClientProvider client={client()}>
        <MemoryRouter>
          <ResultView session={done} />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(screen.getByRole('radio', { name: /答錯/ })).toHaveTextContent('答錯 0')
    expect(screen.queryByText(/重寫這次的/)).toBeNull()
    expect(await screen.findByText(/申論及格、未達/)).toBeInTheDocument()
  })

  it('沒作答的申論題評分後說明不會進錯題本', () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(RULES)))
    const item = essay(1, { revealed: true, graded: true, rubric_hits: [], score: 0, is_correct: false })
    render(
      <QueryClientProvider client={client()}>
        <EssayAnswer item={item} sessionId={1} practice submitted={false} onUpdate={() => {}} />
      </QueryClientProvider>,
    )
    expect(screen.getByText('沒有作答，不收進錯題本。')).toBeInTheDocument()
  })
})
