import type { FeatureDefinition } from '@/app/types'
import { WrongBookPage } from './WrongBookPage'

export const feature: FeatureDefinition = {
  id: 'review',
  routes: [{ path: 'review', element: <WrongBookPage /> }],
  nav: { label: '錯題本', path: '/review', icon: 'wrong', order: 2, primary: true },
}
