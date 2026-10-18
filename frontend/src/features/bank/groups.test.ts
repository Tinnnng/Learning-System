import { describe, expect, it } from 'vitest'
import type { PaperSummary } from '@/lib/types'
import { groupFilter, groupPapers, groupPath, sortExamTypes } from './groups'

const paper = (id: number, overrides: Partial<PaperSummary>): PaperSummary => ({
  id,
  source_key: `p${id}`,
  origin: 'official',
  exam_type: '普考',
  year: 115,
  subject: '科目',
  title: null,
  categories: [],
  duration_minutes: null,
  question_count: 10,
  essay_count: 0,
  ...overrides,
})

describe('groupPapers', () => {
  const papers = [
    paper(1, { subject: '行政學概要', categories: ['一般行政'] }),
    paper(2, { subject: '政治學概要', categories: ['一般行政'], question_count: 13, essay_count: 3 }),
    paper(3, { subject: '國文', categories: ['一般行政', '資訊處理'] }),
    paper(4, { subject: '資料庫', categories: ['資訊處理'], exam_type: '高考' }),
    paper(5, { subject: '程式設計-JAVA', exam_type: '期中考', origin: 'generated', question_count: 15 }),
  ]
  const groups = groupPapers(papers)

  it('合併同年度、同考試、同類科的科目', () => {
    expect(groups.map((group) => group.label)).toEqual([
      '115高考－資訊處理',
      '115普考－一般行政',
      '115普考－資訊處理',
      '115期中考－程式設計-JAVA',
    ])
    const general = groups[1]
    expect(general.papers.map((item) => item.id)).toEqual([1, 2, 3])
    expect([general.choiceCount, general.essayCount]).toEqual([30, 3])
  })

  it('屬於多個類科的試卷在每個類科都出現', () => {
    expect(groups[2].papers.map((item) => item.id)).toEqual([3])
  })

  it('沒有類科時用科目分組與篩選', () => {
    const midterm = groups[3]
    expect(groupFilter(midterm)).toEqual({ year: 115, exam_type: '期中考', category: null, subject: '程式設計-JAVA', no_year: false, no_category: true })
    expect(groupPath(groups[1])).toBe(`/bank/group?year=115&exam_type=${encodeURIComponent('普考')}&category=${encodeURIComponent('一般行政')}`)
  })
})

describe('sortExamTypes', () => {
  it('orders national exams before school exams', () => {
    expect(sortExamTypes(['地方特考', '普考', '期中考', '高考'])).toEqual(['高考', '普考', '地方特考', '期中考'])
  })
})
