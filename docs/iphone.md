# 在 iPhone 上使用劃重點

做法：電腦跑劃重點，手機透過 **Tailscale** 用 HTTPS 連回電腦，再從 Safari「加入主畫面」，就像一個 App。
不經過 App Store、不用付費開發者帳號；資料只有一份（在電腦的 `data/`），電腦和手機看到的一樣。

> 限制：**電腦要開著而且不能睡眠**。電腦關機時手機打得開 App，但會顯示「連不到劃重點」。

## 一次性設定

1. **啟用 Tailscale Serve 與 HTTPS**（只要做一次）：在電腦執行 `tailscale serve --bg 8765`，第一次會給一個
   `https://login.tailscale.com/f/serve?...` 的網址；用 Tailscale 帳號登入後按同意。之後再執行一次：

   ```bash
   tailscale serve --bg 8765
   tailscale serve status   # 會顯示 https://<電腦名稱>.<tailnet>.ts.net → http://127.0.0.1:8765
   ```

   只有你 Tailscale 網路裡的裝置連得到這個網址，不會公開到網際網路（公開要用 `tailscale funnel`，**不要用**，系統沒有登入）。

2. **啟動劃重點**：雙擊專案根目錄的 `start-server.cmd`（或在終端機 `npm run serve`）。
   它會打包前端、套用資料庫 migration，再在 `127.0.0.1:8765` 啟動。開發用的 `npm run dev`（8000／5173）可以同時開。

3. **開機自動啟動（建議）**：`Win + R` 輸入 `shell:startup`，把 `start-server.cmd` 的捷徑放進去。
   電源選項把「插電時進入睡眠」設成「永不」。

4. **iPhone**：
   1. 安裝並登入 Tailscale App（和電腦同一個帳號），開啟連線。
   2. 用 **Safari** 打開 `https://<電腦名稱>.<tailnet>.ts.net`（網址見 `tailscale serve status`）。
   3. 分享按鈕 →「加入主畫面」。之後從主畫面的「劃重點」圖示打開，會全螢幕執行。

## 日常使用

- 手機要連得上：電腦開著、`start-server.cmd` 在跑、手機的 Tailscale 是連線狀態（在外面用行動網路也可以）。
- 程式更新後重新啟動 `start-server.cmd` 就會重新打包；手機的 App 下次打開會自動換成新版。
- 打開過一次之後，沒網路也能開啟 App 外殼，畫面會提示「連不到劃重點」，不會一片空白。
- AI 功能（助教、評分、拍照辨識）照樣能用：手機送出後由電腦上的 Claude Code 處理。

## 疑難排解

| 狀況 | 處理 |
|---|---|
| 手機顯示「連不到劃重點」 | 電腦是否開著、沒睡眠；`start-server.cmd` 視窗是否還在；手機 Tailscale 是否連線 |
| 網址打不開、憑證錯誤 | `tailscale serve status` 確認有設定；HTTPS 憑證第一次申請要等幾十秒 |
| 加入主畫面後沒有全螢幕 | 要用 Safari 開（不是 Chrome 或 LINE 內建瀏覽器）再「加入主畫面」 |
| 更新後手機還是舊畫面 | 把 App 從多工畫面滑掉再打開；還不行就到 Safari 設定清除這個網站的資料 |

## 技術說明（給維護的人）

- `frontend/pwa/serviceWorker.ts`：打包時產生 `sw.js`，快取 App 外殼；`/api/` 一律走網路。
- `backend/app/core/frontend.py`：後端直接提供 `frontend/dist`，未知路徑回 `index.html`（前端路由）。
- `scripts/serve.mjs`：`npm run serve` 的內容；埠號可用 `LS_SERVE_PORT` 改。
- 圖示：`frontend/scripts/make-icons.py` 產生 `frontend/public/icons/`。
