import { api } from '@/lib/api'
import type { Overview, PaperSummary, SessionSummary, VocabStats } from '@/lib/types'

export const fetchVocabStats = () => api.get<VocabStats>('/vocab/stats')
export const fetchOverview = () => api.get<Overview>('/review/overview')
export const fetchSessions = (status?: 'open' | 'submitted') =>
  api.get<SessionSummary[]>(`/exam/sessions${status ? `?status=${status}&limit=6` : '?limit=6'}`)
export const fetchPapers = () => api.get<PaperSummary[]>('/bank/papers')
