import type { FeatureDefinition } from '@/app/types'
import { DailyPage, MasteredWordsPage, WordsPage, WrongWordsPage } from './VocabPages'

export const feature: FeatureDefinition = {
  id: 'vocab',
  routes: [
    { path: 'vocab', element: <DailyPage /> },
    { path: 'vocab/wrong', element: <WrongWordsPage /> },
    { path: 'vocab/mastered', element: <MasteredWordsPage /> },
    { path: 'vocab/words', element: <WordsPage /> },
  ],
  nav: { label: '單字', path: '/vocab', icon: 'vocab', order: 3, primary: true },
}
