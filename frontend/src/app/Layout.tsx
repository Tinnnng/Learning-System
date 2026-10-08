import { NavLink, Outlet, useLocation, useMatches } from 'react-router'
import { type RefObject, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Icon } from '@/components/Icon'
import { ThemeToggle } from '@/components/ThemeToggle'
import { cx } from '@/lib/cx'
import { navItems } from './registry'

/** 品牌：原子筆圖示＋「劃重點」；滑過時筆尖在紙上寫兩下 */
function Wordmark() {
  return (
    <NavLink to="/" className="group flex items-center gap-2" aria-label="劃重點 首頁">
      <Icon name="edit" size={20} className="origin-bottom-left text-accent group-hover:animate-[scribble_520ms_var(--ease-out)]" />
      <span className="font-display text-lg font-bold tracking-[0.06em] text-ink">劃重點</span>
    </NavLink>
  )
}

interface InkBar {
  left: number
  width: number
}

/**
 * 導覽列底下那條原子筆線的位置：量出目前頁面連結（aria-current）的文字寬度。
 * 換頁時線會從舊項目滑到新項目；第一次定位不播動畫，避免從最左邊滑進來。
 */
function useInkBar(listRef: RefObject<HTMLElement | null>, pathname: string) {
  const [bar, setBar] = useState<InkBar | null>(null)
  const [animate, setAnimate] = useState(false)
  useLayoutEffect(() => {
    const measure = () => {
      const list = listRef.current
      const active = list?.querySelector<HTMLElement>('a[aria-current="page"] [data-ink-label]')
      if (!list || !active) return setBar(null)
      const listBox = list.getBoundingClientRect()
      const box = active.getBoundingClientRect()
      setBar({ left: box.left - listBox.left, width: box.width })
    }
    measure()
    void document.fonts?.ready.then(measure)
    window.addEventListener('resize', measure)
    const frame = requestAnimationFrame(() => setAnimate(true))
    return () => {
      window.removeEventListener('resize', measure)
      cancelAnimationFrame(frame)
    }
  }, [listRef, pathname])
  return { bar, animate }
}

