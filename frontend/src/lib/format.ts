/** 日期與數字格式。後端的時間是 UTC（沒有時區標記），顯示時一律轉成台灣時間。 */

const TIME_ZONE = 'Asia/Taipei'

export function parseUtc(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

const dayKey = (date: Date) => date.toLocaleDateString('en-CA', { timeZone: TIME_ZONE })

export function formatDate(value: string | Date, options: Intl.DateTimeFormatOptions = {}): string {
  const date = typeof value === 'string' ? parseUtc(value) : value
  return date.toLocaleDateString('zh-TW', { timeZone: TIME_ZONE, month: 'long', day: 'numeric', ...options })
}

export function formatDateTime(value: string): string {
  return parseUtc(value).toLocaleString('zh-TW', {
    timeZone: TIME_ZONE,
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** 「今天」「明天」「3 天後」「2 天前」 */
export function relativeDay(value: string, now = new Date()): string {
  const target = new Date(dayKey(parseUtc(value)))
  const today = new Date(dayKey(now))
  const days = Math.round((target.getTime() - today.getTime()) / 86_400_000)
  if (days === 0) return '今天'
  if (days === 1) return '明天'
  if (days === -1) return '昨天'
  return days > 0 ? `${days} 天後` : `${-days} 天前`
}

export function todayLabel(now = new Date()): string {
  return now.toLocaleDateString('zh-TW', { timeZone: TIME_ZONE, month: 'long', day: 'numeric', weekday: 'long' })
}

export function percent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`
}

export function clock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = String(seconds % 60).padStart(2, '0')
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`
}

export function score(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** 去掉科目名稱裡冗長的說明括號，例如「法學知識與英文(包括中華民國憲法、法學緒論、英文)」→「法學知識與英文」 */
export function shortName(text: string): string {
  return text.replace(/\s*[（(]包括[^)）]*[)）]/g, '').trim()
}

/** 題目摘要用的純文字：程式碼區塊、公式、填空、Markdown 符號都轉成好讀的文字 */
export function plainText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, '〔程式碼〕')
    .replace(/\{\{blank(?::\d+)?\}\}/g, '＿＿')
    .replace(/\$([^$]+)\$/g, (_, tex: string) =>
      tex.replace(/\\oplus/g, '⊕').replace(/\\[a-zA-Z]+/g, '').replace(/[{}]/g, '').replace(/_(\w+)/g, '$1').replace(/\^(\w+)/g, '^$1'),
    )
    .replace(/[`*#>|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}
