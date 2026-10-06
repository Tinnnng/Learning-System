// 設計自檢用：把主要頁面在桌機／手機、日間／夜間各截一張圖。
// 用法：先 npm run dev，再執行 node scripts/screenshots.mjs <輸出資料夾> [頁面路徑...]
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from '@playwright/test'

const BASE = process.env.BASE_URL ?? 'http://localhost:5173'
const outDir = process.argv[2] ?? 'screenshots'
const pages = process.argv.slice(3).length
  ? process.argv.slice(3)
  : ['/', '/bank', '/review', '/overview', '/vocab', '/vocab/words', '/import']

const viewports = {
  desktop: { width: 1280, height: 860 },
  mobile: { width: 390, height: 844 },
}

mkdirSync(outDir, { recursive: true })
const browser = await chromium.launch()
for (const [device, viewport] of Object.entries(viewports)) {
  for (const theme of ['light', 'dark']) {
    const context = await browser.newContext({ viewport, deviceScaleFactor: 1, colorScheme: theme })
    await context.addInitScript((value) => localStorage.setItem('ls-theme', value), theme)
    const page = await context.newPage()
    for (const path of pages) {
      await page.goto(BASE + path, { waitUntil: 'networkidle' })
      await page.waitForTimeout(500)
      const name = `${path.replace(/[/:]+/g, '_').replace(/^_|_$/g, '') || 'home'}-${device}-${theme}.png`
      await page.screenshot({ path: join(outDir, name), fullPage: true })
      console.log(name)
    }
    await context.close()
  }
}
await browser.close()
