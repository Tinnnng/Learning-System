import type { FeatureDefinition } from '@/app/types'
import { PrintPage } from './PrintPage'
import { WrongBookPage } from './WrongBookPage'

export const feature: FeatureDefinition = {
  id: 'review',
  routes: [
    { path: 'review', element: <WrongBookPage /> },
    { path: 'review/print', element: <PrintPage />, handle: { focus: true } },
  ],
  nav: { label: '錯題本', path: '/review', icon: 'wrong', order: 2, primary: true },
}
