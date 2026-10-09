/** 題目編輯器用的資料型別與檢查（與後端 QuestionEdit 的驗證規則相同）。 */

import type { components } from './api-types'

export type QuestionDraft = components['schemas']['QuestionEdit']
export type RubricDraft = components['schemas']['RubricPoint']
type QuestionLike = Partial<components['schemas']['QuestionIn']> & Pick<components['schemas']['QuestionIn'], 'stem'>

export function emptyQuestion(): QuestionDraft {
  return {
    type: 'single_choice',
    label: null,
    passage: null,
    stem: '',
    options: ['', '', '', ''],
    answer: [],
    points: null,
    explanation: null,
    rubric: [],
    tags: [],
  }
}

/** 題庫或匯入檔裡的題目 → 編輯器的草稿 */
export function toDraft(question: QuestionLike): QuestionDraft {
  return {
    type: question.type ?? 'single_choice',
    label: question.label ?? null,
    passage: question.passage ?? null,
    stem: question.stem,
    options: question.options ?? [],
    answer: question.answer ?? [],
    points: question.points ?? null,
    explanation: question.explanation ?? null,
    rubric: question.rubric ?? [],
    tags: question.tags ?? [],
  }
}

/** 切換題型時調整選項與答案：申論題不用選項，換回選擇題時補四個空白選項 */
export function changeType(question: QuestionDraft, type: NonNullable<QuestionDraft['type']>): QuestionDraft {
  if (type === 'essay') {
    return { ...question, type, options: [], answer: [], rubric: question.rubric?.length ? question.rubric : [{ text: '', points: question.points ?? 0 }] }
  }
  const options = question.options?.length ? question.options : ['', '', '', '']
  const answer = type === 'single_choice' ? (question.answer ?? []).slice(0, 1) : (question.answer ?? [])
  return { ...question, type, options, answer, rubric: [] }
}

export const rubricTotal = (rubric: RubricDraft[] | undefined) => (rubric ?? []).reduce((sum, point) => sum + (point.points || 0), 0)

/** 驗證錯誤對到哪個欄位：編輯器用它標 aria-invalid、把焦點移過去 */
export type QuestionField = 'stem' | 'points' | 'explanation' | 'rubric' | 'options' | 'answer'
export interface QuestionProblem {
  field: QuestionField
  message: string
}

/** 檢查編輯中的題目，回傳第一個問題與對應欄位（沒問題回傳 null）。 */
export function findProblem(question: QuestionDraft): QuestionProblem | null {
  const problem = (field: QuestionField, message: string) => ({ field, message })
  if (!question.stem.trim()) return problem('stem', '請輸入題幹')
  if (question.type === 'essay') {
    if (!question.points || question.points <= 0) return problem('points', '申論題要填配分')
    if (!question.explanation?.trim()) return problem('explanation', '申論題要填參考答案')
    const rubric = question.rubric ?? []
    if (rubric.length === 0) return problem('rubric', '至少要有一個得分要點')
    if (rubric.some((point) => !point.text.trim() || !(point.points > 0))) return problem('rubric', '每個得分要點都要有內容和分數')
    if (Math.abs(rubricTotal(rubric) - question.points) > 0.01)
      return problem('rubric', `得分要點加總 ${rubricTotal(rubric)} 分，要等於配分 ${question.points} 分`)
    return null
  }
  const options = question.options ?? []
  const answer = question.answer ?? []
  if (options.length < 2) return problem('options', '至少要有兩個選項')
  if (options.some((option) => !option.trim())) return problem('options', '有空白的選項')
  if (answer.length === 0) return problem('answer', '請勾選正確答案')
  if (question.type === 'multi_choice' && answer.length < 2) return problem('answer', '複選題至少要有兩個正確答案')
  return null
}

/** 只要錯誤訊息 */
export function validateQuestion(question: QuestionDraft): string | null {
  return findProblem(question)?.message ?? null
}
