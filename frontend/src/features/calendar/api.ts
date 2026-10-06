import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'

export type EventOut = components['schemas']['EventOut']
export type EventIn = components['schemas']['EventIn']
export type ExtractResult = components['schemas']['ExtractResult']
export type Countdown = components['schemas']['Countdown']

export const fetchEvents = (start: string, end: string) => api.get<EventOut[]>(`/calendar/events?start=${start}&end=${end}`)
export const fetchCountdown = () => api.get<Countdown>('/calendar/countdown')
export const createEvent = (data: EventIn, source: 'manual' | 'photo' = 'manual') =>
  api.post<EventOut>(`/calendar/events?source=${source}`, data)
export const updateEvent = (id: number, data: EventIn) => api.put<EventOut>(`/calendar/events/${id}`, data)
export const deleteEvent = (id: number) => api.delete<null>(`/calendar/events/${id}`)

export function extractFromImage(file: File) {
  const form = new FormData()
  form.append('image', file)
  return api.postForm<ExtractResult>('/calendar/extract', form)
}

export const ICS_URL = '/api/calendar/export.ics'
