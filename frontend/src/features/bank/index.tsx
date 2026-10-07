import type { FeatureDefinition } from '@/app/types'
import { BankPage } from './BankPage'
import { PaperPage } from './PaperPage'
import { SearchPage } from './SearchPage'

export const feature: FeatureDefinition = {
  id: 'bank',
  routes: [
    { path: 'bank', element: <BankPage /> },
    { path: 'bank/papers/:paperId', element: <PaperPage /> },
    { path: 'bank/search', element: <SearchPage /> },
  ],
  nav: { label: '題庫', path: '/bank', icon: 'bank', order: 1, primary: true },
}
