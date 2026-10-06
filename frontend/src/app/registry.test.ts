import { describe, expect, it } from 'vitest'
import { collectFeatures, features, navItems } from './registry'

describe('feature registry', () => {
  it('自動收集 features 資料夾下的所有 feature', () => {
    expect(features.map((feature) => feature.id)).toContain('home')
  })

  it('導覽項目依 order 排序', () => {
    const orders = navItems.map((item) => item.order)
    expect(orders).toEqual([...orders].sort((a, b) => a - b))
  })

  it('feature id 重複時報錯', () => {
    const feature = { id: 'dup', routes: [] }
    expect(() => collectFeatures({ a: { feature }, b: { feature } })).toThrow('feature id 重複：dup')
  })

  it('沒有匯出 feature 時報錯', () => {
    expect(() => collectFeatures({ '../features/x/index.tsx': {} })).toThrow('必須匯出 feature')
  })
})
