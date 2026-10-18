import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'
import { noteKey } from '@/lib/notes'
import { NotesPage } from './NotesPage'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const entry = (id: number, type: string, note: string | null, updatedAt: string) => ({
  question: {
    id,
    number: id,
    label: null,
    type,
    passage: null,
    stem: `第 ${id} 題`,
    options: type === 'essay' ? [] : ['甲', '乙'],
    answer: type === 'essay' ? [] : ['A'],
    explanation: null,
    rubric: null,
    assets: [],
    paper: { year: 115, exam_type: '普考', subject: '測試科目' },
  },
  note: { question_id: id, starred: true, note, updated_at: updatedAt },
})

function renderPage(list: unknown[], queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const posts: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        posts.push(JSON.parse(String(init.body)))
        return new Response(JSON.stringify({ detail: 'stop' }), { status: 400 })
      }
      if (url.startsWith('/api/notes/list')) return new Response(JSON.stringify(list))
      return new Response(JSON.stringify({}))
    }),
  )
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <NotesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { posts, queryClient }
}

test('收藏裡有申論題時，「練習收藏的題目」會帶上申論題', async () => {
  const { posts } = renderPage([entry(1, 'essay', null, '2026-01-01T00:00:00')])
  fireEvent.click(await screen.findByRole('button', { name: /練習收藏的題目/ }))
  await waitFor(() => expect(posts).toHaveLength(1))
  expect(posts[0]).toMatchObject({ source: { kind: 'starred' }, include_essay: true })
})

test('只有選擇題時不帶申論題', async () => {
  const { posts } = renderPage([entry(1, 'single_choice', null, '2026-01-01T00:00:00')])
  fireEvent.click(await screen.findByRole('button', { name: /練習收藏的題目/ }))
  await waitFor(() => expect(posts).toHaveLength(1))
  expect(posts[0]).toMatchObject({ include_essay: false })
})

test('列表比快取舊時，不會把快取裡比較新的筆記蓋回去', async () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(noteKey(1), { question_id: 1, starred: true, note: '剛改的新筆記', updated_at: '2026-01-02T00:00:00' })
  queryClient.setQueryData(noteKey(2), { question_id: 2, starred: true, note: '舊的', updated_at: '2026-01-01T00:00:00' })
  renderPage(
    [entry(1, 'single_choice', '列表裡的舊筆記', '2026-01-01T00:00:00'), entry(2, 'single_choice', '列表較新', '2026-01-03T00:00:00')],
    queryClient,
  )
  await screen.findByText('第 1 題')
  await waitFor(() => expect(queryClient.getQueryData<{ note: string }>(noteKey(2))?.note).toBe('列表較新'))
  expect(queryClient.getQueryData<{ note: string }>(noteKey(1))?.note).toBe('剛改的新筆記')
})
