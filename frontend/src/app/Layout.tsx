import { NavLink, Outlet, useLocation, useMatches } from 'react-router'
import { useEffect } from 'react'
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
  // 作答等需要專注的頁面（route handle: { focus: true }）隱藏手機底部分頁列
  const focus = useMatches().some((match) => (match.handle as { focus?: boolean } | undefined)?.focus)

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [pathname])

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

      {/* 手機版底部分頁列 */}
      <nav
        hidden={focus}
        aria-label="主要導覽"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper/92 pb-[env(safe-area-inset-bottom,0px)] backdrop-blur-md md:hidden"
      >
        <ul className="m-0 grid list-none p-0" style={{ gridTemplateColumns: `repeat(${primary.length}, 1fr)` }}>
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
        </ul>
      </nav>
    </div>
  )
}
