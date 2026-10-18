import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import type { FilterOptions, WrongQuestionOut } from '@/lib/types'

export type WrongStatus = 'active' | 'mastered' | 'all'
export type QuestionHistory = components['schemas']['QuestionHistory']
export type AttemptOut = components['schemas']['AttemptOut']
export type MasteryRules = components['schemas']['MasteryRules']

export const fetchWrongQuestions = (status: WrongStatus, subject: string | null) => {
  const params = new URLSearchParams({ status })
  if (subject) params.set('subject', subject)
  return api.get<WrongQuestionOut[]>(`/review/wrong-questions?${params}`)
}

export const fetchHistory = (questionId: number) => api.get<QuestionHistory>(`/review/questions/${questionId}/history`)
export const fetchRules = () => api.get<MasteryRules>('/review/rules')
export const fetchFilters = () => api.get<FilterOptions>('/bank/filters')
