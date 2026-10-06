/**
 * 題目編輯器：修正轉檔錯誤、自己出題。題庫頁與匯入預覽頁共用。
 * 支援 Markdown＋LaTeX＋{{blank}}，可以切到預覽看實際顯示的樣子。
 */

import { useId, useState } from 'react'
import { Button } from '@/components/Button'
import { Segmented } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { RichText } from '@/components/RichText'
import { cx } from '@/lib/cx'
import type { QuestionDraft } from '@/lib/questionEdit'

const LETTERS = 'ABCDEFGHIJ'
const field =
  'w-full rounded-md border border-line bg-sheet px-3 py-2 text-[15px] leading-relaxed text-ink outline-none transition-colors focus:border-accent'

interface QuestionEditorProps {
  value: QuestionDraft
  onChange: (value: QuestionDraft) => void
}

export function QuestionEditor({ value, onChange }: QuestionEditorProps) {
  const id = useId()
  const [preview, setPreview] = useState(false)
  const [showPassage, setShowPassage] = useState(Boolean(value.passage))
  const set = <K extends keyof QuestionDraft>(key: K, next: QuestionDraft[K]) => onChange({ ...value, [key]: next })
  const multiple = value.type === 'multi_choice'

  const toggleAnswer = (letter: string) => {
    if (multiple) {
      const next = value.answer.includes(letter) ? value.answer.filter((item) => item !== letter) : [...value.answer, letter]
      set('answer', next.sort())
    } else {
      set('answer', [letter])
    }
  }

  const removeOption = (index: number) => {
    const options = value.options.filter((_, position) => position !== index)
    // 刪掉選項後，後面的字母往前移
    const answer = value.answer
      .map((letter) => LETTERS.indexOf(letter))
      .filter((position) => position !== index)
      .map((position) => LETTERS[position > index ? position - 1 : position])
    onChange({ ...value, options, answer })
  }

  if (preview) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" onClick={() => setPreview(false)}>
            <Icon name="edit" size={16} />
            回到編輯
          </Button>
        </div>
        {value.passage && <RichText className="rounded-md bg-sheet-tint px-4 py-3 text-[15px]">{value.passage}</RichText>}
        <RichText>{value.stem || '（還沒有題幹）'}</RichText>
        <ol className="m-0 flex list-none flex-col gap-2 p-0">
          {value.options.map((option, index) => (
            <li key={index} className="flex gap-3">
              <span className={cx('font-hand text-lg', value.answer.includes(LETTERS[index]) ? 'text-ok' : 'text-accent')}>
                {LETTERS[index]}
              </span>
              <span className={cx('marker', value.answer.includes(LETTERS[index]) ? '[--marker-color:var(--ok-hl)]' : '[--marker-scale:0]')}>
                <RichText inline>{option || '（空白）'}</RichText>
              </span>
            </li>
          ))}
        </ol>
        {value.explanation && <RichText className="text-[15px] text-ink-soft">{value.explanation}</RichText>}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="題型"
          value={value.type ?? 'single_choice'}
          onChange={(type) => onChange({ ...value, type, answer: type === 'single_choice' ? value.answer.slice(0, 1) : value.answer })}
          className="min-w-[240px]"
          options={[
            { value: 'single_choice', label: '單選' },
            { value: 'multi_choice', label: '複選' },
          ]}
        />
        <Button variant="ghost" size="sm" onClick={() => setPreview(true)}>
          預覽
        </Button>
      </div>

      {showPassage ? (
        <div className="flex flex-col gap-1.5">
          <label htmlFor={`${id}-passage`} className="text-xs text-muted">
            題組文章（閱讀測驗、克漏字；空格寫 {'{{blank:題號}}'}）
          </label>
          <textarea id={`${id}-passage`} rows={5} className={field} value={value.passage ?? ''} onChange={(event) => set('passage', event.target.value || null)} />
        </div>
      ) : (
        <button type="button" onClick={() => setShowPassage(true)} className="w-fit text-sm text-accent underline underline-offset-4">
          加上題組文章
        </button>
      )}

      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-stem`} className="text-xs text-muted">
          題幹（支援 Markdown、公式 $x^2$、填空 {'{{blank}}'}）
        </label>
        <textarea id={`${id}-stem`} rows={3} required className={field} value={value.stem} onChange={(event) => set('stem', event.target.value)} />
      </div>

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-1.5 text-xs text-muted">選項（勾選正確答案{multiple ? '，可以多個' : ''}）</legend>
        {value.options.map((option, index) => {
          const letter = LETTERS[index]
          const correct = value.answer.includes(letter)
          return (
            <div key={index} className="flex items-center gap-2">
              <button
                type="button"
                role={multiple ? 'checkbox' : 'radio'}
                aria-checked={correct}
                aria-label={`把 ${letter} 設為正確答案`}
                onClick={() => toggleAnswer(letter)}
                className={cx(
                  'grid h-10 w-10 flex-none place-items-center rounded-md border font-hand text-lg transition-colors',
                  correct ? 'border-ok bg-ok-hl text-ink' : 'border-line text-accent hover:bg-sheet-tint',
                )}
              >
                {letter}
              </button>
              <input
                aria-label={`選項 ${letter}`}
                className={cx(field, 'h-10 py-0')}
                value={option}
                onChange={(event) => set('options', value.options.map((item, position) => (position === index ? event.target.value : item)))}
              />
              <Button variant="ghost" size="sm" aria-label={`刪除選項 ${letter}`} disabled={value.options.length <= 2} onClick={() => removeOption(index)}>
                <Icon name="close" size={16} />
              </Button>
            </div>
          )
        })}
        {value.options.length < LETTERS.length && (
          <button type="button" onClick={() => set('options', [...value.options, ''])} className="w-fit text-sm text-accent underline underline-offset-4">
            新增選項
          </button>
        )}
      </fieldset>

      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-explanation`} className="text-xs text-muted">
          詳解（可留空，之後也能問 AI 助教）
        </label>
        <textarea id={`${id}-explanation`} rows={3} className={field} value={value.explanation ?? ''} onChange={(event) => set('explanation', event.target.value || null)} />
      </div>

      <div className="grid gap-4 sm:grid-cols-[1fr_140px]">
        <div className="flex flex-col gap-1.5">
          <label htmlFor={`${id}-tags`} className="text-xs text-muted">
            標籤（用頓號或逗號分隔，例如：指標、遞迴）
          </label>
          <input
            id={`${id}-tags`}
            className={cx(field, 'h-10 py-0')}
            value={value.tags?.join('、') ?? ''}
            onChange={(event) => set('tags', event.target.value.split(/[、,，]/).map((tag) => tag.trim()).filter(Boolean))}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={`${id}-points`} className="text-xs text-muted">
            配分
          </label>
          <input
            id={`${id}-points`}
            type="number"
            min={0}
            step={0.5}
            className={cx(field, 'h-10 py-0')}
            value={value.points ?? ''}
            onChange={(event) => set('points', event.target.value === '' ? null : Number(event.target.value))}
          />
        </div>
      </div>
    </div>
  )
}
