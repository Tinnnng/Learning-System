/**
 * 題目編輯器：修正轉檔錯誤、自己出題。題庫頁與匯入預覽頁共用。
 * 支援 Markdown＋LaTeX＋{{blank}}，可以切到預覽看實際顯示的樣子。
 * 申論題不用選項，改填參考答案與得分要點（分數加總要等於配分）。
 */

import { useId, useState } from 'react'
import { Button } from '@/components/Button'
import { Segmented } from '@/components/Controls'
import { EssayReference } from '@/components/EssayReference'
import { Icon } from '@/components/Icon'
import { RichText } from '@/components/RichText'
import { cx } from '@/lib/cx'
import { changeType, type QuestionDraft, type QuestionProblem, rubricTotal } from '@/lib/questionEdit'
import { onRovingKeyDown, rovingTabIndex } from '@/lib/roving'

const LETTERS = 'ABCDEFGHIJ'
const control =
  'rounded-md border border-line bg-sheet px-3 py-2 text-[15px] leading-relaxed text-ink outline-none transition-colors focus:border-accent'
const field = `w-full ${control}`

interface QuestionEditorProps {
  value: QuestionDraft
  onChange: (value: QuestionDraft) => void
  /** 儲存時驗證失敗的欄位：標 aria-invalid，用 aria-describedby 連到錯誤訊息（訊息由呼叫端顯示，id 是 errorId） */
  problem?: QuestionProblem | null
  errorId?: string
}

