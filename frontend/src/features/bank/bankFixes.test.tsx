/** 2026-10-17 全服務稽核找到的 bank 前端 bug 回歸測試 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PaperSummary } from '@/lib/types'
import { groupFilter, groupPapers, groupPath } from './groups'
import { PaperRow } from './PaperRow'
import { StartPanel } from './StartPanel'

const paper = (id: number, overrides: Partial<PaperSummary>): PaperSummary => ({
  id,
  source_key: `p${id}`,
  origin: 'manual',
  exam_type: '期中考',
  year: null,
  subject: '資料結構',
  title: null,
  categories: [],
  duration_minutes: null,
  question_count: 0,
  essay_count: 0,
  ...overrides,
})

afterEach(() => vi.restoreAllMocks())

describe('bank 稽核修正', () => {
  it('沒有年度、沒有類科的組會明確要求「沒有」，不會混進其他試卷', () => {
    const groups = groupPapers([paper(1, {}), paper(2, { year: 114 }), paper(3, { year: 114, categories: ['資工系'] })])
    const noYear = groups.find((group) => group.year === null)!
    expect(groupFilter(noYear)).toMatchObject({ year: null, no_year: true, no_category: true, subject: '資料結構' })
    const withCategory = groups.find((group) => group.category === '資工系')!
    expect(groupFilter(withCategory)).toMatchObject({ no_year: false, no_category: false, subject: null })
    // 網址只放原本的四個欄位，分組頁讀回來會自己算出「沒有」的條件
    expect(groupPath(noYear)).toBe(`/bank/group?exam_type=${encodeURIComponent('期中考')}&subject=${encodeURIComponent('資料結構')}`)
  })

  it('還沒有題目的試卷顯示「0 題」，不是「申論 0 題」', () => {
    render(
      <MemoryRouter>
        <ul>
          <PaperRow paper={paper(1, {})} />
        </ul>
      </MemoryRouter>,
    )
    expect(document.body.textContent).toContain('0 題')
    expect(document.body.textContent).not.toContain('申論 0 題')
  })

  it('關掉申論題讓題數選項變少時，回到「全部」', async () => {
    const calls: { count: number | null; shuffle_questions: boolean }[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
      calls.push(JSON.parse(String(init?.body)))
      return new Response('{"detail":"x"}', { status: 400, headers: { 'content-type': 'application/json' } })
    })
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <StartPanel filter={{ paper_ids: [1] }} questionCount={25} essayCount={10} />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    fireEvent.click(screen.getByRole('switch', { name: /包含申論題/ }))
    fireEvent.click(screen.getByRole('radio', { name: /30 題/ }))
    fireEvent.click(screen.getByRole('switch', { name: /包含申論題/ }))
    expect(screen.getByRole('radio', { name: /全部 25/ }).getAttribute('aria-checked')).toBe('true')
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /開始練習/ }))
    })
    expect(calls[0]).toMatchObject({ count: null, shuffle_questions: false })
  })
})
