import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ChipGroup } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { Button, ButtonLink } from '@/components/Button'
import { fetchFilters, fetchPapers, type PaperFilters } from './api'
import { groupPapers, groupPath, ORIGIN_LABELS, type PaperGroup } from './groups'
import { NewPaperDialog } from './NewPaperDialog'
import { QuestionSearchForm } from './SearchPage'
import { StartPanel } from './StartPanel'

const countText = (choice: number, essay: number) =>
  [choice > 0 && `${choice} 題`, essay > 0 && `申論 ${essay} 題`].filter(Boolean).join('・')

function GroupRow({ group }: { group: PaperGroup }) {
  const origins = [...new Set(group.papers.map((paper) => ORIGIN_LABELS[paper.origin] ?? paper.origin))]
  return (
    <li>
      <Link
        to={groupPath(group)}
        className="group grid grid-cols-[1fr_auto] items-center gap-4 border-b border-rule px-2 py-4 transition-colors hover:bg-sheet-tint sm:px-4"
      >
        <span className="flex min-w-0 flex-col gap-1">
          <span className="w-fit font-display text-lg font-semibold leading-snug text-ink">
            <span className="pen-underline">{group.label}</span>
          </span>
          <span className="text-xs text-muted">
            {group.papers.length} 科・{origins.join('、')}
          </span>
        </span>
        <span className="flex items-center gap-3 text-sm text-muted">
          <span className="tabular">{countText(group.choiceCount, group.essayCount)}</span>
          <Icon name="arrow" size={18} className="text-accent transition-transform duration-[var(--dur)] group-hover:translate-x-1" />
        </span>
      </Link>
    </li>
  )
}

export function BankPage() {
  const [params, setParams] = useSearchParams()
  const [creating, setCreating] = useState(false)
  // 題庫只用「考試」「年度」篩選；類科併進分組名稱（115普考－一般行政），科目在分組頁裡看
  const filters: PaperFilters = {
    exam_type: params.get('exam_type'),
    year: params.get('year') ? Number(params.get('year')) : null,
  }
  const options = useQuery({ queryKey: ['bank', 'filters'], queryFn: fetchFilters })
  const papers = useQuery({ queryKey: ['bank', 'papers', filters], queryFn: () => fetchPapers(filters) })

  const setFilter = (key: keyof PaperFilters, value: string | number | null) => {
    const next = new URLSearchParams(params)
    if (value === null) next.delete(key)
    else next.set(key, String(value))
    setParams(next, { replace: true })
  }

  const list = papers.data ?? []
  const essayCount = list.reduce((sum, paper) => sum + paper.essay_count, 0)
  const questionCount = list.reduce((sum, paper) => sum + paper.question_count, 0) - essayCount
  const groups = groupPapers(list)
  const hasFilter = Object.values(filters).some((value) => value !== null && value !== undefined)

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="題庫"
        title="試卷"
        description="同一年度、同一考試、同一類科的科目放在一組，例如「115普考－一般行政」。點進去可以整組練，也可以挑一科寫。"
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => setCreating(true)}>
              <Icon name="plus" size={18} />
              自建題組
            </Button>
            <ButtonLink to="/import" variant="ghost" size="sm">
              <Icon name="import" size={18} />
              匯入題目
            </ButtonLink>
          </>
        }
      />

      <QuestionSearchForm className="max-w-[640px]" />

      {options.data && (
        <div className="flex flex-col gap-3">
          <ChipGroup
            label="考試"
            value={filters.exam_type ?? null}
            options={options.data.exam_types.map((value) => ({ value, label: value }))}
            onChange={(value) => setFilter('exam_type', value)}
          />
          <ChipGroup
            label="年度"
            value={filters.year ?? null}
            options={options.data.years.map((value) => ({ value, label: `${value} 年` }))}
            onChange={(value) => setFilter('year', value)}
          />
        </div>
      )}

      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1.6fr)_minmax(300px,1fr)]">
        <section aria-label="試卷分組">
          {papers.isPending ? (
            <Loading />
          ) : papers.isError ? (
            <ErrorState error={papers.error} onRetry={() => papers.refetch()} />
          ) : list.length === 0 ? (
            <EmptyState
              title={hasFilter ? '沒有符合條件的試卷' : '題庫還是空的'}
              action={
                hasFilter ? undefined : (
                  <ButtonLink to="/import" variant="secondary">
                    匯入題目
                  </ButtonLink>
                )
              }
            >
              {hasFilter ? '換個條件試試看。' : '把試卷 PDF 交給 Claude Code 轉檔後，到「匯入」頁匯入。'}
            </EmptyState>
          ) : (
            <ul className="stagger m-0 list-none border-t border-rule p-0">
              {groups.map((group) => (
                <GroupRow key={group.key} group={group} />
              ))}
            </ul>
          )}
        </section>

        <aside className="rounded-lg bg-sheet p-5 shadow-sheet sm:p-6 lg:sticky lg:top-24">
          <h2 className="m-0 mb-1 font-display text-lg font-bold">{hasFilter ? '用這些條件出題' : '從整個題庫出題'}</h2>
          <p className="m-0 mb-5 text-sm text-muted">
            {groups.length} 組、{list.length} 份試卷，共 <span className="tabular text-ink">{questionCount}</span> 題選擇題
            {essayCount > 0 && (
              <>
                、<span className="tabular text-ink">{essayCount}</span> 題申論題
              </>
            )}
          </p>
          <StartPanel
            filter={{ exam_type: filters.exam_type ?? null, year: filters.year ?? null }}
            questionCount={questionCount}
            essayCount={essayCount}
          />
        </aside>
      </div>
      <NewPaperDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  )
}
