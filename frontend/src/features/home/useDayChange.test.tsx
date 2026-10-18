import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { useDayChange } from './useDayChange'

afterEach(() => vi.useRealTimers())

it('首頁開著過了午夜，會重新抓資料並換成新的日期', () => {
  vi.useFakeTimers({ now: new Date('2026-10-17T23:59:30+08:00') })
  const client = new QueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const { result } = renderHook(() => useDayChange(), { wrapper })
  expect(result.current).toBe('2026-10-17')

  act(() => void vi.advanceTimersByTime(30_000)) // 還沒到下一次檢查：不重抓
  expect(invalidate).not.toHaveBeenCalled()
  act(() => void vi.advanceTimersByTime(30_000))
  expect(invalidate).toHaveBeenCalledTimes(1)
  expect(result.current).toBe('2026-10-18')
})
