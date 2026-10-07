import type { FeatureDefinition } from '@/app/types'
import { BackupPage } from './BackupPage'

export const feature: FeatureDefinition = {
  id: 'backup',
  routes: [{ path: 'backup', element: <BackupPage /> }],
  nav: { label: '備份', path: '/backup', icon: 'archive', order: 8 },
}
