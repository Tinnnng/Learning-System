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
  /** 選擇題題數 */
  questionCount: number
  /** 申論題題數；有的話可以選擇要不要一起寫 */
  essayCount?: number
  /** 整份試卷的考試時間（分鐘），模擬考預設用這個 */
  durationMinutes?: number | null
  title?: string
}

type CountChoice = 'all' | '10' | '20' | '30'

export function StartPanel({ filter, questionCount: choiceCount, essayCount = 0, durationMinutes, title }: StartPanelProps) {
  const [mode, setMode] = useState<'practice' | 'mock'>('practice')
  const [chosenCount, setCountChoice] = useState<CountChoice>('all')
  const [shuffleQuestions, setShuffleQuestions] = useState(false)
  const [shuffleOptions, setShuffleOptions] = useState(false)
  // 只有申論題時一定要包含；有選擇題時預設不含（申論題要打字、自己評分，比較花時間）
  const [wantEssay, setWantEssay] = useState(false)
  const includeEssay = essayCount > 0 && (wantEssay || choiceCount === 0)
  const questionCount = choiceCount + (includeEssay ? essayCount : 0)
  const start = useStartSession()

  const countOptions = (['all', '10', '20', '30'] as const)
    .filter((choice) => choice === 'all' || Number(choice) < questionCount)
    .map((choice) => ({ value: choice, label: choice === 'all' ? `全部 ${questionCount}` : `${choice} 題` }))
  // 題數變少（例如關掉申論題、換篩選條件）時，選過的題數可能已經不在選項裡，回到「全部」
  const countChoice: CountChoice = countOptions.some((option) => option.value === chosenCount) ? chosenCount : 'all'
  const count = countChoice === 'all' ? null : Math.min(Number(countChoice), questionCount)
  const fullPaper = countChoice === 'all' && durationMinutes

  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault()
        start.mutate({
          mode,
          title: title ? `${title}（${mode === 'mock' ? '模擬考' : '練習'}）` : undefined,
          source: { kind: 'filter', filter: { no_year: false, no_category: false, ...filter, types: ['single_choice', 'multi_choice'] } },
          include_essay: includeEssay,
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
        {essayCount > 0 && (
          <Switch
            label={`包含申論題（${essayCount} 題）`}
            description={
              choiceCount === 0 ? '這裡只有申論題：打字作答，再對照參考答案自評' : '要打字作答，再對照參考答案勾選得分要點自評'
            }
            checked={includeEssay}
            onChange={setWantEssay}
            disabled={choiceCount === 0}
          />
        )}
        <Switch
          label="打亂題目順序"
          description={count !== null ? '抽部分題目時一律隨機抽' : undefined}
          checked={shuffleQuestions || count !== null}
          onChange={setShuffleQuestions}
        />
        {choiceCount > 0 && (
          <Switch
            label="打亂選項順序"
            description="選項有「以上皆是」這類寫法的題目不會打亂"
            checked={shuffleOptions}
            onChange={setShuffleOptions}
          />
        )}
      </div>
      {start.isError && <ErrorState error={start.error} />}
      <Button type="submit" size="lg" disabled={start.isPending || questionCount === 0}>
        <Icon name="play" size={16} />
        {start.isPending ? '準備試卷中…' : mode === 'mock' ? '開始模擬考' : '開始練習'}
      </Button>
    </form>
  )
}
