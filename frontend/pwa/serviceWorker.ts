/**
 * 產生 service worker（sw.js）的 Vite 外掛：打包時把所有輸出檔列進「App 外殼」快取。
 *
 * - 網頁與 assets：打開過一次之後，沒網路也能開起來（顯示「連不到伺服器」而不是一片空白）。
 * - /api/：一律走網路，資料永遠是最新的，不放快取。
 * - 換頁（navigation）：先試網路，失敗才用快取的首頁；所以有網路時一定拿到新版。
 * - 每次打包的版本號由檔名雜湊算出，新版上線時舊快取會被清掉。
 */

import { createHash } from 'node:crypto'
import type { Plugin } from 'vite'

/** public/ 裡要一起快取的檔案（打包輸出不會列出它們） */
const PUBLIC_FILES = ['/', '/manifest.webmanifest', '/favicon.svg', '/icons/icon-192.png', '/icons/apple-touch-icon.png']

function source(version: string, files: string[]): string {
  return `// 由 frontend/pwa/serviceWorker.ts 產生，不要手改
const CACHE = 'hzd-shell-${version}'
const FONTS = 'hzd-fonts'
const SHELL = ${JSON.stringify(files)}

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith('hzd-shell-') && key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

function remember(cacheName, request, response) {
  if (response.ok || response.type === 'opaque') {
    const copy = response.clone()
    caches.open(cacheName).then((cache) => cache.put(request, copy))
  }
  return response
}

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)

  if (url.origin === self.location.origin && url.pathname.startsWith('/api/')) return

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match('/')))
    return
  }

  if (url.origin === self.location.origin) {
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request).then((response) => remember(CACHE, request, response))))
    return
  }

  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    // 字型：先用快取，背景再更新
    event.respondWith(
      caches.open(FONTS).then((cache) =>
        cache.match(request).then((hit) => {
          const update = fetch(request).then((response) => remember(FONTS, request, response)).catch(() => hit)
          return hit || update
        }),
      ),
    )
  }
})
`
}

export function serviceWorker(): Plugin {
  return {
    name: 'hzd-service-worker',
    apply: 'build',
    generateBundle(_options, bundle) {
      const built = Object.keys(bundle)
        // KaTeX 每種字型都附 .woff2／.woff／.ttf，手機只會用到 woff2；其他的用到時才下載
        .filter((name) => !/\.(map|ttf|woff)$/.test(name))
        .map((name) => `/${name}`)
      const files = [...new Set([...PUBLIC_FILES, ...built])].filter((name) => name !== '/index.html')
      const version = createHash('sha256').update(files.join('\n')).digest('hex').slice(0, 12)
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: source(version, files) })
    },
  }
}
