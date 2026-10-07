// 讓同一個 Wi-Fi 的手機連進來用（npm run dev:lan）。
// 只綁定家用區網的 IP，不用 --host 0.0.0.0：VPN（Radmin、Tailscale…）與虛擬網卡上的其他人才連不到。
// 系統沒有登入機制，同網路的人都能看到資料、使用 AI 額度，只在信任的家用網路使用。
// 自動判斷不準時，用環境變數 LS_LAN_HOST 指定，例如 LS_LAN_HOST=192.168.0.110 npm run dev:lan
import { spawn } from 'node:child_process'
import { networkInterfaces } from 'node:os'

const VIRTUAL = /vEthernet|VirtualBox|VMware|Hyper-V|Radmin|Tailscale|ZeroTier|Hamachi|WSL|Docker|VPN|Loopback|Bluetooth|藍牙/i
const VIRTUAL_MAC = /^(0a:00:27|00:15:5d|00:50:56|00:0c:29|00:05:69)/i // VirtualBox、Hyper-V、VMware
const PREFERRED = /Wi-?Fi|WLAN|無線|Wireless|Ethernet|乙太網路/i

function isPrivate(address) {
  const [a, b] = address.split('.').map(Number)
  return a === 10 || (a === 192 && b === 168) || (a === 172 && b >= 16 && b <= 31)
}

function pickLanAddress() {
  const candidates = []
  for (const [name, addresses] of Object.entries(networkInterfaces())) {
    for (const entry of addresses ?? []) {
      if (entry.family !== 'IPv4' || entry.internal || !isPrivate(entry.address)) continue
      if (VIRTUAL.test(name) || VIRTUAL_MAC.test(entry.mac) || entry.address.startsWith('192.168.56.')) continue
      candidates.push({ name, address: entry.address, preferred: PREFERRED.test(name) })
    }
  }
  candidates.sort((a, b) => Number(b.preferred) - Number(a.preferred))
  return candidates[0]
}

const chosen = process.env.LS_LAN_HOST ? { name: 'LS_LAN_HOST', address: process.env.LS_LAN_HOST } : pickLanAddress()
if (!chosen) {
  console.error('找不到家用區網的 IP（Wi-Fi／乙太網路）。請用 LS_LAN_HOST=你的區網 IP 指定。')
  process.exit(1)
}

console.log(`\n手機請連：http://${chosen.address}:5173/   （網卡：${chosen.name}）`)
console.log('⚠ 沒有登入機制，同一個網路的人都能使用；只在信任的家用 Wi-Fi 開，用完就關掉。\n')

const vite = spawn('npx', ['vite', '--host', chosen.address, '--strictPort', ...process.argv.slice(2)], { stdio: 'inherit', shell: true })
vite.on('exit', (code) => process.exit(code ?? 0))
