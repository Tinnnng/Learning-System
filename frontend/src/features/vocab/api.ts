import { api } from '@/lib/api'
import type {
  BuiltinList,
  DailyQuiz,
  ImportResult,
  QuizItem,
  VocabAnswerResult,
  VocabStats,
  WordOut,
  WordPage,
} from '@/lib/types'

export type QuizContext = 'daily' | 'wrong' | 'practice'
export type WordStatus = 'new' | 'learning' | 'wrong' | 'mastered'

export const fetchDaily = () => api.get<DailyQuiz>('/vocab/daily')
export const fetchStats = () => api.get<VocabStats>('/vocab/stats')
export const fetchWrongWords = () => api.get<WordOut[]>('/vocab/wrong')
export const fetchQuiz = (source: 'wrong' | 'due' | 'new' | 'all', count = 10) =>
  api.get<QuizItem[]>(`/vocab/quiz?source=${source}&count=${count}`)

export const answerWord = (item: QuizItem, response: string, context: QuizContext) =>
  api.post<VocabAnswerResult>('/vocab/answers', {
    word_id: item.word_id,
    quiz_type: item.quiz_type,
    response,
    context,
  })

export const fetchWords = (params: { search?: string; status?: WordStatus | null; offset?: number; limit?: number }) => {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  query.set('offset', String(params.offset ?? 0))
  query.set('limit', String(params.limit ?? 40))
  return api.get<WordPage>(`/vocab/words?${query}`)
}

export const fetchBuiltin = () => api.get<BuiltinList[]>('/vocab/builtin')
export const importBuiltin = (name: string) => api.post<ImportResult>(`/vocab/builtin/${name}/import`)

export function uploadWords(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.postForm<ImportResult>('/vocab/import', form)
}
