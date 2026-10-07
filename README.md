# 劃重點 Learning-System

個人用的考試學習系統：把高普考／期中考題目匯入題庫，出題作答、錯題複習、英文單字間隔複習，需要時再請 AI 助教解題。

- 單一使用者、在自己電腦上執行，**沒有登入／帳號系統**。
- 題目 PDF 由 Claude Code 離線轉成 JSON 後匯入；系統內的 AI 功能呼叫本機已登入的 Claude Code CLI（Claude Haiku 4.5），使用你自己的 Claude 訂閱額度，**不需要 API 金鑰**，而且一律「按按鈕才用」。

## 功能一覽

| 頁面 | 能做什麼 |
|---|---|
| 今日 | 今天該複習的錯題與單字、考試倒數 |
| 題庫 | 依考試類型與年度篩選，同年度＋考試＋類科合成一組（例如「115普考－一般行政」），可整組出題或挑一科寫；全文搜尋題幹、選項、文章與詳解；手動新增或修改題目 |
| 作答 | 練習模式（每題立即對答案）或模擬考（計時、交卷才評分）；可打亂題目與選項；申論題打字作答後對照參考答案勾得分要點自評，也可請 AI 評分 |
| 錯題本 | 選擇題連續答對 5 次才移出（用「正」字記進度）；申論題低於 60% 進錯題本、連續 2 次 80% 以上移出；以 FSRS 排複習日；可匯出 PDF |
| 單字 | 每日 5 個單字測驗與間隔複習，寫完可以「再測一組」新的字；重複匯入的字會合併中文意思、保留進度；內建多益核心 468 字、可匯入 CSV／Excel、可請 AI 從考古題英文題抽生字 |
| 行事曆 | 手動輸入考試日期、拍照或 PDF 由 AI 辨識後依高考／普考／地方特考等分類勾選要加入的考試、訂閱 iCal 考試行事曆、匯出 .ics |
| 總覽／弱點 | 作答統計；AI 依科目整理知識點，作答 3 次以上且正確率低於 60% 列為弱點，可直接練 |
| 收藏 | 收藏題目，每題底下有自動儲存的筆記區 |
| 匯入 | 預覽匯入檔（解析結果與原始試卷頁面並排）、修改後再匯入 |
| 備份 | 每天第一次啟動自動備份，也可手動備份、下載、還原 |

## 快速開始

### 1. 需要先安裝

