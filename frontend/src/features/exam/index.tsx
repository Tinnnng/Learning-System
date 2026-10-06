import type { FeatureDefinition } from '@/app/types'
import { ExamPage } from './ExamPage'

export const feature: FeatureDefinition = {
  id: 'exam',
  routes: [{ path: 'exam/:sessionId', element: <ExamPage />, handle: { focus: true } }],
}
