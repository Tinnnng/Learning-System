import { api } from '@/lib/api'
import type { FilterOptions, WrongQuestionOut } from '@/lib/types'

export type WrongStatus = 'active' | 'mastered' | 'all'

export interface QuestionHistory {
  attempts: Array<{ is_correct: boolean; response: string[]; answered_at: string; time_spent_seconds: number | null }>
}

export const fetchWrongQuestions = (status: WrongStatus, subject: string | null) => {
  const params = new URLSearchParams({ status })
  if (subject) params.set('subject', subject)
  return api.get<WrongQuestionOut[]>(`/review/wrong-questions?${params}`)
}

export const fetchHistory = (questionId: number) => api.get<QuestionHistory>(`/review/questions/${questionId}/history`)
export const fetchFilters = () => api.get<FilterOptions>('/bank/filters')
