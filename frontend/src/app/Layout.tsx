import { NavLink, Outlet, useLocation, useMatches } from 'react-router'
import { useEffect, useState } from 'react'
import { Icon } from '@/components/Icon'
import { ThemeToggle } from '@/components/ThemeToggle'
import { cx } from '@/lib/cx'
import { navItems } from './registry'

/** 品牌：「劃重點」，重點兩個字被螢光筆劃過；滑過時重新刷一次 */
function Wordmark() {
  return (
    <NavLink to="/" className="group flex items-center gap-2" aria-label="劃重點 首頁">
      <Icon name="edit" size={20} className="text-accent transition-transform duration-[var(--dur)] group-hover:-rotate-12" />
      <span className="font-hand text-xl font-bold tracking-wide text-ink">
        劃
        <span className="marker [&::before]:animate-[swipe_var(--dur-marker)_var(--ease-marker)_both] group-hover:[&::before]:animate-none">
          重點
        </span>
      </span>
    </NavLink>
  )
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

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [pathname])

  useEffect(() => {
    if (!moreOpen) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setMoreOpen(false)
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
          <nav aria-label="主要導覽" className="hidden flex-1 md:block">
            <ul className="m-0 flex list-none gap-1 p-0">
              {navItems.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    end={item.path === '/'}
                    className={({ isActive }) =>
                      cx(
                        'group flex h-10 items-center rounded-md px-3 text-sm transition-colors duration-[var(--dur)]',
                        isActive ? 'font-medium text-ink' : 'text-muted hover:text-ink',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <span
                        className={cx(
                          'marker',
                          isActive ? '[--marker-scale:1]' : '[--marker-scale:0] group-hover:[--marker-scale:0.35]',
                        )}
                      >
                        {item.label}
                      </span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <ThemeToggle className="ml-auto" />
        </div>
      </header>

      <main
        id="main"
        className={cx('mx-auto max-w-[var(--content-width)] px-4 pt-8 sm:px-6 md:pb-16 md:pt-10', focus ? 'pb-10' : 'pb-28')}
      >
        <Outlet />
      </main>

      {/* 手機版「更多」選單：從底部分頁列上方展開 */}
      {moreOpen && !focus && (
        <div className="fixed inset-0 z-20 md:hidden">
          <button
            type="button"
            aria-label="關閉選單"
            className="absolute inset-0 bg-ink/25 animate-[fade-in_var(--dur)_var(--ease-out)]"
            onClick={() => setMoreOpen(false)}
          />
          <nav
            id="more-menu"
            aria-label="更多頁面"
            className="absolute inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom,0px))] rounded-t-lg border-t border-line bg-sheet px-4 pt-4 pb-3 shadow-sheet animate-[rise-in_var(--dur)_var(--ease-out)]"
          >
            <ul className="m-0 grid list-none grid-cols-4 gap-1 p-0">
              {overflow.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    onClick={() => setMoreOpen(false)}
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
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper/92 pb-[env(safe-area-inset-bottom,0px)] backdrop-blur-md md:hidden"
      >
        <ul
          className="m-0 grid list-none p-0"
          style={{ gridTemplateColumns: `repeat(${primary.length + (overflow.length > 0 ? 1 : 0)}, 1fr)` }}
        >
          {primary.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  cx(
                    'flex h-16 flex-col items-center justify-center gap-1 text-[11px] transition-colors',
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
                type="button"
                aria-expanded={moreOpen}
                aria-controls="more-menu"
                onClick={() => setMoreOpen(!moreOpen)}
                className={cx(
                  'flex h-16 w-full flex-col items-center justify-center gap-1 text-[11px] transition-colors',
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
