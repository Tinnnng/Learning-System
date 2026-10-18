/**
 * 讀書日曆：每天一格，寫的題目＋背的單字越多，原子筆藍越深。上方是連續讀書天數。
 * 依卡片寬度顯示近 17／26／30 週（手機放得下、不用左右捲，桌機盡量填滿）。
 * 格子不是按鈕（一百多個 Tab 停留點太多）：滑鼠移過或點一下，下方顯示那天的數字；螢幕閱讀器念整體摘要。
 */

import { useQuery } from '@tanstack/react-query'
import { type CSSProperties, useState } from 'react'
import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { cx } from '@/lib/cx'

type Calendar = components['schemas']['ActivityCalendar']
type Day = components['schemas']['ActivityDay']

const WEEKS = 30
const MOBILE_WEEKS = 17
const MEDIUM_WEEKS = 26
const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
/** 一天的份量（題數＋單字數）對應的深淺：0、1–9、10–24、25–49、50 以上 */
const LEVELS = [1, 10, 25, 50]
const SHADES = [0, 28, 52, 76, 100]

const total = (day: Day) => day.questions + day.words
const level = (day: Day) => LEVELS.filter((min) => total(day) >= min).length

function label(day: Day) {
  const [, month, date] = day.date.split('-').map(Number)
  const parts = [day.questions && `${day.questions} 題`, day.words && `${day.words} 個單字`].filter(Boolean)
  return `${month}/${date}：${parts.length ? parts.join('、') : '沒有讀書'}`
}

function shade(value: number): CSSProperties {
  return value === 0
    ? { background: 'var(--line)' }
    : { background: `color-mix(in srgb, var(--accent) ${SHADES[value]}%, var(--sheet))` }
}

export function StudyCalendar() {
  const calendar = useQuery({
    queryKey: ['activity', 'calendar'],
    queryFn: () => api.get<Calendar>(`/activity/calendar?days=${WEEKS * 7}`),
    // 作答的頁面不會通知首頁；每次回到首頁都重抓，剛寫完的題目馬上算進今天
    staleTime: 0,
  })
  const [picked, setPicked] = useState<Day | null>(null)
  if (!calendar.data) return null
  const data = calendar.data

  // 補到從星期日開始，每 7 天一欄
  const first = new Date(`${data.days[0].date}T00:00:00`)
  const cells: Array<Day | null> = [...Array(first.getDay()).fill(null), ...data.days]
  const weeks: Array<Array<Day | null>> = []
  for (let index = 0; index < cells.length; index += 7) weeks.push(cells.slice(index, index + 7))
  const recentActive = data.days.slice(-30).filter((day) => total(day) > 0).length
  // 越舊的週越早藏起來：手機 17 週；sm 與 lg（卡片比較窄）26 週；其他 30 週
  const hide = (index: number) => {
    const age = weeks.length - index
    return cx(age > MOBILE_WEEKS && 'max-sm:hidden', age > MEDIUM_WEEKS && 'sm:max-md:hidden lg:max-xl:hidden')
  }
  const today = data.days[data.days.length - 1]
  const studiedToday = total(today) > 0

  return (
    <section aria-labelledby="study-calendar-title" className="flex flex-col gap-4 rounded-lg bg-sheet px-5 py-6 shadow-sheet sm:px-7">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div className="flex flex-col gap-1">
          <h2 id="study-calendar-title" className="eyebrow m-0">
            讀書日曆
          </h2>
          <p className="m-0 flex items-baseline gap-2">
            <span className="text-sm text-muted">連續讀書</span>
            <span className="tabular font-display text-3xl font-bold leading-none text-accent">{data.streak}</span>
            <span className="text-sm text-accent">天</span>
          </p>
        </div>
        <p className="m-0 text-xs text-muted">
          {studiedToday ? '今天已經打卡' : data.streak > 0 ? '今天寫一題就能延續' : '今天寫一題就開始累積'}・最長 {data.longest_streak} 天
        </p>
      </div>

      <div
        role="img"
        aria-label={`近 30 天有 ${recentActive} 天讀書，連續 ${data.streak} 天，最長連續 ${data.longest_streak} 天`}
        className="flex justify-between gap-[3px] sm:justify-start"
        onMouseLeave={() => setPicked(null)}
      >
        <div aria-hidden="true" className="mr-0.5 grid grid-rows-7 gap-[3px] text-[10px] leading-none text-muted">
          {WEEKDAYS.map((name, index) => (
            <span key={name} className={cx('flex h-3.5 items-center sm:h-4', index % 2 === 0 && 'invisible')}>
              {name}
            </span>
          ))}
        </div>
        {weeks.map((week, index) => (
          <div
            key={index}
            aria-hidden="true"
            className={cx('grid grid-rows-7 gap-[3px]', hide(index))}
          >
            {week.map((day, row) =>
              day ? (
                <span
                  key={day.date}
                  title={label(day)}
                  onMouseEnter={() => setPicked(day)}
                  onClick={() => setPicked(day)}
                  className={cx(
                    'size-3.5 rounded-[3px] transition-transform sm:size-4 duration-[var(--dur-fast)] hover:scale-125',
                    day.date === data.today && 'ring-1 ring-ink ring-offset-1 ring-offset-[var(--sheet)]',
                    picked?.date === day.date && 'scale-125',
                  )}
                  style={shade(level(day))}
                />
              ) : (
                <span key={`empty-${row}`} className="size-3.5 sm:size-4" />
              ),
            )}
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span aria-live="polite" className="tabular">
          {picked ? (
            label(picked)
          ) : (
            `近 30 天讀了 ${recentActive} 天`
          )}
        </span>
        <span className="flex items-center gap-1" aria-hidden="true">
          少
          {SHADES.map((_, value) => (
            <span key={value} className="h-3 w-3 rounded-[3px]" style={shade(value)} />
          ))}
          多
        </span>
      </div>
    </section>
  )
}
