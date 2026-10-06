import type { FeatureDefinition } from '@/app/types'
import { OverviewPage } from './OverviewPage'

export const feature: FeatureDefinition = {
  id: 'overview',
  routes: [{ path: 'overview', element: <OverviewPage /> }],
  nav: { label: '總覽', path: '/overview', icon: 'overview', order: 5 },
}
