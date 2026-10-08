/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { serviceWorker } from './pwa/serviceWorker.ts'

export default defineConfig({
  plugins: [react(), tailwindcss(), serviceWorker()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: Number(process.env.LS_WEB_PORT ?? 5173),
    // 開發時把 /api 轉給後端，前端程式一律用相對路徑呼叫 API。
    // LS_API_PORT／LS_WEB_PORT：截圖自檢時另開一組用資料副本的伺服器，不影響使用者正在跑的 8000／5173
    proxy: { '/api': `http://127.0.0.1:${process.env.LS_API_PORT ?? 8000}` },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
