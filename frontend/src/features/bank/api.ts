import { api } from '@/lib/api'
import type { FilterOptions, PaperDetail, PaperSummary } from '@/lib/types'

export interface PaperFilters {
  exam_type?: string | null
  year?: number | null
  category?: string | null
  subject?: string | null
  origin?: string | null
}

const query = (filters: PaperFilters) => {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== null && value !== undefined && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const fetchPapers = (filters: PaperFilters) => api.get<PaperSummary[]>(`/bank/papers${query(filters)}`)
export const fetchPaper = (id: number) => api.get<PaperDetail>(`/bank/papers/${id}`)
export const fetchFilters = () => api.get<FilterOptions>('/bank/filters')