| 工具 | 版本 | 用途 |
|---|---|---|
| [Python](https://www.python.org/) | 3.13 | 後端 |
| [uv](https://docs.astral.sh/uv/) | 最新版 | 安裝後端套件 |
| [Node.js](https://nodejs.org/) | 22 | 前端 |
| [Claude Code](https://claude.com/claude-code) | 已登入 | 系統內 AI 功能與題目轉檔（不用 AI 也能使用其餘功能） |

### 2. 安裝與啟動

在專案根目錄執行：

```bash
npm install        # 安裝根目錄的啟動工具
npm run setup      # 安裝後端套件、建立資料庫、安裝前端套件
npm run dev        # 同時啟動後端（:8000）與前端（:5173）
```

打開 http://localhost:5173 就可以使用。關閉時在終端機按 `Ctrl+C`。

> Windows 注意：後端開發伺服器偶爾會留下子程序佔住 8000 埠，若重開時顯示埠被占用，請在工作管理員結束殘留的 `python` 程序。

### 3. 第一次使用

剛裝好的資料庫是**空的**（`data/` 是個人資料，不進版本控制）。建議依序：

1. **加入單字**：到「單字」→「單字庫」匯入內建的多益核心單字。
2. **匯入題目**：把題目檔放進對應資料夾，請 Claude Code 照流程文件轉檔後匯入（見下一節）；或在「題庫」手動新增題目。
3. **開始作答**：在「題庫」選試卷或條件出題，答錯的題目會自動進錯題本。
4. **設定考試日期**：在「行事曆」新增考試或訂閱考試行事曆，首頁會顯示倒數。

## 匯入題目

資料夾分工：原始檔放 `data/inbox/`，轉檔中間產物在 `data/drafts/`，可以匯入的檔案在 `data/converted/`（匯入頁只看這裡），三者不要混放。

| 來源 | 放在哪裡 | 怎麼轉 |
|---|---|---|
| 高普考題目＋答案 PDF | `data/inbox/gaopu/<例如 115普考QA-一般行政>/` | 請 Claude Code 照 [`docs/ingest-gaopu.md`](docs/ingest-gaopu.md) 轉檔 |
| 期中考教材（PPTX／DOCX／PDF，舊版 PPT／DOC 會自動用 Office 轉檔） | `data/inbox/lecture/` | 請 Claude Code 照 [`docs/ingest-lecture.md`](docs/ingest-lecture.md) 讀教材出題（每題附答案、詳解、出處頁碼） |
| 自己整理的題目文字檔 | `data/inbox/text/` | 照 [`docs/text-question-format.md`](docs/text-question-format.md) 的格式寫，系統直接解析，不需要 AI（範例：[`docs/examples/sample-questions.txt`](docs/examples/sample-questions.txt)） |

轉好的檔案可以在「匯入」頁預覽、修改後匯入，也可以用指令（在 `backend/` 執行）：

```bash
uv run python -m app.modules.ingest.cli check  ../data/converted/<檔名>   # 檢查
uv run python -m app.modules.ingest.cli import ../data/converted/<檔名>   # 匯入
```

最簡單的做法：把檔案放好後，直接跟 Claude Code 說「幫我把 data/inbox 裡的新檔案轉檔匯入」。

## AI 功能與用量

- 會用到 AI 的地方：AI 助教詳解與追問、申論題 AI 評分、行事曆照片辨識、知識點標記、從考古題抽生字。全部都要按按鈕才會呼叫。
- AI 助教送出後可以按「中斷」立刻停止（不再花用量）；面板會顯示這題與本月已用的額度。
- 參考花費（以 API 等值計算）：AI 評分一題約 0.004 美元、助教詳解一題約 0.003 美元、標記一科知識點約 0.01～0.03 美元、辨識一份考選部考試計畫表約 0.03 美元。
- 每月用量上限預設 3 美元，可在 `backend/.env` 用 `LS_AI_MONTHLY_BUDGET_USD` 調整。
- 沒裝或沒登入 Claude Code 時，AI 按鈕會顯示錯誤，其他功能照常使用。

## 用手機作答

手機和電腦連同一個家用 Wi-Fi 時：

```bash
npm run dev:lan
```

終端機會顯示手機要開的網址。前端只綁定 Wi-Fi 的 IP（不開放給 VPN 上的人），但系統沒有登入，**只在信任的網路使用**。IP 判斷錯誤時，用環境變數 `LS_LAN_HOST` 指定。

## 調整設定

可調參數集中在 `backend/app/core/config.py`，用 `backend/.env` 覆寫（變數名稱加 `LS_` 前綴）：

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

- 所有個人資料都在 `data/`：資料庫 `learning.db`、題目圖片 `assets/`、備份 `backups/`。
- 每天第一次啟動會自動備份到 `data/backups/`（保留最近 10 份）；換電腦時從「備份」頁下載 zip，在新電腦還原即可。

## 開發

| 指令 | 用途 |
|---|---|
| `npm test` | 後端 pytest 與前端 Vitest（含模組邊界檢查） |
| `npm run migrate` | 套用資料庫 migration |
| `cd backend && uv run alembic revision --autogenerate -m "說明"` | 改了 models 後產生 migration |
| `npm run gen:api` | 後端 API 改了之後重新產生前端型別 |
| `cd frontend && npm run build` / `npm run lint` | 型別檢查＋建置 / oxlint |

- 技術：前端 React + TypeScript + Vite + Tailwind CSS；後端 Python + FastAPI + SQLAlchemy + SQLite；PDF 處理用 PyMuPDF。
- 後端 API 文件：http://127.0.0.1:8000/docs
- 架構採模組化：後端每個功能是 `backend/app/modules/<名稱>/`，前端對應 `frontend/src/features/<名稱>/`，新增功能只要加一個資料夾並登記。完整規則、架構與決策見 [`CLAUDE.md`](CLAUDE.md)；目前進度見 [`docs/STATUS.md`](docs/STATUS.md) 與 [`CHECKLIST.md`](CHECKLIST.md)。
