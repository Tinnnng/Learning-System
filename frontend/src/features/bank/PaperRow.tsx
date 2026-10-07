import { Link } from 'react-router'
import { Icon } from '@/components/Icon'
import { shortName } from '@/lib/format'
import type { PaperSummary } from '@/lib/types'
import { ORIGIN_LABELS } from './groups'

/** 分組頁裡的一份試卷（一個科目）；年度與考試已經寫在分組標題，這裡不重複 */
export function PaperRow({ paper }: { paper: PaperSummary }) {
  return (
    <li>
      <Link
        to={`/bank/papers/${paper.id}`}
        className="group grid grid-cols-[1fr_auto] items-center gap-4 border-b border-rule px-2 py-4 transition-colors hover:bg-sheet-tint sm:px-4"
      >
        <span className="flex min-w-0 flex-col gap-1">
          <span className="w-fit font-display text-[17px] font-semibold leading-snug text-ink">
            <span className="pen-underline">{shortName(paper.subject)}</span>
          </span>
          <span className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted">
            {paper.categories.length > 0 && <span>{paper.categories.join('、')}</span>}
            <span>{ORIGIN_LABELS[paper.origin] ?? paper.origin}</span>
            {paper.duration_minutes && <span>{paper.duration_minutes} 分鐘</span>}
          </span>
        </span>
        <span className="flex items-center gap-3 text-sm text-muted">
          <span className="tabular">
            {paper.essay_count === paper.question_count ? `申論 ${paper.essay_count} 題` : `${paper.question_count - paper.essay_count} 題`}
          </span>
          <Icon name="arrow" size={18} className="text-accent transition-transform duration-[var(--dur)] group-hover:translate-x-1" />
        </span>
      </Link>
    </li>
  )
}
