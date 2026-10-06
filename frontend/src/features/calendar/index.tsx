import type { FeatureDefinition } from '@/app/types'
import { CalendarPage } from './CalendarPage'

export const feature: FeatureDefinition = {
  id: 'calendar',
  routes: [{ path: 'calendar', element: <CalendarPage /> }],
  nav: { label: '行事曆', path: '/calendar', icon: 'today', order: 4, primary: true },
}
