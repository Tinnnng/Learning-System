/** 日夜間模式：預設跟隨系統，可手動切換並記住（localStorage）。index.html 有同樣邏輯避免閃爍。 */

import { useEffect, useState } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'ls-theme'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

export function readPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

export function resolveTheme(preference: ThemePreference, systemDark: boolean): 'light' | 'dark' {
  if (preference === 'system') return systemDark ? 'dark' : 'light'
  return preference
}

function apply(preference: ThemePreference) {
  const dark = resolveTheme(preference, media().matches) === 'dark'
  document.documentElement.classList.toggle('dark', dark)
}

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(readPreference)

  useEffect(() => {
    apply(preference)
    try {
      if (preference === 'system') localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, preference)
    } catch {
      // 無法存取 localStorage（例如私密模式）時只在本次生效
    }
    if (preference !== 'system') return
    const query = media()
    const onChange = () => apply('system')
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [preference])

  return { preference, setPreference }
}
