import { useEffect, useState } from 'react'

/** 值停止變動 delay 毫秒後才更新（打字搜尋時不要每個字都查一次） */
export function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(timer)
  }, [value, delay])
  return debounced
}
