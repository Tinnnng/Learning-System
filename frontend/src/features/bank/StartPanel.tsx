/** 出題設定：模式、題數、是否打亂。題庫列表（依篩選）與試卷詳情共用。 */

import { useState } from 'react'
import { Button } from '@/components/Button'
import { Segmented, Switch } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'
import { useStartSession } from '@/lib/sessions'
import type { QuestionFilter } from '@/lib/types'

interface StartPanelProps {
  filter: Partial<QuestionFilter>
  questionCount: number
  /** 整份試卷的考試時間（分鐘），模擬考預設用這個 */
  durationMinutes?: number | null
  title?: string
}

type CountChoice = 'all' | '10' | '20' | '30'

export function StartPanel({ filter, questionCount, durationMinutes, title }: StartPanelProps) {
  const [mode, setMode] = useState<'practice' | 'mock'>('practice')
  const [countChoice, setCountChoice] = useState<CountChoice>('all')
  const [shuffleQuestions, setShuffleQuestions] = useState(false)
  const [shuffleOptions, setShuffleOptions] = useState(false)
  const start = useStartSession()

  const count = countChoice === 'all' ? null : Math.min(Number(countChoice), questionCount)
  const countOptions = (['all', '10', '20', '30'] as const)
    .filter((choice) => choice === 'all' || Number(choice) < questionCount)
    .map((choice) => ({ value: choice, label: choice === 'all' ? `全部 ${questionCount}` : `${choice} 題` }))
  const fullPaper = countChoice === 'all' && durationMinutes

  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault()
        start.mutate({
          mode,
          title: title ? `${title}（${mode === 'mock' ? '模擬考' : '練習'}）` : undefined,
          source: { kind: 'filter', filter: { ...filter, types: ['single_choice', 'multi_choice'] } },
          count,
          shuffle_questions: shuffleQuestions || count !== null,
          shuffle_options: shuffleOptions,
          duration_minutes: mode === 'mock' && !fullPaper ? Math.max(5, Math.round((count ?? questionCount) * 1.2)) : null,
        })
      }}
    >
      <Segmented
        label="作答模式"
        value={mode}
        onChange={setMode}
        options={[
          { value: 'practice', label: '練習', hint: '每題作答後立刻對答案' },
          {
            value: 'mock',
            label: '模擬考',
            hint: fullPaper ? `計時 ${durationMinutes} 分鐘，交卷才評分` : '計時，交卷才評分',
          },
        ]}
      />
      {countOptions.length > 1 && (
        <Segmented label="題數" value={countChoice} onChange={setCountChoice} options={countOptions} />
      )}
      <div className="flex flex-col gap-1">
        <Switch
          label="打亂題目順序"
          description={count !== null ? '抽部分題目時一律隨機抽' : undefined}
          checked={shuffleQuestions || count !== null}
          onChange={setShuffleQuestions}
        />
        <Switch
          label="打亂選項順序"
          description="選項有「以上皆是」這類寫法的題目不會打亂"
          checked={shuffleOptions}
          onChange={setShuffleOptions}
        />
      </div>
      {start.isError && <ErrorState error={start.error} />}
      <Button type="submit" size="lg" disabled={start.isPending || questionCount === 0}>
        <Icon name="play" size={16} />
        {start.isPending ? '準備試卷中…' : mode === 'mock' ? '開始模擬考' : '開始練習'}
      </Button>
    </form>
  )
}
