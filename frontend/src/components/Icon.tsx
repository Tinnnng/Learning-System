/** 線條圖示（1.6px 筆畫、圓頭），風格統一，不依賴外部圖示套件。 */

const PATHS = {
  today: 'M5 4.5h14a1.5 1.5 0 0 1 1.5 1.5v13A1.5 1.5 0 0 1 19 20.5H5A1.5 1.5 0 0 1 3.5 19V6A1.5 1.5 0 0 1 5 4.5ZM3.5 9h17M8 3v3M16 3v3M8 13.5h3',
  bank: 'M6 3.5h9l3.5 3.5v13.5H6ZM15 3.5V7h3.5M9 11h6.5M9 14.5h6.5M9 18h4',
  wrong: 'M6 3.5h12v17H6ZM9 8.5l6 6M15 8.5l-6 6',
  vocab: 'M4 18.5 8.5 6l4.5 12.5M5.6 14h5.8M15 13.5c0-1.6 1.2-2.5 2.6-2.5 1.5 0 2.4.9 2.4 2.5v5M20 15.5c-3.5 0-5 .7-5 1.8 0 .9.7 1.4 1.8 1.4 1.8 0 3.2-1.3 3.2-3.2',
  overview: 'M4 20.5h16M7 17v-5M12 17V7M17 17v-8',
  import: 'M12 3.5v11M7.5 10l4.5 4.5 4.5-4.5M4.5 15.5v3.5A1.5 1.5 0 0 0 6 20.5h12a1.5 1.5 0 0 0 1.5-1.5v-3.5',
  sun: 'M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4',
  moon: 'M19.5 14.5A7.5 7.5 0 0 1 9.5 4.5a7.5 7.5 0 1 0 10 10Z',
  system: 'M3.5 5.5h17v11h-17ZM9 20.5h6M12 16.5v4',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  back: 'M19 12H5M11 6l-6 6 6 6',
  check: 'M5 12.5 10 17.5 19 7',
  close: 'M6 6l12 12M18 6 6 18',
  clock: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17ZM12 7.5V12l3 2',
  shuffle: 'M3.5 7h3.5c4 0 6 10 10 10h3.5M17.5 13.5 21 17l-3.5 3.5M3.5 17h3.5c1.6 0 2.8-1.6 3.8-3.5M14 8.5c.9-.9 1.9-1.5 3-1.5h4M17.5 3.5 21 7l-3.5 3.5',
  play: 'M8 5.5v13l10.5-6.5Z',
  list: 'M9 6.5h11M9 12h11M9 17.5h11M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01',
  page: 'M4 4.5h16v15H4ZM4 8.5h16',
  flag: 'M5.5 21V4M5.5 4.5h11l-2.5 4 2.5 4h-11',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20.5 20.5 16 16',
  refresh: 'M20 11a8 8 0 0 0-14.5-4.5M4 4.5V8h3.5M4 13a8 8 0 0 0 14.5 4.5M20 19.5V16h-3.5',
} as const

export type IconName = keyof typeof PATHS

interface IconProps {
  name: IconName
  size?: number
  className?: string
  /** 有意義的圖示要給 label；純裝飾不給 */
  label?: string
}

export function Icon({ name, size = 20, className, label }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={name === 'play' ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
