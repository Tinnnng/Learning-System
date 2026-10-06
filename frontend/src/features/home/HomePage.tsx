import { useEffect, useState } from 'react'
import { fetchHealth } from './api'

type Status = 'loading' | 'ok' | 'error'

export function HomePage() {
  const [status, setStatus] = useState<Status>('loading')

  useEffect(() => {
    fetchHealth()
      .then(() => setStatus('ok'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <section>
      <h1 className="text-2xl font-semibold">首頁</h1>
      <p className="mt-2" role="status">
        後端連線：{{ loading: '檢查中…', ok: '正常', error: '無法連線' }[status]}
      </p>
    </section>
  )
}
