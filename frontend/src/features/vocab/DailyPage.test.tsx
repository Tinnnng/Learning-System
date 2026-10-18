/** 2026-10-17 稽核找到的每日單字前端 bug 回歸測試。 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeAll, beforeEach, expect, test, vi } from 'vitest'
import { ApiError } from '@/lib/api'

const mk = (prefix: string) =>
  Array.from({ length: 5 }, (_, i) => ({
    word_id: prefix === 'a' ? i + 1 : i + 101,
    quiz_type: 'en_to_zh',
    prompt: `${prefix}word${i}`,
    part_of_speech: null,
    options: [`${prefix}m${i}`, 'x1', 'x2', 'x3'],
    hint: null,
    answered: false,
    is_correct: null,
  }))
const state = { set: 'a' as 'a' | 'b' | 'empty', conflict: false }

vi.mock('@/features/vocab/api', () => ({
  fetchDaily: vi.fn(async () =>
    state.set === 'empty'
      ? { day: '2026-10-17', items: [], done: 0, total: 0, word_count: 12 }
      : { day: '2026-10-17', items: mk(state.set), done: 0, total: 5, word_count: 10 },
  ),
  fetchStats: vi.fn(async () => ({ total: 10, studied: 0, wrong_list: 0, mastered: 0, due_today: 0, daily_done: 0, daily_total: 5 })),
  fetchWrongWords: vi.fn(async () => []),
  fetchQuiz: vi.fn(async () => []),
  fetchWords: vi.fn(),
  fetchBuiltin: vi.fn(async () => []),
  importBuiltin: vi.fn(),
  uploadWords: vi.fn(),
  resetVocab: vi.fn(async () => {
    state.set = 'b'
    return { words: 2, backup: 'x.zip' }
  }),
  answerWord: vi.fn(async (item: { word_id: number; options: string[] }, response: string) => {
    if (state.conflict) throw new ApiError(409, '今天的每日複習已經作答過這個單字')
    return {
      is_correct: response === item.options[0],
      expected: item.options[0],
      word: { id: item.word_id, term: 't', meaning: item.options[0], part_of_speech: null, example: null, example_translation: null, tags: [], source: null, status: 'learning', progress: null, review_due: null },
    }
  }),
}))

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
  }
})

beforeEach(() => {
  state.set = 'a'
  state.conflict = false
})

async function renderDaily() {
  const { DailyPage } = await import('@/features/vocab/VocabPages')
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DailyPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('清除單字進度後，每日單字從新一組的第 1 題開始', async () => {
  await renderDaily()
  for (const i of [0, 1]) {
    await screen.findByText(`aword${i}`)
    fireEvent.click(screen.getByText(`am${i}`))
    fireEvent.click(await screen.findByRole('button', { name: /下一個/ }))
  }
  await screen.findByText('aword2')
  fireEvent.click(screen.getByRole('button', { name: /清除單字進度/ }))
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: '清除進度', hidden: true }))
  })
  await screen.findByText('bword0')
  expect(document.querySelector('[role="img"][aria-label^="第"]')?.getAttribute('aria-label')).toBe('第 1 個，共 5 個')
})

test('單字都學會了：不顯示「單字庫是空的」', async () => {
  state.set = 'empty'
  await renderDaily()
  await screen.findByText('單字庫的字都學會了')
  expect(screen.queryByText('單字庫是空的')).toBeNull()
})

test('別的分頁已經寫過這個字（409）：可以跳過，繼續下一個', async () => {
  state.conflict = true
  await renderDaily()
  await screen.findByText('aword0')
  fireEvent.click(screen.getByText('am0'))
  fireEvent.click(await screen.findByRole('button', { name: /跳過這個/ }))
  await waitFor(() => expect(screen.getByText('aword1')).toBeTruthy())
})
