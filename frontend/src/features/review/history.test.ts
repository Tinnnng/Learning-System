import { describe, expect, it } from 'vitest'
import type { AttemptOut, MasteryRules } from './api'
import { attemptSummary, masteredEmptyText, masteryDescription } from './history'

const rules: MasteryRules = { mastery_streak: 3, essay_mastery_streak: 4, essay_pass_ratio: 0.8, essay_wrong_ratio: 0.6 }
const attempt = (overrides: Partial<AttemptOut>): AttemptOut => ({
  is_correct: false,
  response: [],
  score_ratio: null,
  session_id: null,
  time_spent_seconds: null,
  answered_at: '2026-10-01T00:00:00',
  ...overrides,
})

describe('attemptSummary', () => {
  it('shows the score ratio for essays instead of 選 — 錯', () => {
    expect(attemptSummary(attempt({ score_ratio: 0.7 }), rules)).toEqual({ text: '得分 70%', tone: 'neutral' })
    expect(attemptSummary(attempt({ score_ratio: 0.85, is_correct: true }), rules).tone).toBe('ok')
    expect(attemptSummary(attempt({ score_ratio: 0.3 }), rules).tone).toBe('bad')
  })

  it('keeps the choice format', () => {
    expect(attemptSummary(attempt({ response: ['B', 'C'], is_correct: true }), rules)).toEqual({ text: '選 B、C　對', tone: 'ok' })
  })
})

describe('mastery text', () => {
  it('follows the configured streaks', () => {
    expect(masteryDescription(rules)).toContain('連續答對 3 次')
    expect(masteryDescription(rules)).toContain('連續 4 次拿到 80% 以上')
    expect(masteredEmptyText(rules)).toBe('錯題連續答對 3 次就會出現在這裡。')
  })
})
