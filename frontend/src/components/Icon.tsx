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
  spark: 'M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9ZM18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8Z',
  camera: 'M4 7.5h3.5L9 5h6l1.5 2.5H20A1.5 1.5 0 0 1 21.5 9v9A1.5 1.5 0 0 1 20 19.5H4A1.5 1.5 0 0 1 2.5 18V9A1.5 1.5 0 0 1 4 7.5ZM12 10a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z',
  home: 'M4 10.5 12 4l8 6.5V20h-5.5v-6h-5v6H4Z',
  star: 'M12 3.8l2.5 5.2 5.7.8-4.1 4 1 5.6L12 16.7l-5.1 2.7 1-5.6-4.1-4 5.7-.8Z',
  note: 'M5 4.5h14v10.5l-4.5 4.5H5ZM14.5 19.5V15H19M8.5 9h7M8.5 12.5h4',
  plus: 'M12 5v14M5 12h14',
  edit: 'M4.5 19.5h4l10-10-4-4-10 10ZM13 7l4 4',
  more: 'M5.5 12h.01M12 12h.01M18.5 12h.01',
  archive: 'M3.5 4.5h17v4h-17ZM5 8.5v11h14v-11M10 12.5h4',
  trash: 'M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13M10 11v5.5M14 11v5.5',
  left: 'M15 5l-7 7 7 7',
  right: 'M9 5l7 7-7 7',
  send: 'M4 12 20 4l-6 16-2.5-6.5Z',
  refresh: 'M20 11a8 8 0 0 0-14.5-4.5M4 4.5V8h3.5M4 13a8 8 0 0 0 14.5 4.5M20 19.5V16h-3.5',
} as const

export type IconName = keyof typeof PATHS

interface IconProps {
  name: IconName
  size?: number
  className?: string
  /** 有意義的圖示要給 label；純裝飾不給 */
  label?: string
  /** 實心（目前只有星號用） */
  filled?: boolean
}

export function Icon({ name, size = 20, className, label, filled }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={name === 'play' || (name === 'star' && filled) ? 'currentColor' : 'none'}
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
