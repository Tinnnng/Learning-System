import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
import { ErrorState, Loading } from '@/components/States'
import { fetchSession } from './api'
import { ResultView } from './ResultView'
import { TakingView } from './TakingView'

export function ExamPage() {
  const id = Number(useParams().sessionId)
  const session = useQuery({ queryKey: ['exam', 'session', id], queryFn: () => fetchSession(id), staleTime: Infinity })

  if (session.isPending) return <Loading label="準備試卷中" />
  if (session.isError) return <ErrorState error={session.error} onRetry={() => session.refetch()} />
  return session.data.submitted_at ? (
    <ResultView session={session.data} />
  ) : (
    <TakingView key={session.data.id} session={session.data} />
  )
}
