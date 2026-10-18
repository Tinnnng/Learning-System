/** 首頁開著過了午夜（或手機 App 從背景切回來已經是隔天）：重新抓所有資料，抽籤、讀書日曆、每日單字都換成新的一天。 */

import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { isoDay } from '@/lib/format'

export function useDayChange(): string {
  const queryClient = useQueryClient()
  const [day, setDay] = useState(isoDay)
  useEffect(() => {
    const check = () => {
      const now = isoDay()
      setDay((previous) => {
        if (previous !== now) void queryClient.invalidateQueries()
        return now
      })
    }
    const timer = window.setInterval(check, 60_000)
    const onVisible = () => {
      if (!document.hidden) check()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [queryClient])
  return day
}