export function Layout() {
  const { pathname } = useLocation()
  const primary = navItems.filter((item) => item.primary).slice(0, 5)
  // 不在底部分頁列的項目收進「更多」
  const overflow = navItems.filter((item) => !primary.includes(item))
  const [moreOpen, setMoreOpen] = useState(false)
  const overflowActive = overflow.some((item) => pathname.startsWith(item.path))
  // 作答等需要專注的頁面（route handle: { focus: true }）隱藏手機底部分頁列
  const focus = useMatches().some((match) => (match.handle as { focus?: boolean } | undefined)?.focus)
  const navRef = useRef<HTMLUListElement>(null)
  const ink = useInkBar(navRef, pathname)
  const primaryIndex = primary.findIndex((item) =>
    item.path === '/' ? pathname === '/' : pathname === item.path || pathname.startsWith(`${item.path}/`),
  )
  const tabIndex = primaryIndex >= 0 ? primaryIndex : overflowActive || moreOpen ? primary.length : -1
  const tabCount = primary.length + (overflow.length > 0 ? 1 : 0)

  // 換頁：捲到頂端、瀏覽器分頁標題換成這頁的標題（WCAG 2.4.2），
  // 用鍵盤或螢幕閱讀器的人換頁後焦點移到新頁的 h1，才知道到了哪裡（第一次載入不移，避免打斷）
  const firstRoute = useRef(true)
  useEffect(() => {
    window.scrollTo({ top: 0 })
    const fallback = navItems.find((item) => (item.path === '/' ? pathname === '/' : pathname.startsWith(item.path)))?.label
    const timer = window.setTimeout(() => {
      const heading = document.querySelector<HTMLElement>('main h1')
      const name = heading?.textContent?.trim() || fallback
      document.title = name ? `${name}｜劃重點` : '劃重點'
      if (!firstRoute.current && heading) {
        heading.tabIndex = -1
        heading.focus({ preventScroll: true })
      }
      firstRoute.current = false
    }, 350)
    return () => window.clearTimeout(timer)
  }, [pathname])

  const moreButton = useRef<HTMLButtonElement>(null)
  const moreMenu = useRef<HTMLElement>(null)
  const closeMore = (returnFocus: boolean) => {
    setMoreOpen(false)
    if (returnFocus) moreButton.current?.focus()
  }
  useEffect(() => {
    if (!moreOpen) return
    moreMenu.current?.querySelector<HTMLElement>('a')?.focus()  // 打開時焦點移進選單
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMoreOpen(false)
        moreButton.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [moreOpen])

  return (
    <div className="min-h-dvh bg-paper text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-ink focus:px-4 focus:py-2 focus:text-paper"
      >
        跳到主要內容
      </a>

      <header className="sticky top-[env(safe-area-inset-top,0px)] z-30 border-b border-line bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[var(--content-width)] items-center gap-6 px-4 sm:px-6">
          <Wordmark />
          <nav aria-label="主要導覽" className="hidden flex-1 lg:block">
            <ul ref={navRef} className="relative m-0 flex list-none gap-1 p-0">
              {navItems.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    end={item.path === '/'}
                    className={({ isActive }) =>
                      cx(
                        'group flex h-10 items-center whitespace-nowrap rounded-md px-3 text-sm transition-colors duration-[var(--dur)]',
                        isActive ? 'font-medium text-ink' : 'text-muted hover:text-ink',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <span data-ink-label className={cx(!isActive && 'pen-underline [--pen:var(--rule)]')}>
                        {item.label}
                      </span>
                    )}
                  </NavLink>
                </li>
              ))}
              {/* 目前頁面的原子筆底線：換頁時滑到新的項目 */}
              <li
                aria-hidden="true"
                className={cx(
                  'pointer-events-none absolute -bottom-[13px] left-0 h-[2px] rounded-full bg-accent',
                  ink.animate && 'transition-[transform,width,opacity] duration-[var(--dur-slow)] ease-[var(--ease-pen)]',
                )}
                style={{
                  width: ink.bar?.width ?? 0,
                  transform: `translateX(${ink.bar?.left ?? 0}px)`,
                  opacity: ink.bar ? 1 : 0,
                }}
              />
            </ul>
          </nav>
          <ThemeToggle className="ml-auto" />
        </div>
      </header>

      <main
        id="main"
        className={cx('mx-auto max-w-[var(--content-width)] px-4 pt-8 sm:px-6 lg:pb-16 lg:pt-10', focus ? 'pb-10' : 'pb-28')}
      >
        {/* 換頁時重新掛載，讓頁面區塊依序進場；作答頁有自己的翻頁動畫，不另外加 */}
        <div key={pathname} className={focus ? undefined : 'route-enter'}>
          <Outlet />
        </div>
      </main>

      {/* 手機版「更多」選單：從底部分頁列上方展開 */}
      {moreOpen && !focus && (
        <div className="fixed inset-0 z-20 lg:hidden">
          <button
            type="button"
            aria-label="關閉選單"
            className="absolute inset-0 bg-ink/25 animate-[fade-in_var(--dur)_var(--ease-out)]"
            onClick={() => closeMore(true)}
          />
          <nav
            ref={moreMenu}
            id="more-menu"
            aria-label="更多頁面"
            className="absolute inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom,0px))] rounded-t-lg border-t border-line bg-sheet px-4 pt-4 pb-3 shadow-sheet animate-[rise-in_var(--dur)_var(--ease-out)]"
          >
            <ul className="m-0 grid list-none grid-cols-4 gap-1 p-0">
              {overflow.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    onClick={() => closeMore(false)}
                    className={({ isActive }) =>
                      cx(
                        'flex h-18 flex-col items-center justify-center gap-1.5 rounded-md text-xs transition-colors active:bg-accent-faint',
                        isActive ? 'bg-accent-faint text-accent' : 'text-ink-soft',
                      )
                    }
                  >
                    <Icon name={item.icon} size={22} />
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      )}

      {/* 手機版底部分頁列 */}
      <nav
        hidden={focus}
        aria-label="主要導覽"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper/92 pb-[env(safe-area-inset-bottom,0px)] backdrop-blur-md lg:hidden"
      >
        {/* 目前分頁上方的短線：換分頁時滑過去 */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute top-0 left-0 flex justify-center transition-[transform,opacity] duration-[var(--dur-slow)] ease-[var(--ease-pen)]"
          style={{
            width: `${100 / tabCount}%`,
            transform: `translateX(${Math.max(tabIndex, 0) * 100}%)`,
            opacity: tabIndex >= 0 ? 1 : 0,
          }}
        >
          <span className="h-[2px] w-7 rounded-full bg-accent" />
        </span>
        <ul className="m-0 grid list-none p-0" style={{ gridTemplateColumns: `repeat(${tabCount}, 1fr)` }}>
          {primary.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  cx(
                    'flex h-16 flex-col items-center justify-center gap-1 text-xs transition-colors active:bg-accent-faint',
                    isActive ? 'text-accent' : 'text-muted',
                  )
                }
              >
                <Icon name={item.icon} size={22} />
                {item.label}
              </NavLink>
            </li>
          ))}
          {overflow.length > 0 && (
            <li>
              <button
                ref={moreButton}
                type="button"
                aria-expanded={moreOpen}
                aria-controls="more-menu"
                onClick={() => setMoreOpen(!moreOpen)}
                className={cx(
                  'flex h-16 w-full flex-col items-center justify-center gap-1 text-xs transition-colors active:bg-accent-faint',
                  moreOpen || overflowActive ? 'text-accent' : 'text-muted',
                )}
              >
                <Icon name={moreOpen ? 'close' : 'more'} size={22} />
                更多
              </button>
            </li>
          )}
        </ul>
      </nav>
    </div>
  )
}
