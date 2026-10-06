import type { FeatureDefinition } from '@/app/types'
import { NotesPage } from './NotesPage'

export const feature: FeatureDefinition = {
  id: 'notes',
  routes: [{ path: 'notes', element: <NotesPage /> }],
  nav: { label: '收藏', path: '/notes', icon: 'star', order: 6 },
}
