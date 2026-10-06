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

export function extractFromFile(file: File, examsOnly: boolean) {
  const form = new FormData()
  form.append('image', file)
  form.append('exams_only', String(examsOnly))
  return api.postForm<ExtractResult>('/calendar/extract', form)
}

export const ICS_URL = '/api/calendar/export.ics'

export type Subscription = components['schemas']['SubscriptionOut']
export type SyncResult = components['schemas']['SyncResult']
export type PresetList = components['schemas']['PresetList']

export const fetchSubscriptions = () => api.get<Subscription[]>('/calendar/subscriptions')
export const fetchPresets = () => api.get<PresetList>('/calendar/subscriptions/presets')
export const subscribe = (data: { url: string; name?: string | null; include_deadlines: boolean }) =>
  api.post<SyncResult>('/calendar/subscriptions', data)
export const syncSubscription = (id: number) => api.post<SyncResult>(`/calendar/subscriptions/${id}/sync`)
export const unsubscribe = (id: number) => api.delete<null>(`/calendar/subscriptions/${id}`)