export function QuestionEditor({ value, onChange, problem, errorId }: QuestionEditorProps) {
  const id = useId()
  /** 欄位的錯誤標記；data-field 讓對話框把焦點移到出錯的欄位 */
  const invalid = (field: QuestionProblem['field'], when = true) =>
    problem?.field === field && when
      ? { 'aria-invalid': true as const, 'aria-describedby': errorId, 'data-field': field }
      : { 'data-field': field }
  const [preview, setPreview] = useState(false)
  const [showPassage, setShowPassage] = useState(Boolean(value.passage))
  const set = <K extends keyof QuestionDraft>(key: K, next: QuestionDraft[K]) => onChange({ ...value, [key]: next })
  const type = value.type ?? 'single_choice'
  const essay = type === 'essay'
  const multiple = type === 'multi_choice'
  const options = value.options ?? []
  const answer = value.answer ?? []
  const rubric = value.rubric ?? []

  const toggleAnswer = (letter: string) => {
    if (multiple) {
      const next = answer.includes(letter) ? answer.filter((item) => item !== letter) : [...answer, letter]
      set('answer', next.sort())
    } else {
      set('answer', [letter])
    }
  }

  const removeOption = (index: number) => {
    // 刪掉選項後，後面的字母往前移
    const nextAnswer = answer
      .map((letter) => LETTERS.indexOf(letter))
      .filter((position) => position !== index)
      .map((position) => LETTERS[position > index ? position - 1 : position])
    onChange({ ...value, options: options.filter((_, position) => position !== index), answer: nextAnswer })
  }

  const setRubric = (index: number, patch: Partial<(typeof rubric)[number]>) =>
    set('rubric', rubric.map((point, position) => (position === index ? { ...point, ...patch } : point)))

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
        {essay ? (
          <EssayReference explanation={value.explanation} rubric={rubric} open />
        ) : (
          <>
            <ol className="m-0 flex list-none flex-col gap-2 p-0">
              {options.map((option, index) => (
                <li key={index} className="flex gap-3">
                  <span className={cx('font-display text-lg', answer.includes(LETTERS[index]) ? 'text-ok' : 'text-accent')}>
                    {LETTERS[index]}
                  </span>
                  <span className={cx(answer.includes(LETTERS[index]) && 'font-medium text-ok')}>
                    <RichText inline>{option || '（空白）'}</RichText>
                  </span>
                </li>
              ))}
            </ol>
            {value.explanation && <RichText className="text-[15px] text-ink-soft">{value.explanation}</RichText>}
          </>
        )}
      </div>
    )
  }

  const total = rubricTotal(rubric)
  const totalMismatch = essay && value.points != null && Math.abs(total - value.points) > 0.01

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="題型"
          value={type}
          onChange={(next) => onChange(changeType(value, next))}
          className="min-w-[280px]"
          options={[
            { value: 'single_choice', label: '單選' },
            { value: 'multi_choice', label: '複選' },
            { value: 'essay', label: '申論' },
          ]}
        />
        <Button variant="ghost" size="sm" onClick={() => setPreview(true)}>
          預覽
        </Button>
      </div>

      {showPassage ? (
        <div className="flex flex-col gap-1.5">
          <label htmlFor={`${id}-passage`} className="text-xs text-muted">
            {essay ? '題目說明（大題共同的情境，例如「某校計畫…請回答以下問題」）' : '題組文章（閱讀測驗、克漏字；空格寫 {{blank:題號}}）'}
          </label>
          <textarea id={`${id}-passage`} rows={5} className={field} value={value.passage ?? ''} onChange={(event) => set('passage', event.target.value || null)} />
        </div>
      ) : (
        <button type="button" onClick={() => setShowPassage(true)} className="hit w-fit text-sm text-accent underline underline-offset-4">
          {essay ? '加上題目說明' : '加上題組文章'}
        </button>
      )}

      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-stem`} className="text-xs text-muted">
          題幹（支援 Markdown、公式 $x^2${essay ? '、程式碼用 ``` 包起來' : '、填空 {{blank}}'}）
        </label>
        <textarea id={`${id}-stem`} {...invalid('stem')} rows={essay ? 5 : 3} required className={field} value={value.stem} onChange={(event) => set('stem', event.target.value)} />
      </div>

      {essay ? (
        <>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-explanation`} className="text-xs text-muted">
              參考答案（作答後才會看到）
            </label>
            <textarea id={`${id}-explanation`} {...invalid('explanation')} rows={6} className={field} value={value.explanation ?? ''} onChange={(event) => set('explanation', event.target.value || null)} />
          </div>

          <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
            <legend className="mb-1.5 text-xs text-muted">得分要點（作答後勾選自評，分數加總要等於配分）</legend>
            {rubric.map((point, index) => (
              <div key={index} className="flex flex-wrap items-center gap-2 border-b border-dashed border-rule pb-2 last:border-b-0 sm:flex-nowrap sm:border-b-0 sm:pb-0">
                <input
                  aria-label={`得分要點 ${index + 1}`}
                  {...invalid('rubric', !point.text.trim() || !(point.points > 0) || index === 0)}
                  placeholder="寫成可以判斷有沒有寫到的具體內容，例如：指出需要路由器…"
                  className={cx(control, 'h-10 min-w-0 basis-full py-0 sm:basis-auto sm:flex-1')}
                  value={point.text}
                  onChange={(event) => setRubric(index, { text: event.target.value })}
                />
                <input
                  aria-label={`得分要點 ${index + 1} 的分數`}
                  type="number"
                  min={0}
                  step={0.5}
                  className={cx(control, 'tabular ml-auto h-10 w-20 flex-none py-0 text-right sm:ml-0')}
                  value={point.points || ''}
                  onChange={(event) => setRubric(index, { points: Number(event.target.value) || 0 })}
                />
                <span className="flex-none text-sm text-muted">分</span>
                <Button variant="ghost" size="sm" aria-label={`刪除得分要點 ${index + 1}`} disabled={rubric.length <= 1} onClick={() => set('rubric', rubric.filter((_, position) => position !== index))}>
                  <Icon name="close" size={16} />
                </Button>
              </div>
            ))}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button type="button" onClick={() => set('rubric', [...rubric, { text: '', points: 0 }])} className="hit w-fit text-sm text-accent underline underline-offset-4">
                新增得分要點
              </button>
              <span className={cx('tabular text-sm', totalMismatch ? 'text-bad' : 'text-muted')} role="status">
                加總 {total} 分{value.points != null && `／配分 ${value.points} 分`}
              </span>
            </div>
          </fieldset>
        </>
      ) : (
        <>
          <fieldset
            className="m-0 flex flex-col gap-2 border-0 p-0"
            onKeyDown={multiple ? undefined : (event) => onRovingKeyDown(event)}
          >
            <legend className="mb-1.5 text-xs text-muted">選項（勾選正確答案{multiple ? '，可以多個' : ''}）</legend>
            {options.map((option, index) => {
              const letter = LETTERS[index]
              const correct = answer.includes(letter)
              return (
                <div key={index} className="flex items-center gap-2">
                  <button
                    type="button"
                    role={multiple ? 'checkbox' : 'radio'}
                    aria-checked={correct}
                    aria-label={`把 ${letter} 設為正確答案`}
                    {...invalid('answer', index === 0)}
                    tabIndex={multiple ? undefined : rovingTabIndex(correct, index, answer.length > 0)}
                    onClick={() => toggleAnswer(letter)}
                    className={cx(
                      'grid h-10 w-10 flex-none place-items-center rounded-md border font-display text-lg transition-colors',
                      correct ? 'border-ok bg-ok-soft text-ok' : 'border-line text-accent hover:bg-sheet-tint',
                    )}
                  >
                    {letter}
                  </button>
                  <input
                    aria-label={`選項 ${letter}`}
                    {...invalid('options', !option.trim() || options.length < 2)}
                    className={cx(field, 'h-10 py-0')}
                    value={option}
                    onChange={(event) => set('options', options.map((item, position) => (position === index ? event.target.value : item)))}
                  />
                  <Button variant="ghost" size="sm" aria-label={`刪除選項 ${letter}`} disabled={options.length <= 2} onClick={() => removeOption(index)}>
                    <Icon name="close" size={16} />
                  </Button>
                </div>
              )
            })}
            {options.length < LETTERS.length && (
              <button type="button" onClick={() => set('options', [...options, ''])} className="hit w-fit text-sm text-accent underline underline-offset-4">
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
        </>
      )}

      <div className={cx('grid gap-4', essay ? 'sm:grid-cols-[1fr_120px_120px]' : 'sm:grid-cols-[1fr_140px]')}>
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
        {essay && (
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-label`} className="text-xs text-muted">
              顯示題號
            </label>
            <input
              id={`${id}-label`}
              placeholder="例如 一(二)"
              maxLength={20}
              className={cx(field, 'h-10 py-0')}
              value={value.label ?? ''}
              onChange={(event) => set('label', event.target.value || null)}
            />
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <label htmlFor={`${id}-points`} className="text-xs text-muted">
            配分{essay && '（必填）'}
          </label>
          <input
            id={`${id}-points`}
            {...invalid('points')}
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
