/** 題目收藏與筆記的快取。列表頁先 prefetchNotes 一次取多題，NoteControls 就不會每題各發一次請求。 */

import type { QueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { components } from './api-types'

export type Note = components['schemas']['NoteOut']

export const noteKey = (questionId: number) => ['notes', 'question', questionId]

export async function prefetchNotes(queryClient: QueryClient, questionIds: number[]) {
  if (questionIds.length === 0) return
  const query = questionIds.map((id) => `ids=${id}`).join('&')
  const notes = await api.get<Note[]>(`/notes/questions?${query}`)
  for (const note of notes) queryClient.setQueryData(noteKey(note.question_id), note)
}
