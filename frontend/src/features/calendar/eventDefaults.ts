import type { EventIn } from './api'

export const KIND_LABELS: Record<EventIn['kind'] & string, string> = { exam: '考試', deadline: '期限', other: '其他' }

export function emptyEvent(date: string): EventIn {
  return { title: '', kind: 'exam', date, time: null, end_date: null, location: null, subject: null, note: null }
}
