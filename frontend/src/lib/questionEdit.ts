/** 題目編輯器用的資料型別與檢查（與後端 QuestionEdit 的驗證規則相同）。 */

import type { components } from './api-types'

export type QuestionDraft = components['schemas']['QuestionEdit']

export function emptyQuestion(): QuestionDraft {
  return { type: 'single_choice', passage: null, stem: '', options: ['', '', '', ''], answer: [], points: null, explanation: null, tags: [] }
}

/** 檢查編輯中的題目，回傳第一個問題（沒問題回傳 null）。 */
export function validateQuestion(question: QuestionDraft): string | null {
  if (!question.stem.trim()) return '請輸入題幹'
  if (question.options.length < 2) return '至少要有兩個選項'
  if (question.options.some((option) => !option.trim())) return '有空白的選項'
  if (question.answer.length === 0) return '請勾選正確答案'
  if (question.type === 'multi_choice' && question.answer.length < 2) return '複選題至少要有兩個正確答案'
  return null
}
