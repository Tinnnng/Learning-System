import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '@/lib/api'
import { TopicsPage } from './TopicsPage'

const overview = (tagged: number) => ({
  subjects: [{ subject: '行政法', questions: 5, tagged, estimated_calls: tagged < 5 ? 2 : 0, topics: [] }],
  weak: [],
  weak_accuracy: 0.6,
  weak_min_attempts: 3,
})

afterEach(() => vi.restoreAllMocks())

describe('TopicsPage', () => {
  it('refetches the overview after tagging fails, so batches already saved show up', async () => {
    let tagged = 0
    const get = vi.spyOn(api, 'get').mockImplementation(async () => overview(tagged))
    vi.spyOn(api, 'post').mockImplementation(async () => {
      tagged = 3 // 前面的批次已經存好，後面的批次失敗
      throw new ApiError(502, 'AI 回傳的格式看不懂，請再試一次')
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <TopicsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /AI 標記知識點/ }))
    await screen.findByText('AI 回傳的格式看不懂，請再試一次')
    await waitFor(() => expect(screen.getByText(/已標記 3／5 題/)).toBeTruthy())
    expect(get.mock.calls.filter(([path]) => path === '/topics').length).toBeGreaterThanOrEqual(2)
  })
})
