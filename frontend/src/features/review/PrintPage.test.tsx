import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'
import { PrintPage } from './PrintPage'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const wrongEntry = {
  question: {
    id: 1,
    number: 1,
    label: null,
    type: 'single_choice',
    passage: null,
    stem: '題幹',
    options: ['甲', '乙'],
    answer: ['A'],
    explanation: null,
    assets: [],
    paper: { year: 115, exam_type: '普考', subject: '測試科目' },
  },
  progress: {},
}

test('列印頁每次打開都重抓筆記，30 秒內重印也不會印出舊筆記', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.startsWith('/api/review/wrong-questions')) return new Response(JSON.stringify([wrongEntry]))
      if (url.startsWith('/api/notes/questions?')) return new Response(JSON.stringify([{ question_id: 1, starred: false, note: '新筆記', updated_at: null }]))
      return new Response(JSON.stringify({}))
    }),
  )
  const print = vi.fn()
  vi.stubGlobal('print', print)
  Object.defineProperty(document, 'fonts', { value: { ready: Promise.resolve() }, configurable: true })
  // main.tsx 的預設值：30 秒內快取都算新的
  const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: false } } })
  queryClient.setQueryData(['notes', 'batch', '1'], [{ question_id: 1, starred: false, note: '舊筆記', updated_at: null }])

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PrintPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(await screen.findByText('筆記：新筆記')).toBeInTheDocument()
  expect(screen.queryByText('筆記：舊筆記')).not.toBeInTheDocument()
  await waitFor(() => expect(print).toHaveBeenCalledTimes(1))
})
