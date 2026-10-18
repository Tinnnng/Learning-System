/**
 * 日期與數字格式。後端的時間是 UTC（沒有時區標記），顯示時一律轉成台灣時間。
 * 一律用 Intl.DateTimeFormat／NumberFormat，格式器建一次重複使用（列表每列都格式化，不要每次重建）。
 */

const TIME_ZONE = 'Asia/Taipei'
const LOCALE = 'zh-TW'

export function parseUtc(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

const isoDayFormat = new Intl.DateTimeFormat('en-CA', { timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' })
/** 台灣時間的日期 YYYY-MM-DD（行事曆、每日統計用來分天） */
export const isoDay = (date: Date = new Date()) => isoDayFormat.format(date)
const dayKey = isoDay

const dateFormats = new Map<string, Intl.DateTimeFormat>()
function dateFormat(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = JSON.stringify(options)
  let format = dateFormats.get(key)
  if (!format) {
    format = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, ...options })
    dateFormats.set(key, format)
  }
  return format
}

export function formatDate(value: string | Date, options: Intl.DateTimeFormatOptions = {}): string {
  const date = typeof value === 'string' ? parseUtc(value) : value
  return dateFormat({ month: 'long', day: 'numeric', ...options }).format(date)
}

const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function formatDateTime(value: string): string {
  return dateTimeFormat.format(parseUtc(value))
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
  return dateFormat({ month: 'long', day: 'numeric', weekday: 'long' }).format(now)
}

const percentFormats = new Map<number, Intl.NumberFormat>()
export function percent(value: number, digits = 0): string {
  let format = percentFormats.get(digits)
  if (!format) {
    format = new Intl.NumberFormat(LOCALE, { style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits })
    percentFormats.set(digits, format)
  }
  return format.format(value)
}

const usdFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const usdSmallFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 3, maximumFractionDigits: 3 })
/** AI 用量：$0.24；不到一分錢時多一位小數（$0.004） */
export function usd(value: number): string {
  return (value > 0 && value < 0.01 ? usdSmallFormat : usdFormat).format(value)
}

const megabytes = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1, minimumFractionDigits: 1 })
const integer = new Intl.NumberFormat(LOCALE)
export function fileSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${megabytes.format(bytes / 1024 / 1024)} MB` : `${integer.format(Math.max(1, Math.round(bytes / 1024)))} KB`
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
    .replace(/\$\$([\s\S]+?)\$\$|\$([^$]+)\$/g, (_, block: string | undefined, inline: string | undefined) =>
      (block ?? inline ?? '').replace(/\\oplus/g, '⊕').replace(/\\[a-zA-Z]+/g, '').replace(/[{}]/g, '').replace(/_(\w+)/g, '$1').replace(/\^(\w+)/g, '^$1'),
    )
    .replace(/[`*#>|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}
