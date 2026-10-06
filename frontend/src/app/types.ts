import type { RouteObject } from 'react-router'
import type { IconName } from '@/components/Icon'

/** 每個 feature 在自己的 index.tsx 匯出 `feature`，由 app/registry.ts 自動收集。 */
export interface FeatureDefinition {
  /** 唯一識別碼，建議與資料夾名稱相同 */
  id: string
  /** 這個 feature 提供的頁面，path 為相對於根目錄的路徑 */
  routes: RouteObject[]
  /** 要顯示在導覽列時才需要填 */
  nav?: {
    label: string
    path: string
    icon: IconName
    /** 數字越小越前面 */
    order: number
    /** 手機版底部分頁列只放主要項目（最多 5 個），其餘只在桌機導覽列 */
    primary?: boolean
  }
}
