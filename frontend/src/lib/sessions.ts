/** 建立測驗：題庫、錯題本、首頁都會用到，所以放在共用的 lib。 */

import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { api } from './api'
import type { SessionCreate, SessionOut } from './types'

export const createSession = (data: Partial<SessionCreate>) => api.post<SessionOut>('/exam/sessions', data)

/** 建立後直接進入作答頁。 */
export function useStartSession() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: createSession,
    onSuccess: (session) => navigate(`/exam/${session.id}`),
  })
}
