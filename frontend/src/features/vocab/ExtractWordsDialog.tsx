/** 從考古題的英文題找生字：AI 挑出值得背的字（附題目原句當例句），勾選確認後才加入單字庫。 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button } from '@/components/Button'
import { Segmented } from '@/components/Controls'
import { Dialog } from '@/components/Dialog'
import { Icon } from '@/components/Icon'
import { ErrorState } from '@/components/States'
import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { cx } from '@/lib/cx'

type Extracted = components['schemas']['ExtractedWords']
type WordIn = components['schemas']['WordIn']
type ImportResult = components['schemas']['ImportResult']

export function ExtractWordsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [source, setSource] = useState<'wrong' | 'all'>('wrong')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const extract = useMutation({
    mutationFn: () => api.post<Extracted>('/vocab/extract-from-questions', { source }),
    onSuccess: (data) => setSelected(new Set(data.drafts.map((word) => word.term))),
  })
  const add = useMutation({
    mutationFn: (words: WordIn[]) => api.post<ImportResult>('/vocab/words', { words, source: '考古題生字' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['vocab'] }),
  })
  const drafts = extract.data?.drafts ?? []

  const close = () => {
    extract.reset()
    add.reset()
    onClose()
  }
  const toggle = (term: string) => {
    const next = new Set(selected)
    if (next.has(term)) next.delete(term)
    else next.add(term)
    setSelected(next)
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title="從考古題找生字"
      wide
      actions={
        drafts.length > 0 && !add.isSuccess ? (
          <>
            <Button variant="ghost" onClick={close}>
              取消
            </Button>
            <Button onClick={() => add.mutate(drafts.filter((word) => selected.has(word.term)))} disabled={selected.size === 0 || add.isPending}>
              加入 {selected.size} 個字
            </Button>
          </>
        ) : (
          <Button variant="ghost" onClick={close}>
            關閉
          </Button>
        )
      }
    >
      <div className="flex flex-col gap-5">
        <p className="m-0 text-sm text-muted">
          AI 會讀考古題裡的英文題（例如法學知識與英文），挑出值得背的字，用題目原句當例句。單字庫已有的字會自動略過；每次最多讀 15 題，大約 10 秒、花一點點 Claude 額度。
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            label="從哪些題目找"
            value={source}
            onChange={setSource}
            className="w-full sm:w-auto sm:min-w-[300px]"
            options={[
              { value: 'wrong', label: '答錯過的英文題' },
              { value: 'all', label: '全部英文題' },
            ]}
          />
          <Button onClick={() => extract.mutate()} disabled={extract.isPending}>
            <Icon name="spark" size={17} />
            {extract.isPending ? 'AI 找生字中…' : extract.isSuccess ? '再找一次' : '開始找'}
          </Button>
        </div>

        {extract.isError && <ErrorState error={extract.error} />}
        {extract.data?.message && <p className="m-0 text-sm text-muted">{extract.data.message}</p>}
        {add.isError && <ErrorState error={add.error} />}
        {add.data && (
          <p className="m-0 rounded-md bg-ok-soft/60 px-3 py-2 text-sm" role="status">
            已加入 {add.data.created} 個新單字{add.data.updated > 0 && `、更新 ${add.data.updated} 個`}，明天起會出現在每日複習。
          </p>
        )}

        {drafts.length > 0 && (
          <section aria-label="找到的生字" className="flex flex-col gap-2">
            <p className="m-0 text-xs text-muted">
              從 {extract.data?.question_count} 題中找到 {drafts.length} 個生字
              {extract.data && extract.data.skipped_existing > 0 && `（另有 ${extract.data.skipped_existing} 個已在單字庫）`}，取消勾選不需要的字：
            </p>
            <ul className="m-0 flex max-h-[45vh] list-none flex-col gap-2 overflow-y-auto p-0">
              {drafts.map((word) => {
                const checked = selected.has(word.term)
                return (
                  <li key={word.term}>
                    <label
                      className={cx(
                        'flex cursor-pointer items-start gap-3 rounded-md border px-4 py-3 transition-colors',
                        // 沒勾的不降透明度（會讓文字對比不足），改用一般底色
                        checked ? 'border-accent bg-accent-faint' : 'border-line bg-sheet',
                      )}
                    >
                      <input type="checkbox" checked={checked} onChange={() => toggle(word.term)} className="mt-1.5 h-4 w-4 accent-[var(--accent)]" />
                      <span className="flex min-w-0 flex-col gap-1">
                        <span className="flex flex-wrap items-baseline gap-x-3">
                          <span className="font-mono text-lg">{word.term}</span>
                          {word.part_of_speech && <span className="text-xs text-accent">{word.part_of_speech}</span>}
                          <span className="text-sm">{word.meaning}</span>
                        </span>
                        {word.example && (
                          <span className="text-sm text-muted">
                            {word.example}
                            {word.example_translation && <span className="block">{word.example_translation}</span>}
                          </span>
                        )}
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          </section>
        )}
      </div>
    </Dialog>
  )
}
