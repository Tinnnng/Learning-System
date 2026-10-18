import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { AiTutor } from '@/components/AiTutor'

const empty = { question_id: 1, messages: [], cost_usd: 0 }
const withChat = {
  question_id: 1,
  cost_usd: 0.001,
  messages: [
    { id: 1, role: 'user', kind: 'chat', content: '為什麼 B 不對', flagged: false, created_at: '2026-10-17T00:00:00' },
    { id: 2, role: 'assistant', kind: 'chat', content: '因為 B 是錯的', flagged: false, created_at: '2026-10-17T00:00:00' },
  ],
}
const explained = {
  question_id: 1,
  cost_usd: 0.001,
  messages: [{ id: 3, role: 'assistant', kind: 'explanation', content: '詳解內容', flagged: false, created_at: '2026-10-17T00:00:00' }],
}
const json = (status: number, body: unknown) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

type Handler = (url: string, method: string, body: Record<string, unknown>) => Promise<Response>

function setup(post: Handler) {
  const bodies: { url: string; body: Record<string, unknown> }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url.startsWith('/api/ai/status')) return json(200, { month_cost_usd: 0, month_calls: 0, model: 'fake' })
      if (method === 'GET') return json(200, empty)
      const body = init?.body ? JSON.parse(String(init.body)) : {}
      bodies.push({ url, body })
      return post(url, method, body)
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <AiTutor questionId={1} myAnswer={['C']} />
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: /AI 助教/ }))
  return bodies
}

async function askQuestion(text: string) {
  const input = await screen.findByLabelText('追問 AI 助教')
  fireEvent.change(input, { target: { value: text } })
  await act(async () => {
    fireEvent.submit(input.closest('form')!)
  })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('詳解被中斷後追問成功，不再顯示舊的「已中斷」', async () => {
  setup((url) => (url.endsWith('/explain') ? json(409, { detail: '已中斷' }) : json(200, withChat)))
  fireEvent.click(await screen.findByRole('button', { name: /請 AI 詳解這題/ }))
  await screen.findByText('已中斷，這次沒有產生內容。')
  await askQuestion('為什麼 B 不對')
  await screen.findByText('因為 B 是錯的')
  expect(screen.queryByText('已中斷，這次沒有產生內容。')).not.toBeInTheDocument()
})

test('追問失敗後改按詳解成功，不再顯示舊的追問錯誤', async () => {
  setup((url) => (url.endsWith('/messages') ? json(503, { detail: 'AI 程序逾時' }) : json(200, explained)))
  await askQuestion('問題')
  await screen.findByText('AI 程序逾時')
  fireEvent.click(screen.getByRole('button', { name: /請 AI 詳解這題/ }))
  await screen.findByText('詳解內容')
  expect(screen.queryByText('AI 程序逾時')).not.toBeInTheDocument()
})

test('共用的詳解不送個人作答，追問才帶', async () => {
  const bodies = setup((url) => json(200, url.endsWith('/explain') ? explained : withChat))
  fireEvent.click(await screen.findByRole('button', { name: /請 AI 詳解這題/ }))
  await screen.findByText('詳解內容')
  await askQuestion('為什麼 B 不對')
  await screen.findByText('因為 B 是錯的')
  const explainBody = bodies.find((entry) => entry.url.endsWith('/explain'))!.body
  const askBody = bodies.find((entry) => entry.url.endsWith('/messages'))!.body
  expect(explainBody).not.toHaveProperty('my_answer')
  expect(askBody.my_answer).toEqual(['C'])
})
