/** 題庫分組頁：例如「115普考－一般行政」底下的各科試卷，可以整組出題，也可以點進單科。 */

import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { Icon } from '@/components/Icon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { shortName } from '@/lib/format'
import { fetchPapers } from './api'
import { PaperRow } from './PaperRow'
import { groupFilter, groupLabel } from './groups'
import { StartPanel } from './StartPanel'

export function GroupPage() {
  const [params] = useSearchParams()
  const year = params.get('year') ? Number(params.get('year')) : null
  const examType = params.get('exam_type') ?? ''
  const category = params.get('category')
  const subject = params.get('subject')
  const filter = groupFilter({ year, examType, category, subject })
  const papers = useQuery({ queryKey: ['bank', 'papers', filter], queryFn: () => fetchPapers(filter) })

  const list = papers.data ?? []
  const essayCount = list.reduce((sum, paper) => sum + paper.essay_count, 0)
  const choiceCount = list.reduce((sum, paper) => sum + paper.question_count, 0) - essayCount
  const name = category ?? shortName(subject ?? '')
  const label = groupLabel(year, examType, name)

  return (
    <div className="flex flex-col gap-8">
      <Link to="/bank" className="inline-flex w-fit items-center gap-1.5 text-sm text-muted hover:text-ink">
        <Icon name="back" size={16} />
        題庫
      </Link>
      <PageHeader
        eyebrow={`${year ?? ''} 年・${examType}`}
        title={name}
        description={`${list.length} 科，選擇題 ${choiceCount} 題${essayCount > 0 ? `、申論題 ${essayCount} 題` : ''}。可以整組混在一起練，也可以點一科整份寫。`}
      />
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1.6fr)_minmax(300px,1fr)]">
        <section aria-label="科目">
          {papers.isPending ? (
            <Loading />
          ) : papers.isError ? (
            <ErrorState error={papers.error} onRetry={() => papers.refetch()} />
          ) : list.length === 0 ? (
            <EmptyState title="這一組沒有試卷">回題庫換一組看看。</EmptyState>
          ) : (
            <ul className="stagger m-0 list-none border-t border-rule p-0">
              {list.map((paper) => (
                <PaperRow key={paper.id} paper={paper} />
              ))}
            </ul>
          )}
        </section>
        <aside className="rounded-lg bg-sheet p-5 shadow-sheet sm:p-6 lg:sticky lg:top-24">
          <h2 className="m-0 mb-1 font-display text-lg font-bold">整組出題</h2>
          <p className="m-0 mb-5 text-sm text-muted">從 {label} 的所有科目抽題。</p>
          <StartPanel filter={filter} questionCount={choiceCount} essayCount={essayCount} title={label} />
        </aside>
      </div>
    </div>
  )
}
