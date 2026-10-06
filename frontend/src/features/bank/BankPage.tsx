import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ChipGroup } from '@/components/Controls'
import { Icon } from '@/components/Icon'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, Loading } from '@/components/States'
import { Button, ButtonLink } from '@/components/Button'
import { shortName } from '@/lib/format'
import type { PaperSummary } from '@/lib/types'
import { fetchFilters, fetchPapers, type PaperFilters } from './api'
import { NewPaperDialog } from './NewPaperDialog'
import { StartPanel } from './StartPanel'

const ORIGIN_LABELS: Record<string, string> = { official: '考古題', generated: '教材出題', manual: '自建題目' }

function PaperRow({ paper }: { paper: PaperSummary }) {
  return (
    <li>
      <Link
        to={`/bank/papers/${paper.id}`}
        className="group grid grid-cols-[3.5rem_1fr_auto] items-center gap-4 border-b border-rule px-2 py-4 transition-colors hover:bg-sheet-tint sm:px-4"
      >
        <span className="flex flex-col items-start leading-tight">
          <span className="tabular text-lg text-ink">{paper.year ?? '—'}</span>
          <span className="text-xs text-accent">{paper.exam_type}</span>
        </span>
        <span className="flex min-w-0 flex-col gap-1">
          <span className="font-hand text-[17px] font-semibold leading-snug text-ink">{shortName(paper.subject)}</span>
          <span className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted">
            {paper.categories.length > 0 && <span>{paper.categories.join('、')}</span>}
            <span>{ORIGIN_LABELS[paper.origin] ?? paper.origin}</span>
            {paper.duration_minutes && <span>{paper.duration_minutes} 分鐘</span>}
          </span>
        </span>
        <span className="flex items-center gap-3 text-sm text-muted">
          <span className="tabular">{paper.question_count} 題</span>
          <Icon name="arrow" size={18} className="text-accent transition-transform duration-[var(--dur)] group-hover:translate-x-1" />
        </span>
      </Link>
    </li>
  )
}

export function BankPage() {
  const [params, setParams] = useSearchParams()
  const [creating, setCreating] = useState(false)
  const filters: PaperFilters = {
    exam_type: params.get('exam_type'),
    year: params.get('year') ? Number(params.get('year')) : null,
    category: params.get('category'),
    subject: params.get('subject'),
    origin: params.get('origin'),
  }
  const options = useQuery({ queryKey: ['bank', 'filters'], queryFn: fetchFilters })
  const papers = useQuery({ queryKey: ['bank', 'papers', filters], queryFn: () => fetchPapers(filters) })

  const setFilter = (key: keyof PaperFilters, value: string | number | null) => {
    const next = new URLSearchParams(params)
    if (value === null) next.delete(key)
    else next.set(key, String(value))
    if (key !== 'subject') next.delete('subject')
    setParams(next, { replace: true })
  }

  const list = papers.data ?? []
  const questionCount = list.reduce((sum, paper) => sum + paper.question_count, 0)
  const subjects = [...new Set(list.map((paper) => paper.subject))].sort()
  const hasFilter = Object.values(filters).some((value) => value !== null && value !== undefined)

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="題庫"
        title="試卷"
        description="選一份試卷整份寫，或用下面的條件跨試卷出題，例如把所有年度的「法學知識與英文」混在一起練。"
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
          <ChipGroup
            label="類科"
            value={filters.category ?? null}
            options={options.data.categories.map((value) => ({ value, label: value }))}
            onChange={(value) => setFilter('category', value)}
          />
          <ChipGroup
            label="科目"
            value={filters.subject ?? null}
            options={subjects.map((value) => ({ value, label: shortName(value) }))}
            onChange={(value) => setFilter('subject', value)}
          />
          {options.data.origins.length > 1 && (
            <ChipGroup
              label="來源"
              value={filters.origin ?? null}
              options={options.data.origins.map((value) => ({ value, label: ORIGIN_LABELS[value] ?? value }))}
              onChange={(value) => setFilter('origin', value)}
            />
          )}
        </div>
      )}

      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1.6fr)_minmax(300px,1fr)]">
        <section aria-label="試卷列表">
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
            <ul className="m-0 list-none border-t border-rule p-0">
              {list.map((paper) => (
                <PaperRow key={paper.id} paper={paper} />
              ))}
            </ul>
          )}
        </section>

        <aside className="rounded-lg bg-sheet p-5 shadow-sheet sm:p-6 lg:sticky lg:top-24">
          <h2 className="m-0 mb-1 font-hand text-lg font-bold">{hasFilter ? '用這些條件出題' : '從整個題庫出題'}</h2>
          <p className="m-0 mb-5 text-sm text-muted">
            {list.length} 份試卷，共 <span className="tabular text-ink">{questionCount}</span> 題選擇題
          </p>
          <StartPanel
            filter={{
              exam_type: filters.exam_type ?? null,
              year: filters.year ?? null,
              category: filters.category ?? null,
              subject: filters.subject ?? null,
              origin: (filters.origin as PaperSummary['origin'] | null) ?? null,
            }}
            questionCount={questionCount}
          />
        </aside>
      </div>
      <NewPaperDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  )
}
