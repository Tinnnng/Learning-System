import type { FeatureDefinition } from '@/app/types'
import { HomePage } from './HomePage'

export const feature: FeatureDefinition = {
  id: 'home',
  routes: [{ index: true, element: <HomePage /> }],
  nav: { label: '今日', path: '/', icon: 'home', order: 0, primary: true },
}
