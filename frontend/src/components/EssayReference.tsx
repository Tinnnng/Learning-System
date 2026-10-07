/** 申論題的參考答案與得分要點（唯讀）。試卷預覽、錯題本、搜尋、收藏共用。 */

import { RichText } from '@/components/RichText'
import { cx } from '@/lib/cx'
import { score } from '@/lib/format'

interface EssayReferenceProps {
  explanation: string | null | undefined
  rubric: Array<{ text: string; points: number }>
  /** 參考答案預設展開 */
  open?: boolean
  className?: string
}

export function EssayReference({ explanation, rubric, open = false, className }: EssayReferenceProps) {
  return (
    <div className={cx('flex flex-col gap-4', className)}>
      {rubric.length > 0 && (
        <section aria-label="得分要點" className="flex flex-col gap-1.5">
          <h4 className="m-0 text-sm font-normal text-muted">得分要點</h4>
          <ul className="m-0 flex list-none flex-col p-0">
            {rubric.map((point, index) => (
              <li key={index} className="flex items-baseline gap-3 border-b border-dashed border-rule py-2 text-[15px] last:border-b-0">
                <span className="flex-1 text-ink">{point.text}</span>
                <span className="tabular flex-none text-sm text-muted">{score(point.points)} 分</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {explanation && (
        <details className="rounded-md border-l-[3px] border-accent bg-accent-faint/60 px-4 py-3" open={open}>
          <summary className="cursor-pointer list-none text-sm font-medium text-accent">
            參考答案 <span className="font-normal text-muted">・由 Claude Code 撰寫，僅供參考</span>
          </summary>
          <RichText className="mt-3 text-[15px]">{explanation}</RichText>
        </details>
      )}
    </div>
  )
}
