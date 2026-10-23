# 劃重點 Learning-System

個人開發的全端學習系統：為了學習和複習大量考古題與教材而寫的工具，把 PDF 考古題與上課教材自動轉成結構化題庫，提供練習、模擬考、錯題複習、單字間隔複習，並整合本機 AI 助教。

![TypeScript](https://img.shields.io/badge/TypeScript-React%20%2B%20Vite-3178C6?logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python-FastAPI-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-SQLAlchemy%20%2B%20Alembic-003B57?logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest%20%2B%20Vitest-informational)

**43 次迭代、13 個後端模組、3 輪使用者回饋稽核、1 次 72 項缺陷的全模組健檢**——持續用「稽核 → 修復 → 補迴歸測試」的流程開發，細節見下方〈工程紀錄〉。

> 個人單機工具，沒有登入系統、不對外服務——這裡展示的是架構與工程取捨，不是一個「可直接部署給他人用」的產品。

<!-- 建議在此放 1–2 張畫面截圖或 demo GIF（例如「今日」首頁、作答畫面） -->

## 這個專案在解決什麼問題

準備考試時題目量很大、分散在不同年度與科目，手動整理耗時；市面上的練習平台多半不支援「申論題 AI 批改」與「個人化弱點分析」。這個系統是為了自己學習和複習題目而開發，把讀書流程（匯入題目 → 作答 → 錯題複習 → 弱點分析 → 單字間隔複習）系統化，並用 AI 處理最耗時的兩個步驟：試卷轉檔、申論題評分。

## 技術亮點

- **零 API 金鑰的 AI 整合**：AI 功能（助教詳解、申論題評分、知識點標記）透過呼叫本機已登入的 Claude Code CLI 執行，不需在專案內管理任何金鑰；另外實作了**每月用量預算上限**（可設定、超過自動擋下），避免個人工具失控燒錢。
- **間隔複習演算法**：單字複習採 FSRS（Free Spaced Repetition Scheduler）排程；錯題複習則依「選擇題連續答對 5 次」「申論題連續 2 次 80 分以上」等規則移出錯題本，規則與門檻都可透過環境變數調整。
- **考卷轉檔 pipeline**：PDF／PPTX／DOCX 教材與考古題，經 Claude Code 離線轉成結構化 JSON 後匯入，匯入前可在介面預覽「解析結果」與「原始試卷頁面」並排比對，確保轉檔品質。
- **模組化架構 + 邊界測試**：後端 `app/modules/<feature>/` 與前端 `src/features/<feature>/` 一一對應，新增功能只需新增一個資料夾並登記；CI 測試包含「模組邊界檢查」，避免模組間直接互相依賴。
- **本機優先、隱私優先**：所有個人資料留在本機 SQLite，不上雲端；手機存取透過 Tailscale 建立私有連線，而非公開 API。

## 工程紀錄：系統性稽核與決策

這個專案不是一次寫完就沒再碰，而是持續用「稽核 → 列清單 → 逐項修 → 補迴歸測試」的方式在跑，紀錄都留在 commit history：

- **無障礙稽核**：對照 WCAG 準則逐頁檢查，並用 axe-core 掃過 14+ 個頁面（含考試頁、桌機／手機、深／淺色模式），修到全數通過。
  > 情況說明：一開始只是手動點點看有沒有問題，後來發現看漏很多，才引入 axe-core 自動掃描當作把關工具。實際修的項目像是：選項和行事曆格子原本滑鼠點得到、鍵盤 Tab 不過去；手機上有些按鈕太小（改成固定 44px 熱區）；答對/答錯、倒數計時只靠顏色或畫面變化顯示，螢幕報讀器完全看不到，後來加上 ARIA live region 讓它用念的播報出來。
- **重複資料稽核**：系統性檢查 13 個後端模組的重複寫入問題，每個修復都先重跑驗證、確認問題重現後才採信修法。
  > 情況說明：起因是訂閱的考試行事曆有時候會把同一場考試加兩次進日曆。追下去發現是不同來源給的 iCal 事件 UID 格式不一致（同一場考試在不同行事曆服務裡 UID 長得不一樣），加上同步時用字串比對判斷「是不是舊事件」，字元全形半形不同就判斷成不同科目名稱、重複建立。後來統一寫了一個共用的正規化比對函式（`core/text.match_key`），所有模組的重複判斷都改用它，而不是每個模組各自土炮比對。
- **併發正確性**：發現同時作答/交卷會出現 read-check-write 競態後，統一改用 SQLite `BEGIN IMMEDIATE` 交易包住所有「先查再寫」的路徑。
  > 情況說明：自己用手機和電腦同時開同一場模擬考測試時，發現偶爾會重複交卷兩三次、或同一題被記錄成答了兩次。原因是「先查有沒有交過 → 沒有的話才寫入」這兩步中間沒有鎖住，兩個請求幾乎同時到就都通過了檢查。一開始想針對出問題的那個 API 加鎖修掉，後來想到前端開發和正式啟動是兩個不同的 process，一般的記憶體鎖沒用，才改成在資料庫層用 `BEGIN IMMEDIATE` 交易，讓所有「先查再寫」的路徑統一排隊處理，而不是哪裡壞了補哪裡。
- **一次性全面稽核**：針對 srs、ai、topics、review、activity、calendar、system、bank、backup、tutor、ingest、notes、vocab、exam 全部 13 個模組做逐一審查，抓出 72 個問題，每個都補上對應的後端/前端迴歸測試後才算修完。
  > 情況說明：功能做得差不多之後，擔心各模組之間互動會有沒想到的邊角案例（例如某個設定值被另一個模組用了不同的預設值），所以逐一把每個模組的程式碼和對應測試重新看一遍，記錄所有可疑行為再分批修。修完的例子包含：模擬考原本題目一倒數完就提醒，改成真的到時間才提醒；申論題沒作答的題目原本也會被判定「答錯」進錯題本，改成沒作答就不列入；番茄鐘中途跳過不該算進完成次數；單字每日複習原本是隨機挑，改成優先挑最久沒被複習到的。
- **視覺設計迭代**：UI 風格經過三次方向嘗試，每次都寫自我審查紀錄比較取捨，最後定案為目前「劃重點」風格與品牌。
  > 情況說明：第一版做的是「答案卷」風格（鉛筆塗答案卡的感覺），做完自己用了一陣子覺得太素、看久了沒有重點感。第二版改成「螢光筆＋原子筆手寫」風格，選項答對會有螢光筆掃過的動畫、字體換成手寫感的 LXGW WenKai，整體品牌也順勢改名叫「劃重點」。每次改版都寫了一份自我審查記錄（寫螢幕截圖、列出跟上一版比較後要保留/捨棄的元素），不是憑感覺換皮。
- **匯入管線的邊角案例**：PDF 要判斷「有文字層直接讀」還是「掃描圖要用高解析度重新渲染」；舊版 `.doc`/`.ppt` 要先用 Office 自動轉檔；同名不同副檔名的文字題目檔案不能互相覆蓋。
  > 情況說明：官方釋出的考古題 PDF 有些是可選取文字的原生 PDF，有些是掃描圖檔（選取不到文字），兩種要用完全不同的方式處理——前者直接抽文字,後者得把每一頁轉成高解析度圖片再讓 AI 讀圖。另外舊的上課教材常常是很早期的 `.ppt`／`.doc` 格式，Python 的函式庫讀不動，後來改成先呼叫本機 Office 把它們轉成新格式再處理。同名不同副檔名覆蓋的 bug，是自己匯入同一份題目的 txt 和手動修正版時，兩個檔案用同一個檔名存檔，後面匯入的直接把前面的蓋掉才發現的。

## 功能一覽

| 模組 | 說明 |
| --- | --- |
| 題庫與作答 | 練習模式即時對答案／模擬考計時交卷；選擇題與申論題皆支援，申論題可自評或請 AI 評分 |
| 錯題複習 | 依正確率與連續答對次數排程複習，支援匯出 PDF |
| 單字學習 | 每日新字 + FSRS 間隔複習，內建多益核心 468 字，可從考古題英文題自動抽生字 |
| 行事曆 | 手動輸入或拍照／PDF 由 AI 辨識考試日期，支援訂閱 iCal |
| 弱點分析 | AI 依科目整理知識點，標出正確率低於 60% 的弱項 |
| 匯入 | 支援考古題 PDF、上課教材、純文字題目三種來源，匯入前可預覽比對 |
| 備份 | 每日自動備份，可手動下載／還原 |

## 技術棧

- **前端**：React + TypeScript + Vite + Tailwind CSS
- **後端**：Python + FastAPI + SQLAlchemy + Alembic + SQLite
- **PDF 處理**：PyMuPDF
- **測試**：pytest（後端）、Vitest（前端），含模組邊界檢查
- **AI**：Claude Code CLI（本機呼叫，無需 API key）

完整架構規則與決策紀錄見 [`CLAUDE.md`](CLAUDE.md)；開發進度見 [`docs/STATUS.md`](docs/STATUS.md)。

---

## 快速開始

### 需要先安裝

| 工具 | 版本 | 用途 |
| --- | --- | --- |
| [Python](https://www.python.org/) | 3.13 | 後端 |
| [uv](https://docs.astral.sh/uv/) | 最新版 | 安裝後端套件 |
| [Node.js](https://nodejs.org/) | 22 | 前端 |
| [Claude Code](https://claude.com/claude-code) | 已登入 | 系統內 AI 功能與題目轉檔（不用 AI 也能使用其餘功能） |

### 安裝與啟動

```bash
npm install        # 安裝根目錄的啟動工具
npm run setup      # 安裝後端套件、建立資料庫、安裝前端套件
npm run dev        # 同時啟動後端（:8000）與前端（:5173）
```

打開 http://localhost:5173 即可使用，`Ctrl+C` 結束。

> Windows 注意：後端開發伺服器偶爾會留下子程序佔住 8000 埠，若重開時顯示埠被占用，請在工作管理員結束殘留的 `python` 程序。

### 第一次使用

資料庫預設是空的（`data/` 為個人資料，不進版本控制）：

1. **加入單字**：「單字」→「單字庫」匯入內建多益核心單字。
2. **匯入題目**：將檔案放入對應資料夾，請 Claude Code 依流程文件轉檔後匯入（見下節），或於「題庫」手動新增。
3. **開始作答**：於「題庫」選試卷或依條件出題，答錯題目自動進錯題本。
4. **設定考試日期**：於「行事曆」新增或訂閱考試行事曆，首頁顯示倒數。

## 匯入題目

資料夾分工：原始檔 `data/inbox/`、轉檔中間產物 `data/drafts/`、可匯入檔案 `data/converted/`（匯入頁只讀這裡）。

| 來源 | 放在哪裡 | 怎麼轉 |
| --- | --- | --- |
| 考古題目＋答案 PDF | `data/inbox/gaopu/<依考試與類科命名的資料夾>/` | 依 [`docs/ingest-gaopu.md`](docs/ingest-gaopu.md) 轉檔 |
| 期中考教材（PPTX／DOCX／PDF） | `data/inbox/lecture/` | 依 [`docs/ingest-lecture.md`](docs/ingest-lecture.md) 出題（附答案、詳解、出處頁碼） |
| 自己整理的題目文字檔 | `data/inbox/text/` | 依 [`docs/text-question-format.md`](docs/text-question-format.md) 格式，系統直接解析、不需 AI |

```bash
uv run python -m app.modules.ingest.cli check  ../data/converted/<檔名>   # 檢查
uv run python -m app.modules.ingest.cli import ../data/converted/<檔名>   # 匯入
```

最簡單的做法：檔案放好後，直接跟 Claude Code 說「幫我把 data/inbox 裡的新檔案轉檔匯入」。

## AI 功能與用量

- 會用到 AI 的地方：助教詳解與追問、申論題評分、行事曆照片辨識、知識點標記、從考古題抽生字——全部按按鈕才呼叫。
- 送出後可隨時「中斷」立即停止，不再計費；面板顯示本題與本月已用額度。
- 參考花費（API 等值）：AI 評分一題約 $0.004、助教詳解一題約 $0.003、標記一科知識點約 $0.01–0.03、辨識一份考試計畫表約 $0.03。
- 每月用量上限預設 $3，可在 `backend/.env` 以 `LS_AI_MONTHLY_BUDGET_USD` 調整。
- 未安裝或未登入 Claude Code 時，AI 按鈕顯示錯誤，其餘功能不受影響。

## 手機使用

建議：電腦執行 `npm run serve`（或雙擊 `start-server.cmd`），手機透過 Tailscale 以 HTTPS 連回電腦，再從 Safari「加入主畫面」。完整步驟見 [`docs/iphone.md`](docs/iphone.md)。

臨時在同一 Wi-Fi 使用：

```bash
npm run dev:lan
```

前端只綁定 Wi-Fi IP，系統無登入機制，**僅限信任網路使用**。

## 設定

可調參數集中在 `backend/app/core/config.py`，以 `backend/.env` 覆寫（變數名稱加 `LS_` 前綴）：

```ini
LS_MASTERY_STREAK=5            # 選擇題連續答對幾次移出錯題本
LS_DAILY_VOCAB_COUNT=5         # 每日新單字數
LS_ESSAY_WRONG_RATIO=0.6       # 申論題得分低於幾成進錯題本
LS_ESSAY_PASS_RATIO=0.8        # 申論題得分幾成以上算過關
LS_ESSAY_MASTERY_STREAK=2      # 申論題連續過關幾次移出
LS_AI_MONTHLY_BUDGET_USD=3.0   # AI 每月用量上限（美元）
LS_BACKUP_KEEP=10              # 保留幾份自動備份
```

## 資料與備份

- 個人資料集中於 `data/`：資料庫 `learning.db`、題目圖片 `assets/`、備份 `backups/`。
- 每日首次啟動自動備份（保留最近 10 份）；換電腦時於「備份」頁下載 zip，在新電腦還原。

## 開發

| 指令 | 用途 |
| --- | --- |
| `npm test` | 後端 pytest 與前端 Vitest（含模組邊界檢查） |
| `npm run migrate` | 套用資料庫 migration |
| `cd backend && uv run alembic revision --autogenerate -m "說明"` | 改了 models 後產生 migration |
| `npm run gen:api` | 後端 API 改了之後重新產生前端型別 |
| `cd frontend && npm run build` / `npm run lint` | 型別檢查＋建置 / oxlint |

後端 API 文件：http://127.0.0.1:8000/docs
