import { describe, expect, it } from 'vitest'
import { emptyQuestion, findProblem, validateQuestion } from './questionEdit'

describe('validateQuestion', () => {
  const ok = { ...emptyQuestion(), stem: '題目', options: ['甲', '乙'], answer: ['A'] }

  it('完整的題目沒有問題', () => {
    expect(validateQuestion(ok)).toBeNull()
  })

  it('找出常見錯誤', () => {
    expect(validateQuestion({ ...ok, stem: ' ' })).toBe('請輸入題幹')
    expect(validateQuestion({ ...ok, options: ['甲', ''] })).toBe('有空白的選項')
    expect(validateQuestion({ ...ok, answer: [] })).toBe('請勾選正確答案')
    expect(validateQuestion({ ...ok, type: 'multi_choice' })).toBe('複選題至少要有兩個正確答案')
  })

  it('錯誤對到欄位', () => {
    expect(findProblem({ ...ok, stem: '' })?.field).toBe('stem')
    expect(findProblem({ ...ok, options: ['甲', ''] })?.field).toBe('options')
    expect(findProblem({ ...ok, answer: [] })?.field).toBe('answer')
    expect(findProblem({ ...ok, type: 'essay', options: [], answer: [], points: 10, explanation: '答', rubric: [] })?.field).toBe('rubric')
  })
})
