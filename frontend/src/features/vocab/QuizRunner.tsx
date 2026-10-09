/** 單字測驗：一次一張卡，作答後翻出完整單字卡（意思、例句、翻譯）。每日複習與錯題單字共用。 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/Button'
import { Switch } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { OptionBubble } from '@/components/OptionBubble'
import { RichText } from '@/components/RichText'
import { ErrorState } from '@/components/States'
import { ZhengTally } from '@/components/ZhengTally'
import { cx } from '@/lib/cx'
import { setShortcutsEnabled, useShortcutsEnabled } from '@/lib/shortcuts'
import { onRovingKeyDown, rovingTabIndex } from '@/lib/roving'
import type { QuizItem, VocabAnswerResult } from '@/lib/types'
import { answerWord, type QuizContext } from './api'

const LETTERS = 'ABCDEFGHIJ'
const TYPE_LABELS: Record<QuizItem['quiz_type'], string> = {
  en_to_zh: '選出中文意思',
  zh_to_en: '選出英文單字',
  spelling: '拼出英文單字',
  cloze: '選出填入空格的單字',
}

function Prompt({ item }: { item: QuizItem }) {
  if (item.quiz_type === 'en_to_zh') {
    return <p className="m-0 font-mono text-[40px] font-medium leading-tight tracking-tight text-ink sm:text-5xl">{item.prompt}</p>
  }
  if (item.quiz_type === 'cloze') {
    return <RichText className="font-sans! text-xl! leading-relaxed">{item.prompt}</RichText>
  }
  return <p className="m-0 font-hand text-2xl font-bold leading-snug text-ink sm:text-3xl">{item.prompt}</p>
}

function resultText(result: VocabAnswerResult) {
  return result.is_correct ? '答對了。' : `答錯了，答案是「${result.expected}」。`
}

function WordReveal({ result }: { result: VocabAnswerResult }) {
  const word = result.word
  const progress = word.progress
  return (
    <div
      className={cx(
        'flex flex-col gap-3 rounded-md border-l-[3px] px-5 py-4 animate-[rise-in_var(--dur)_var(--ease-out)]',
        result.is_correct ? 'border-ok bg-ok-soft/50' : 'border-bad bg-bad-soft/50',
      )}
    >
      <p id="quiz-result" className="m-0 font-medium">
        {resultText(result)}
      </p>
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-mono text-2xl font-medium">{word.term}</span>
        {word.part_of_speech && <span className="text-sm text-accent">{word.part_of_speech}</span>}
        <span className="text-ink">{word.meaning}</span>
      </div>
      {word.example && (
        <p className="m-0 flex flex-col gap-0.5 text-[15px]">
          <span className="text-ink">{word.example}</span>
          {word.example_translation && <span className="text-muted">{word.example_translation}</span>}
        </p>
      )}
      {progress && progress.in_wrong_list && (
        <ZhengTally count={progress.correct_streak} target={progress.mastery_target} size={28} />
      )}
    </div>
  )
}

interface QuizRunnerProps {
  items: QuizItem[]
  context: QuizContext
  onFinish?: (results: VocabAnswerResult[]) => void
}

export function QuizRunner({ items, context, onFinish }: QuizRunnerProps) {
  const queryClient = useQueryClient()
  const firstOpen = items.findIndex((item) => !item.answered)
  const [index, setIndex] = useState(firstOpen === -1 ? items.length : firstOpen)
  const [results, setResults] = useState<Record<number, VocabAnswerResult>>({})
  const [picked, setPicked] = useState<string | null>(null)
  const [spelling, setSpelling] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const item = items[index]
  const result = item ? results[index] : undefined
  // 這次測驗的 id（手機用 dev:lan 的 http 連線沒有 crypto.randomUUID）；每題作答的 id＝測驗 id＋題目位置
  const [runId] = useState(() => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`)

  const answer = useMutation({
    mutationFn: (response: string) => answerWord(item, response, context, `${runId}-${index}`),
    onSuccess: (data) => {
      setResults((old) => ({ ...old, [index]: data }))
      queryClient.invalidateQueries({ queryKey: ['vocab'] })
      window.setTimeout(() => nextRef.current?.focus(), 50)
    },
  })

  useEffect(() => {
    if (item?.quiz_type === 'spelling') window.setTimeout(() => inputRef.current?.focus(), 50)
  }, [index, item?.quiz_type])

  // 換到下一題時焦點移到新題目（第一題不移），鍵盤使用者接著按 Tab 就到選項
  const promptRef = useRef<HTMLDivElement>(null)
  const firstPrompt = useRef(true)
  useEffect(() => {
    if (firstPrompt.current) {
      firstPrompt.current = false
      return
    }
    if (item?.quiz_type !== 'spelling') promptRef.current?.focus({ preventScroll: true })
  }, [index, item?.quiz_type])

  const next = () => {
    const nextIndex = index + 1
    setPicked(null)
    setSpelling('')
    setIndex(nextIndex)
    if (nextIndex >= items.length) onFinish?.(Object.values(results))
  }

  // 鍵盤：1–4 選選項（可關閉）
  const shortcuts = useShortcutsEnabled()
  useEffect(() => {
    if (!shortcuts) return
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return
      if (!item || (event.target as HTMLElement).closest('input, textarea')) return
      const number = Number(event.key)
      if (!result && item.options && number >= 1 && number <= item.options.length && !answer.isPending) {
        setPicked(item.options[number - 1])
        answer.mutate(item.options[number - 1])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [answer, item, result, shortcuts])

  if (!item) return null

  const submitSpelling = (event: FormEvent) => {
    event.preventDefault()
    if (spelling.trim()) answer.mutate(spelling.trim())
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <span className="eyebrow-hand">{TYPE_LABELS[item.quiz_type]}</span>
        <span className="flex gap-1.5" role="img" aria-label={`第 ${index + 1} 個，共 ${items.length} 個`}>
          {items.map((entry, position) => {
            const done = results[position] ?? (entry.answered ? { is_correct: entry.is_correct } : null)
            return (
              <span
                key={`${entry.word_id}-${position}`}
                className={cx(
                  'h-2.5 w-6 rounded-[var(--radius-marker)] transition-colors duration-[var(--dur)]',
                  done ? (done.is_correct ? 'bg-ok-hl' : 'bg-bad-hl') : position === index ? 'bg-hl' : 'bg-line',
                )}
              />
            )
          })}
        </span>
      </div>

      {/* 朗讀區一直存在、作答後才填內容，螢幕閱讀器才會念出對錯 */}
      <p className="sr-only" aria-live="polite">
        {result ? resultText(result) : ''}
      </p>
      <div
        key={index}
        id="quiz-prompt"
        ref={promptRef}
        tabIndex={-1}
        className="flex min-h-[120px] flex-col justify-center gap-2 animate-[rise-in_var(--dur)_var(--ease-out)]"
      >
        <Prompt item={item} />
        {item.part_of_speech && item.quiz_type !== 'cloze' && <span className="text-sm text-accent">{item.part_of_speech}</span>}
      </div>

      {item.options ? (
        <div
          role="radiogroup"
          aria-labelledby="quiz-prompt"
          onKeyDown={(event) => onRovingKeyDown(event, false)}
          className="-mx-3 flex flex-col gap-0.5"
        >
          {item.options.map((option, position) => {
            const letter = LETTERS[position]
            const isPicked = picked === option
            const isExpected = result && option === result.expected
            const state = result
              ? isPicked
                ? result.is_correct
                  ? 'right'
                  : 'wrong'
                : isExpected
                  ? 'answer'
                  : 'dimmed'
              : isPicked
                ? 'chosen'
                : 'idle'
            return (
              <OptionBubble
                key={option}
                letter={letter}
                text={option}
                state={state}
                disabled={Boolean(result) || answer.isPending}
                tabIndex={rovingTabIndex(isPicked, position, picked !== null)}
                onSelect={() => {
                  setPicked(option)
                  answer.mutate(option)
                }}
              />
            )
          })}
        </div>
      ) : (
        <form onSubmit={submitSpelling} className="flex flex-col gap-3">
          <label htmlFor="spelling" className="text-sm text-muted">
            提示：<span className="font-mono tracking-[0.2em] text-ink">{item.hint}</span>
          </label>
          <div className="flex gap-2">
            <input
              id="spelling"
              ref={inputRef}
              value={spelling}
              onChange={(event) => setSpelling(event.target.value)}
              disabled={Boolean(result)}
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              className="h-12 min-w-0 flex-1 rounded-md border border-rule bg-sheet px-4 font-mono text-lg text-ink outline-none transition-colors focus:border-ink"
              placeholder="輸入英文…"
            />
            {!result && (
              <Button type="submit" size="lg" disabled={!spelling.trim() || answer.isPending}>
                確定
              </Button>
            )}
          </div>
        </form>
      )}

      {item.options && !result && (
        // 手機通常沒有實體鍵盤，只在桌機顯示
        <div className="hidden lg:block">
          <Switch
            label="單鍵快捷鍵"
            description={
              <>
                按 <kbd className="tabular">1</kbd>–<kbd className="tabular">{item.options.length}</kbd> 選答案
              </>
            }
            checked={shortcuts}
            onChange={setShortcutsEnabled}
          />
        </div>
      )}
      {answer.isError && <ErrorState error={answer.error} />}
      {result && <WordReveal result={result} />}
      {result && (
        <div className="flex justify-end">
          <Button ref={nextRef} aria-describedby="quiz-result" onClick={next}>
            {index + 1 < items.length ? '下一個' : '完成'}
            <Icon name="arrow" size={18} />
          </Button>
        </div>
      )}
    </div>
  )
}
