/**
 * 模組邊界檢查，對應 CLAUDE.md 的模組化原則：
 * - feature 之間不可以互相 import，共用的東西放 components/ 或 lib/
 * - feature 不可以 import app/registry（避免循環依賴），只能用 app/types
 * - components/ 與 lib/ 不可以依賴任何 feature
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { describe, expect, it } from 'vitest'

const SRC = resolve(__dirname, '..')
const IMPORT_PATTERN = /(?:import|export)[^'"]*?from\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)/g

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sourceFiles(path)
    return /\.(ts|tsx)$/.test(name) ? [path] : []
  })
}

/** 把 import 路徑轉成相對於 src 的路徑；外部套件回傳 null */
function resolveImport(file: string, specifier: string): string | null {
  if (specifier.startsWith('@/')) return specifier.slice(2)
  if (specifier.startsWith('.')) return relative(SRC, resolve(dirname(file), specifier)).split(sep).join('/')
  return null
}

function importsOf(file: string): string[] {
  const content = readFileSync(file, 'utf8')
  return [...content.matchAll(IMPORT_PATTERN)]
    .map((match) => resolveImport(file, match[1] ?? match[2]))
    .filter((target): target is string => target !== null)
}

const srcPath = (file: string) => relative(SRC, file).split(sep).join('/')

describe('模組邊界', () => {
  it('feature 之間不互相 import，也不 import app/registry', () => {
    const violations = sourceFiles(join(SRC, 'features')).flatMap((file) => {
      const owner = srcPath(file).split('/')[1]
      return importsOf(file)
        .filter((target) => {
          const [top, featureName] = target.split('/')
          return (top === 'features' && featureName !== owner) || target.startsWith('app/registry')
        })
        .map((target) => `${srcPath(file)} → ${target}`)
    })
    expect(violations).toEqual([])
  })

  it('components 與 lib 不依賴 feature', () => {
    const files = ['components', 'lib'].flatMap((dir) => sourceFiles(join(SRC, dir)))
    const violations = files.flatMap((file) =>
      importsOf(file)
        .filter((target) => target.startsWith('features/'))
        .map((target) => `${srcPath(file)} → ${target}`),
    )
    expect(violations).toEqual([])
  })
})
