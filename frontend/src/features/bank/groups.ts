/**
 * 題庫分組：同一年度、同一種考試、同一個類科的試卷合成一組，例如「115普考－一般行政」底下有國文、行政學、政治學…。
 * 沒有類科的（期中考、自建題組）用科目當組名。同一份試卷屬於多個類科時（例如國文），每個類科都會出現。
 */

import type { PaperSummary } from '@/lib/types'
import { shortName } from '@/lib/format'
import type { PaperFilters } from './api'

export const ORIGIN_LABELS: Record<string, string> = { official: '考古題', generated: '教材出題', manual: '自建題目' }

export interface PaperGroup {
  key: string
  year: number | null
  examType: string
  /** 類科；沒有類科時為 null，改用 subject 分組 */
  category: string | null
  subject: string | null
  /** 例如「115普考－一般行政」 */
  label: string
  papers: PaperSummary[]
  choiceCount: number
  essayCount: number
}

// 同一年度裡的排列順序；沒列到的排在後面，依名稱排序
const EXAM_ORDER = ['高考', '普考', '初等考試', '地方特考', '期中考', '期末考']
const examRank = (examType: string) => {
  const index = EXAM_ORDER.indexOf(examType)
  return index === -1 ? EXAM_ORDER.length : index
}

/** 篩選列的考試選項也照同樣順序（高考、普考、地方特考、期中考…） */
export const sortExamTypes = (examTypes: string[]) =>
  [...examTypes].sort((a, b) => examRank(a) - examRank(b) || a.localeCompare(b, 'zh-Hant'))

export function groupLabel(year: number | null, examType: string, name: string) {
  return `${year ?? ''}${examType}－${name}`
}

export function groupPapers(papers: PaperSummary[]): PaperGroup[] {
  const groups = new Map<string, PaperGroup>()
  for (const paper of papers) {
    const names = paper.categories.length > 0 ? paper.categories.map((category) => ({ category, subject: null })) : [{ category: null, subject: paper.subject }]
    for (const { category, subject } of names) {
      const name = category ?? shortName(subject ?? '')
      const key = `${paper.year ?? ''}|${paper.exam_type}|${category ? `c:${category}` : `s:${subject}`}`
      let group = groups.get(key)
      if (!group) {
        group = {
          key,
          year: paper.year,
          examType: paper.exam_type,
          category,
          subject,
          label: groupLabel(paper.year, paper.exam_type, name),
          papers: [],
          choiceCount: 0,
          essayCount: 0,
        }
        groups.set(key, group)
      }
      group.papers.push(paper)
      group.essayCount += paper.essay_count
      group.choiceCount += paper.question_count - paper.essay_count
    }
  }
  return [...groups.values()].sort(
    (a, b) =>
      (b.year ?? 0) - (a.year ?? 0) ||
      examRank(a.examType) - examRank(b.examType) ||
      a.examType.localeCompare(b.examType, 'zh-TW') ||
      a.label.localeCompare(b.label, 'zh-TW'),
  )
}

/** 這一組的篩選條件（出題、查詢用）。沒有年度、沒有類科的組要明確說「沒有」，否則會混進其他年度、或同科目但有類科的試卷 */
export function groupFilter(
  group: Pick<PaperGroup, 'year' | 'examType' | 'category' | 'subject'>,
): Pick<PaperFilters, 'year' | 'exam_type' | 'category' | 'subject' | 'no_year' | 'no_category'> {
  return {
    year: group.year,
    exam_type: group.examType,
    category: group.category,
    subject: group.category ? null : group.subject,
    no_year: group.year === null,
    no_category: !group.category,
  }
}

export function groupPath(group: PaperGroup) {
  const params = new URLSearchParams()
  // 網址只放年度、考試、類科、科目；分組頁讀回來時沒有年度／類科就自己補上「沒有」的條件
  const { year, exam_type, category, subject } = groupFilter(group)
  for (const [key, value] of Object.entries({ year, exam_type, category, subject })) {
    if (value !== null && value !== undefined) params.set(key, String(value))
  }
  return `/bank/group?${params}`
}
