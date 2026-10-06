import { api } from '@/lib/api'

export interface Health {
  status: string
  database: string
}

export const fetchHealth = () => api.get<Health>('/system/health')
