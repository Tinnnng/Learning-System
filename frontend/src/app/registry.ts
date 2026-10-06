import type { FeatureDefinition } from './types'

/**
 * 自動收集 src/features/<名稱>/index.tsx 匯出的 feature。
 * 新增頁面只要建立新的 feature 資料夾，不需要修改這個檔案或其他 feature。
 */
const featureModules = import.meta.glob<{ feature: FeatureDefinition }>('../features/*/index.{ts,tsx}', {
  eager: true,
})

export function collectFeatures(modules: Record<string, { feature?: FeatureDefinition }>): FeatureDefinition[] {
  const features = Object.entries(modules).map(([path, module]) => {
    if (!module.feature) {
      throw new Error(`${path} 必須匯出 feature（FeatureDefinition）`)
    }
    return module.feature
  })

  const seen = new Set<string>()
  for (const { id } of features) {
    if (seen.has(id)) throw new Error(`feature id 重複：${id}`)
    seen.add(id)
  }
  return features
}

export const features = collectFeatures(featureModules)

export const routes = features.flatMap((feature) => feature.routes)

export const navItems = features
  .flatMap((feature) => (feature.nav ? [feature.nav] : []))
  .sort((a, b) => a.order - b.order)
