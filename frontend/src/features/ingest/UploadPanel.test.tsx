import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeAll, expect, test, vi } from 'vitest'
import { UploadPanel } from './UploadPanel'

const paper = {
  source_key: 'gaopu-115080-4401',
  subject: '測試科目',
  exam_type: '普考',
  year: 115,
  categories: ['一般行政'],
  has_question: true,
  has_answer: true,
  kind: 'choice',
  pages: 2,
  converted: false,
  reviewed: false,
  estimated_calls: 2,
}
const lecture = { name: '教材.pdf', source_key: 'lecture-upload-x', converted: false, size_bytes: 100 }
const done = { file: 'gaopu-115080-4401.json', report: { source_key: 'x', subject: 's', question_count: 2, issues: [], ok: true }, calls: 0, cost_usd: 0 }

const json = (status: number, body: unknown) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

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
  vi.unstubAllGlobals()
})

function renderPanel(convert: (useAi: boolean) => Promise<Response>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      if (url.startsWith('/api/ingest/uploads/papers/')) return convert(JSON.parse(String(init?.body)).use_ai)
      if (url.includes('/estimate')) return json(200, { calls: 2 })
      if (url.startsWith('/api/ingest/uploads')) return json(200, { papers: [paper], lectures: [lecture] })
      return json(200, {})
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <UploadPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('AI 轉檔失敗後改按自動轉檔成功，舊的錯誤訊息要清掉', async () => {
  renderPanel((useAi) => (useAi ? json(503, { detail: 'AI 程序逾時' }) : json(200, done)))
  fireEvent.click(await screen.findByRole('button', { name: /AI 校對後轉檔/ }))
  fireEvent.click(await screen.findByRole('button', { name: '開始校對' }))
  await screen.findByText('AI 程序逾時')
  fireEvent.click(screen.getByRole('button', { name: /自動轉檔/ }))
  await screen.findByText(/轉好了/)
  expect(screen.queryByText('AI 程序逾時')).not.toBeInTheDocument()
})

test('教材題數輸入框刪光再打 20，不會變成 120', async () => {
  renderPanel(() => json(200, done))
  fireEvent.click(await screen.findByRole('button', { name: /AI 出題/ }))
  const input = await screen.findByLabelText('題數')
  fireEvent.change(input, { target: { value: '' } })
  expect(input).toHaveValue(null)
  fireEvent.change(input, { target: { value: '20' } })
  expect(input).toHaveValue(20)
  fireEvent.change(input, { target: { value: '0' } })
  fireEvent.blur(input)
  expect(input).toHaveValue(1)
})
