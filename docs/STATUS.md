# 目前進度（交接用）

> 最後更新：2026-10-12。開新對話時先讀這份，再看 `CHECKLIST.md`（逐項進度的唯一來源）與 `CLAUDE.md`（決策與規則）。
> **2026-10-09 之後的 commit 都還沒推送**（edd8a0a 起共 5 個）；使用者說「推送上去」再推。

## 一句話

所有規劃中的功能都已完成，使用者每天在用（電腦＋iPhone）。最近三輪：
- 2026-10-09：兩份稽核剩下的項目全部做完（無障礙中低優先；並行寫入用 `core/database.begin_write`；名稱與網址正規化；AI 失敗呼叫也記用量）。
- 2026-10-12 使用者回饋第 2 輪：單字新規則與「已學會單字」分頁、清除單字進度／清除作答紀錄、匯入頁可以自己上傳並轉檔。
- 2026-10-12 首頁左下補上讀書日曆＋連續天數、番茄鐘＋白噪音、每日抽籤（使用者要求「也來點娛樂」，並注意手機版）。

**下一步沒有指定**：等使用者回饋；可做的事見下方「還沒做的」。

## 已完成的功能（後端模組 → 前端頁面）

| 功能 | 後端模組 | 前端 | 重點 |
|---|---|---|---|
| 題庫、分類、全文搜尋 | `bank` | 題庫、分組頁 `/bank/group`、試卷頁、`/bank/search` | 只用考試類型／年度篩選，同年度＋考試＋類科合成一組；手動新增的題目重新匯入不會被覆蓋；題庫頁右欄有「清除作答紀錄」 |
| 匯入 | `ingest` | 匯入 `/import`、預覽 `/import/:name` | 見下方「匯入的兩條路」 |
| 出題作答 | `exam` | 作答、結果頁 | 練習／模擬考、打亂、計時、一題一頁／整卷；單鍵快捷鍵可關 |
| 申論題 | `exam`＋`review` | 作答頁內 | 打字作答、勾得分要點自評、可請 AI 評分 |
| 錯題本、總覽 | `review` | 錯題本、總覽、PDF 匯出 | 連續答對 5 次移出（「正」字）；FSRS |
| 英文單字 | `vocab` | 每日複習、錯題單字、已學會單字、單字庫 | 見下方「單字規則」 |
| 系統內 AI | `ai`、`tutor` | AI 助教 | 本機 Claude Code CLI（Haiku 4.5）；按鈕才用；可中斷；顯示用量 |
| 行事曆 | `calendar` | 行事曆、首頁倒數 | 手動、照片／PDF AI 辨識、訂閱 iCal、匯出 .ics；月曆可用方向鍵 |
| 收藏筆記、知識點弱點、備份還原 | `notes`、`topics`、`backup` | 收藏、弱點、備份 | 快照種類：自動／手動／還原前／清除前 |
| 讀書日曆、每日抽籤 | `activity` | 首頁左下 | 日曆從作答紀錄（review、vocab 的 `answer_times`）算；抽籤一天一支存 `daily_fortune` |
| 番茄鐘、白噪音 | （純前端） | 首頁左下＋頁首小計時 | `lib/pomodoro.ts`（全站共用、用結束時刻計算、存 localStorage）、`lib/noise.ts`（Web Audio 合成雨聲／海浪／風扇／白噪音） |
| iPhone 版 | `core/frontend.py` | PWA | `npm run serve`／`start-server.cmd` 在 127.0.0.1:8765；手機經 `tailscale serve` 的 HTTPS，見 `docs/iphone.md` |

### 單字規則（2026-10-12 使用者決定，也寫在 CLAUDE.md）
- 沒錯過的字**連續答對 3 次**＝已學會，不再出現在每日單字；中途答錯一次進錯題單字，錯題要**連續答對 5 次**才移出。
- 每日 5 字＝學習中＋錯題最多 2 個（到期的先、再來最久沒寫的）＋隨機新字，順序打亂；錯題集中複習一次 5 個。
- 設定在 `core/config.py`：`word_new_mastery_streak`、`word_mastery_streak`、`daily_review_slots`、`daily_vocab_count`。

### 匯入的兩條路（2026-10-12 使用者選「兩種都做」）
- **網頁上自己轉**（`ingest/uploads.py`）：題目文字檔直接進 `data/converted/`；高普考 PDF 上傳到 `data/inbox/gaopu/uploads/<年度><考試>QA-<類科>/`，可「自動轉檔」（不用 AI）或「AI 校對後轉檔」（一頁一次）；教材上傳到 `data/inbox/lecture/`，「AI 出題」。系統轉的檔案帶 `review_notes`，預覽頁列成提醒，改過該題就拿掉。
- **交給 Claude Code 離線轉**（品質最好）：照 `docs/ingest-gaopu.md`、`docs/ingest-lecture.md`；上傳的檔案位置也寫在文件裡。Claude Code build 出來的檔案沒有 `review_notes`，系統不會再覆蓋它。
- 實測（115 普考法學知識與英文，自動轉檔不用 AI）：答案 50 題全對，但 11 題填空底線消失、10 題克漏字文章要補、6 題選項要修 → AI 校對或人工確認要處理的就是這些。

## 使用者真正的資料庫（`data/learning.db`）現況（2026-10-12）

