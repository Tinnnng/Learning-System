/**
 * 題目內容顯示：Markdown（含表格）＋ LaTeX（$...$）＋填空格 {{blank}} / {{blank:41}}。
 */

import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { cx } from '@/lib/cx'

const BLANK = /\{\{blank(?::(\d+))?\}\}/g

interface MdNode {
  type: string
  value?: string
  children?: MdNode[]
  data?: { hName?: string; hProperties?: Record<string, string>; hChildren?: MdNode[] }
}

/** remark 外掛：把文字中的 {{blank}} 換成 <span class="blank"> */
function remarkBlank() {
  const transform = (node: MdNode) => {
    if (!node.children) return
    const next: MdNode[] = []
    for (const child of node.children) {
      if (child.type !== 'text' || !child.value || !BLANK.test(child.value)) {
        transform(child)
        next.push(child)
        continue
      }
      BLANK.lastIndex = 0
      let last = 0
      for (const match of child.value.matchAll(BLANK)) {
        const index = match.index ?? 0
        if (index > last) next.push({ type: 'text', value: child.value.slice(last, index) })
        const label = match[1] ?? ''
        next.push({
          type: 'blank',
          data: {
            hName: 'span',
            hProperties: { className: 'blank', 'aria-label': label ? `第 ${label} 題空格` : '空格' },
            hChildren: label ? [{ type: 'text', value: label }] : [],
          },
        })
        last = index + match[0].length
      }
      if (last < child.value.length) next.push({ type: 'text', value: child.value.slice(last) })
    }
    node.children = next
  }
  return (tree: MdNode) => transform(tree)
}

function assetUrl(path: string) {
  return /^(https?:|data:|\/)/.test(path) ? path : `/api/bank/assets/${path}`
}

interface RichTextProps {
  children: string
  /** 行內模式：不包 <p>，用在選項 */
  inline?: boolean
  className?: string
}

export function RichText({ children, inline = false, className }: RichTextProps) {
  const content = (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath, remarkBlank]}
      rehypePlugins={[rehypeKatex]}
      components={{
        p: ({ children: nodes }) => (inline ? <>{nodes}</> : <p>{nodes}</p>),
        img: ({ src, alt }) => (
          <img src={assetUrl(String(src ?? ''))} alt={alt ?? ''} className="my-2 max-w-full rounded-sm" />
        ),
        a: ({ href, children: nodes }) => (
          <a href={href} target="_blank" rel="noreferrer" className="text-accent underline underline-offset-2">
            {nodes}
          </a>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  )
  return inline ? <span className={className}>{content}</span> : <div className={cx('prose-question', className)}>{content}</div>
}

export function QuestionFigure({ path, caption }: { path: string; caption?: string | null }): ReactNode {
  return (
    <figure className="my-3">
      <img
        src={assetUrl(path)}
        alt={caption ?? '題目附圖'}
        className="max-w-full rounded-sm border border-line bg-white p-2 dark:opacity-95"
        loading="lazy"
      />
      {caption && <figcaption className="mt-1 text-sm text-muted">{caption}</figcaption>}
    </figure>
  )
}
