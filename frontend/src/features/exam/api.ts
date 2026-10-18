import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import type { ItemOut, SessionOut } from '@/lib/types'

export type MasteryRules = components['schemas']['MasteryRules']

/** 模擬考截止時刻（瀏覽器時鐘的毫秒）：抓到試卷的當下用剩餘秒數換算。
 * 作答頁的資料會留在快取裡，離開幾分鐘再回來時，不能再拿快取裡的剩餘秒數重新倒數。 */
const deadlines = new Map<number, number>()
export const sessionDeadline = (id: number) => deadlines.get(id)

export const fetchSession = async (id: number) => {
  const session = await api.get<SessionOut>(`/exam/sessions/${id}`)
  if (session.remaining_seconds !== null && session.remaining_seconds !== undefined) {
    deadlines.set(id, Date.now() + session.remaining_seconds * 1000)
  }
  return session
}

/** 錯題本規則（申論題幾成算及格、低於幾成進錯題本），和 review 共用同一份快取 */
export const fetchRules = () => api.get<MasteryRules>('/review/rules')

export const answerItem = (sessionId: number, position: number, response: string[], timeSpent?: number) =>
  api.put<ItemOut>(`/exam/sessions/${sessionId}/items/${position}`, {
    response,
    time_spent_seconds: timeSpent,
  })

export const submitSession = (id: number) => api.post<SessionOut>(`/exam/sessions/${id}/submit`)

export const deleteSession = (id: number) => api.delete<null>(`/exam/sessions/${id}`)
