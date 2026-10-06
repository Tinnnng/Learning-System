import { api } from '@/lib/api'
import type { ItemOut, SessionOut } from '@/lib/types'

export const fetchSession = (id: number) => api.get<SessionOut>(`/exam/sessions/${id}`)

export const answerItem = (sessionId: number, position: number, response: string[], timeSpent?: number) =>
  api.put<ItemOut>(`/exam/sessions/${sessionId}/items/${position}`, {
    response,
    time_spent_seconds: timeSpent,
  })

export const submitSession = (id: number) => api.post<SessionOut>(`/exam/sessions/${id}/submit`)

export const deleteSession = (id: number) => api.delete<null>(`/exam/sessions/${id}`)
