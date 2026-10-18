/** 錯題本的作答紀錄與說明文字：申論題顯示得分比例，選擇題顯示選了什麼、對或錯。 */

import type { AttemptOut, MasteryRules } from './api'

export type AttemptTone = 'ok' | 'bad' | 'neutral'

const percent = (ratio: number) => `${Math.round(ratio * 100)}%`

export function attemptSummary(attempt: AttemptOut, rules: MasteryRules | undefined): { text: string; tone: AttemptTone } {
  const ratio = attempt.score_ratio
  if (ratio == null) {
    return {
      text: `選 ${attempt.response.join('、') || '—'}　${attempt.is_correct ? '對' : '錯'}`,
      tone: attempt.is_correct ? 'ok' : 'bad',
    }
  }
  // 申論題：達到及格比例算答好，低於錯題比例才算錯，中間只打斷連續、不進錯題本
  const pass = rules?.essay_pass_ratio ?? 0.8
  const wrong = rules?.essay_wrong_ratio ?? 0.6
  const tone: AttemptTone = ratio >= pass ? 'ok' : ratio < wrong ? 'bad' : 'neutral'
  return { text: `得分 ${percent(ratio)}`, tone }
}

export function masteryDescription(rules: MasteryRules | undefined) {
  if (!rules) return '答錯的題目會自動收進來，連續答對到寫滿一個「正」字才會移出。系統依記憶曲線排好每題的複習日。'
  return `答錯的題目會自動收進來，連續答對 ${rules.mastery_streak} 次（寫滿一個「正」字）才會移出；申論題是連續 ${rules.essay_mastery_streak} 次拿到 ${percent(rules.essay_pass_ratio)} 以上。系統依記憶曲線排好每題的複習日。`
}

export function masteredEmptyText(rules: MasteryRules | undefined) {
  return rules ? `錯題連續答對 ${rules.mastery_streak} 次就會出現在這裡。` : '錯題連續答對到寫滿一個「正」字，就會出現在這裡。'
}
