// 正式使用（含手機）：打包前端 → 套用資料庫 migration → 用單一伺服器提供網頁與 API。
// 用法：npm run serve（不想重新打包時加 -- --no-build）
// 只聽 127.0.0.1，外面連不進來；手機透過 Tailscale 連（tailscale serve 把 HTTPS 轉到這個埠），見 docs/iphone.md。
// 用的是真正的資料（data/），和開發用的 npm run dev（8000／5173）不衝突，可以同時開。
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const port = process.env.LS_SERVE_PORT ?? '8765'
const shell = process.platform === 'win32'

function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', shell })
  if (result.status !== 0) process.exit(result.status ?? 1)
}

if (!process.argv.includes('--no-build')) {
  console.log('▸ 打包前端…')
  run('npm', ['run', 'build'], join(root, 'frontend'))
}
console.log('▸ 套用資料庫 migration…')
run('uv', ['run', 'alembic', 'upgrade', 'head'], join(root, 'backend'))

console.log(`▸ 劃重點已啟動：電腦開 http://127.0.0.1:${port}`)
console.log('  手機：Tailscale 連線後開 https://<這台電腦的名稱>.<tailnet>.ts.net（設定見 docs/iphone.md）')
console.log('  關閉：按 Ctrl+C')
const server = spawn(
  'uv',
  ['run', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', port],
  { cwd: join(root, 'backend'), stdio: 'inherit', shell },
)
server.on('exit', (code) => process.exit(code ?? 0))
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.kill(signal))
