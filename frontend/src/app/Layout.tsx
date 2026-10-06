import { NavLink, Outlet } from 'react-router'
import { navItems } from './registry'

// 暫時的版面骨架，正式視覺於階段 5 設計
export function Layout() {
  return (
    <div className="min-h-dvh bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <header className="flex gap-4 border-b border-neutral-200 px-6 py-4 dark:border-neutral-800">
        <span className="font-semibold">Learning-System</span>
        <nav className="flex gap-3">
          {navItems.map((item) => (
            <NavLink key={item.path} to={item.path} className={({ isActive }) => (isActive ? 'underline' : '')}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
