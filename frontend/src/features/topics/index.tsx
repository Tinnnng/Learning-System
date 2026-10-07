import type { FeatureDefinition } from '@/app/types'
import { TopicsPage } from './TopicsPage'

export const feature: FeatureDefinition = {
  id: 'topics',
  routes: [{ path: 'topics', element: <TopicsPage /> }],
  nav: { label: '弱點', path: '/topics', icon: 'flag', order: 5.5 },
}
