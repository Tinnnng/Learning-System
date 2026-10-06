import { api } from '@/lib/api'
import type { ConvertedFile, ImportBundle, ImportOutcome } from '@/lib/types'

export const fetchConverted = () => api.get<ConvertedFile[]>('/ingest/files')
export const fetchBundle = (name: string) => api.get<ImportBundle>(`/ingest/files/${encodeURIComponent(name)}`)
export const importFile = (name: string) => api.post<ImportOutcome>(`/ingest/files/${encodeURIComponent(name)}/import`)
