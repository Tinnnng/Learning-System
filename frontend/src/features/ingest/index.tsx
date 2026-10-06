import type { FeatureDefinition } from '@/app/types'
import { ImportListPage, ImportPreviewPage } from './ImportPages'

export const feature: FeatureDefinition = {
  id: 'ingest',
  routes: [
    { path: 'import', element: <ImportListPage /> },
    { path: 'import/:name', element: <ImportPreviewPage /> },
  ],
  nav: { label: '匯入', path: '/import', icon: 'import', order: 7 },
}