- migration 版本：`0784495984dc`（最新，使用者重開過伺服器）。
- 15 份試卷、358 題（申論 58 題）：115 年高普考一般行政與資訊處理類科＋期中考 JAVA 第 1 章 15 題。
- 單字 929 個。使用者 10/12 20:51 按過「清除單字進度」（有 `learning-20261012-205113-before-reset.zip` 快照），之後單字進度 5 筆、單字作答 5 筆。
- 題目作答 10 筆、測驗 1 次、錯題本 1 題、行事曆 3 個事件與 2 個訂閱。AI 累計 41 次、約 0.24 美元。
- 知識點：12 科已標記（JAVA 第 1 章尚未標記）。
- 每天第一次啟動自動備份到 `data/backups/`；最近一次 `learning-20261012-115539-auto.zip`。

## 還沒做的（都在 CHECKLIST）

1. 使用者還沒實際按過「AI 校對後轉檔」「AI 出題」（會花額度，只用 FakeProvider 測過），等他回報結果再調整 prompt（`uploads.py` 的 `PROOFREAD_SYSTEM`、`LECTURE_SYSTEM`）。
2. 「清除作答紀錄／單字進度」會連讀書日曆一起清空（日曆是從作答紀錄算的）；已告知使用者，若他希望日曆保留，要另外記每日活動。
3. **iPhone 實機**：使用者 10/12 用手機連不上，原因是手機的 Tailscale 沒開（`tailscale status` 顯示 iphone171 離線 56 天）；已教他打開 Tailscale 後用 `https://desktop-v3393bq.taila1733a.ts.net`。還沒回報是否成功，以及拍照辨識、AI 助教、番茄鐘在手機上的情形（iPhone 鎖定後白噪音可能停、通知只有加入主畫面才有）。
4. 重複資料稽核只剩「ingest 文字檔改名會變成另一份題組」：設計取捨，沒有改。
5. JAVA 第 2～7 章教材在 `C:\Users\Administrator\OneDrive\桌面\JAVA_PPT\`，使用者可能要全部出題（流程 `docs/ingest-lecture.md`；整頁掃描圖，要看 `<檔名>-images/` 的圖）。現在也可以讓使用者在匯入頁自己按「AI 出題」。
6. 准考證照片的辨識實測 → 需要使用者提供照片。

## 開發環境與注意事項

- 開發：`npm run dev`（http://localhost:5173，後端 8000）。正式／手機：`npm run serve` 或雙擊 `start-server.cmd`（127.0.0.1:8765，用真正的資料，啟動時自動套用 migration）。兩者可同時開。
- **`vite build` 會更新 `frontend/dist`，也就是 8765 正式伺服器在用的檔案**；驗證時盡量用 dev 伺服器，真的 build 了要確定程式是完成的版本。
- Tailscale：`tailscale serve --bg 8765` 已設定（網址 `https://desktop-v3393bq.taila1733a.ts.net`，只有自己的 tailnet 連得到）。電腦重開機後先確認 `tailscale serve status`。使用者**不要**開機自動啟動 `start-server.cmd`（2026-10-08 決定）。
- 測試：`npm test`（後端 213、前端 19）；改 API 後 `npm run gen:api`；改 models 後 migration（autogenerate 要對**資料庫副本**跑：`LS_DATA_DIR=<副本>`）。
- 截圖／測試要造資料：複製 `data/` 到 scratchpad、`LS_DATA_DIR` 指向副本，**不要碰真正的資料庫**；另開測試伺服器用 8010（後端）／5180（`LS_API_PORT=8010 LS_WEB_PORT=5180 npx vite`），不要關掉使用者的 8000／5173／8765。截圖腳本寫成 `frontend/scripts/_verify.mjs`（才找得到 @playwright/test），用完刪掉。
- 「先讀、檢查、再寫」的服務函式開頭呼叫 `begin_write(db)`；並行測試寫法見 `tests/test_exam.py::test_same_answer_sent_twice_at_once_is_recorded_once`。
- 根字級是 15px：Tailwind 的 rem 單位比預期小，`--spacing-11` 已固定成 44px；要精確像素用 `[44px]`。小按鈕的觸控範圍用 `.hit`。單選群組的方向鍵用 `lib/roving.ts`。
- 無障礙掃描：Playwright 開頁面後注入 `https://cdn.jsdelivr.net/npm/axe-core@4.10.3/axe.min.js` 跑 `axe.run`；有動畫的頁面用 `reducedMotion: 'reduce'`，不然會誤報對比。
- 呼叫真的 AI 會花使用者額度；測試一律 `FakeProvider`。
- Windows 細節：Git Bash 的 heredoc 有時會解析失敗或吃掉跳脫，長的修改腳本用 Write 寫到 scratchpad 再 `python` 執行；curl 送中文表單欄位會亂碼，改用 `uv run --with httpx python`；Write 會把 `\u200b` 這類跳脫轉成真的字元；`.cmd` 必須 CRLF；uvicorn 要連子程序一起關（`taskkill //PID <pid> //T //F`）。
- 已安裝的技能：`web-design-guidelines`、`accessibility`（在 `~/.claude/skills/`）。

## 使用者偏好（摘要）

- 一律繁體中文；不需要使用者介入的步驟直接做，進度與下一步寫在同一則訊息；缺資料、破壞性操作、改專案以外的系統設定或需要意見（規格、設計取捨）時才停下來問。
- 推送到 GitHub 前先問（使用者會說「推送上去」）；commit 可以直接做。
- 會花用量的 AI 功能一律「按按鈕才用」並先顯示預估用量、可中斷。
- 新功能要顧到手機版（使用者 10/12 特別提醒）；每個頁面實際截圖自檢（桌機／手機 × 日／夜）。
- 視覺：作答頁「螢光筆＋原子筆」，其他頁面方向 A「白紙」＋原子筆動效。
- subagent 的回報要先自己驗證證據才採信。
