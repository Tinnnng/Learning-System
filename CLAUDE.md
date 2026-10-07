# Learning-System 專案指示

個人用的考試學習系統：匯入高普考／期中考題目與解答 PDF、出題作答、錯題複習、英文單字間隔複習。

## 已確定的決策（不要自行更改，要改先問使用者）

| 項目 | 決定 |
|---|---|
| 使用情境 | 單一使用者、本機執行，**不做登入/帳號系統** |
| AI 串接 | PDF 轉檔：Claude Code 離線轉成 JSON 再匯入。**系統內 AI（AI 助教、拍照辨識行事曆）**：2026-10-06 使用者決定改為在本機呼叫已登入的 Claude Code CLI（`claude -p`），消耗使用者自己的 Claude 訂閱用量，模型 **Claude Haiku 4.5**；不使用 API 金鑰。只限使用者本機自用 |
| AI 省 token | 呼叫時一律用精簡參數：自訂 `--system-prompt`、`--tools ""`、`--strict-mcp-config`、`--setting-sources ""`、`--no-session-persistence`、`--effort low`（一次約 400 token，不加會變 2.6 萬）。AI 詳解存資料庫重複使用；每月用量上限可設定 |
| 行事曆 | 手動輸入＋拍照由 AI 辨識（使用者確認後才加入）＋首頁考試倒數＋匯出 .ics |
| 題型範圍 | 選擇題（單選、複選/多答案給分）＋**申論題**（2026-10-07 使用者決定加入）。申論題：出題時由使用者選擇要不要包含（預設不含）；**參考答案與得分要點由 Claude Code 匯入時離線撰寫**；系統內打字作答，對照參考答案勾選得分要點自評，可按按鈕請 AI 建議（使用者確認才算分） |
| 錯題掌握 | 同一題**連續答對 5 次**才移出錯題本（中間答錯一次就歸零重算）。申論題：得分低於配分 60% 進錯題本，**連續 2 次 80% 以上**才移出。次數與比例放在設定檔，不寫死 |
| 期中考題目來源 | ① 上課教材（PPT／PDF／DOCX）→ Claude Code 離線**分析教材並出題**；② 現成題目文字檔 → 直接匯入 |
| 前端 | React + TypeScript + Vite + Tailwind CSS |
| 後端 | Python + FastAPI + SQLAlchemy + SQLite（單一 `.db` 檔） |
| PDF 處理 | PyMuPDF（裁切圖片、產生頁面截圖） |
| 視覺方向 | **B 螢光筆與原子筆**（2026-10-07 使用者改選，原本的 A 答案卡已停用）：白紙＋藍色原子筆＋黃色螢光筆；選取＝螢光筆從左刷到右，答對綠色、答錯粉紅；標題與批註用霞鶩文楷（`font-hand`），題目內文用 Noto Sans TC；品牌名「劃重點」；錯題掌握進度仍用「正」字筆畫。提案頁：https://claude.ai/artifact/Svn3CjyBqNR9zpoaNdPLBG |
| Git | 獨立存放庫 https://github.com/Tinnnng/Learning-System （private），不要和其他專案混在一起 |

## 工作流程規則

- **`CHECKLIST.md` 是唯一的進度來源。** 完成一項就把 `[ ]` 改成 `[x]`；過程中發現新工作，立刻加到對應階段（標註 `（新增）`），不要只記在對話裡。
- 開始新工作前先讀 `CHECKLIST.md`，照階段順序進行，除非使用者另有指示。
- 前後端分離：前端只透過 REST API（`/api/...`）跟後端溝通。

## 模組化原則（最重要，目標是「加功能＝加一個資料夾」）

- 每個功能是一個獨立模組，自帶 router / service / models / schemas / tests。
- **後端模組註冊**：`app/modules/registry.py` 列出啟用的模組；`main.py` 依清單自動掛載 router，不手動逐一 import。新增功能只要建資料夾並在清單加一行。
- **前端功能註冊**：每個 `features/<name>/` 匯出自己的路由與導覽項目，`app/registry.ts` 統一收集。新增頁面不需要改動其他功能的程式碼。
- 模組之間只透過對方 `service.py` 公開的函式互相呼叫，**不可直接查詢其他模組的資料表**，也不可互相 import 內部檔案。
- 共用的東西（資料庫連線、設定、工具函式）放 `core/`，`core/` 不可以 import 任何模組。
- **題目來源用轉接器（adapter）設計**：`ingest/adapters/` 下每種匯入檔格式一個轉接器，全部輸出同一種 `ImportBundle`。之後要支援新格式，只要加一個轉接器並登記到 `ADAPTERS`。
- 可調參數（錯題掌握次數、每日單字數等）集中在設定，不寫死在程式中。

## 架構

```
backend/
  app/
    main.py            FastAPI 進入點，依 registry 自動掛載各模組 router
    core/              設定、資料庫連線、共用工具
    modules/
      registry.py      啟用的模組清單
      ingest/          匯入、驗證、轉檔 CLI（cli.py）
        adapters/      匯入檔轉接器（json_bundle / text_file）
        gaopu/         高普考 PDF：檔名、答案表、表頭、草稿產生、build
        lecture.py     教材（PPTX/DOCX/PDF）文字抽取
      bank/            題庫、分類（考試類型/年度/類科/科目）、搜尋
      exam/            出題、題目與選項打亂、計時、交卷評分
      review/          錯題本、作答總覽與統計
      srs/             間隔複習排程（錯題與單字共用，FSRS）
      vocab/           單字匯入、每日測驗
      ai/              系統內 AI：呼叫本機 Claude Code CLI（providers/）、用量紀錄、每月上限
      tutor/           AI 助教：依官方答案解釋題目、追問、詳解快取
      calendar/        行事曆：考試日期、倒數、拍照辨識、匯出 .ics
      notes/           題目收藏與個人筆記
      backup/          備份與還原（zip 快照存 data/backups/，啟動時自動備份）
      topics/          知識點：AI 依科目標記、弱點分析
    每個模組內：router.py / service.py / models.py / schemas.py
  tests/
frontend/
  src/
    app/registry.ts    收集各 feature 的路由與導覽項目
    features/          與後端模組一一對應，各自匯出路由
    components/        共用 UI 元件（OptionBubble 螢光筆選項、AnswerGrid 題號導覽、ZhengTally 正字進度、RichText 題目顯示…）
    lib/               API client、自動產生的型別、格式化、主題
    styles/            design tokens（tokens.css）與全域樣式
data/
  inbox/               原始檔：gaopu/（高普考題目與答案 PDF）、lecture/（教材）、text/（題目文字檔）
  drafts/              轉檔中間產物：題目草稿、教材抽出的文字（不能直接匯入）
  converted/           解析完成、可以匯入的檔案（匯入頁只看這裡）
  assets/              題目圖片、頁面截圖
  backups/             備份快照 zip（learning.db＋assets＋manifest）
  learning.db
docs/                  轉檔流程說明（給 Claude Code 照著做）
```

## 題目資料格式

- 分類欄位彼此獨立、可為空：`exam_type`（高考/普考/期中考/自訂）、`year`、`category`（類科，期中考可空）、`subject`。
- 選項存成**陣列**，不把 A/B/C/D 寫死在文字中，才能打亂選項順序。
- 答案存成**陣列**（`["B","C"]`），以支援「答 B 或 C 均給分」的更正答案。
- 題幹與選項用 Markdown + LaTeX；表格轉 Markdown 表格；圖片裁成 PNG 放 `data/assets/`，以相對路徑參照。
- 每題保留原始頁面截圖，作為解析不準時的備援顯示。
- 題組（閱讀測驗、克漏字）的共用文章放 `passage`，同組每題各存一份；空格寫 `{{blank}}` 或 `{{blank:題號}}`。
- 正式 schema：`bank/schemas.py`（PaperIn、QuestionIn）與 `ingest/schemas.py`（ImportBundle、草稿格式）。

## 匯入題目（使用者丟新檔案時照著做）

| 來源 | 流程文件 |
|---|---|
| 高普考題目＋答案 PDF | `docs/ingest-gaopu.md`（scan → draft → 對照 PDF 校對 → build → import） |
| 期中考教材 PPTX／DOCX／PDF | `docs/ingest-lecture.md`（extract → 出題寫成 JSON → check → import） |
| 題目文字檔 | `docs/text-question-format.md`（放進 data/converted/ → check → import） |

- 平行派 agent 處理多份檔案時，要求每個 agent 的暫存檔用專屬檔名前綴，避免互相覆蓋。
- 本機沒有 poppler，Read 工具無法直接看 PDF，用 PyMuPDF 轉成 PNG 再看。

## 高普考 PDF 已知特性（轉檔程式已處理，改程式時注意）

- 檔名格式：`{年度3碼}{考試代碼3碼}_{科目代碼}_{科目名}.pdf`，例如 `115080_0114_...`。
  前綴 `ANS` = 標準答案，`MOD` = 更正答案（**MOD 優先於 ANS**）。
- 選項標號 (A)~(D) 是私有區字元 U+E18C~U+E18F（多數試卷）或約 22x11pt 的小圖片（例如 115 高考法學知識），草稿產生器兩種都當選項分隔。
- 填空底線、上下標在文字層會消失或黏在一起，必須對照原圖校對。
- 解答表格抽出的文字順序是亂的，需依「第N題」對應，不可依出現順序對應。
- 答案標 `#` 代表有更正，內容在備註（例如「第19題答Ｂ或Ｃ者均給分」）。
- 同一份試題可能出現在多個類科資料夾（例如國文、法學知識與英文），以「年度＋考試代碼＋科目代碼」（source_key `gaopu-115080-0114`）去重，一題只存一次，再與多個類科建立關聯。不同資料夾的同名答案檔內容可能不同（一份已含更正），scan 會提出警告。
- 申論題（如資料結構、資料庫應用）沒有 ANS 檔，照 `docs/ingest-gaopu.md` 的「申論題」一節：Claude Code 寫參考答案與得分要點，程式碼轉成 Markdown 程式碼區塊。

## 期中考題目來源

- **教材出題**（PPT／PDF／DOCX）：Claude Code 讀教材後出選擇題，每題必須附上正確答案、詳解，以及**出處**（第幾張投影片或第幾頁），讓使用者可以回頭查證。題目標記 `origin: "generated"`，與官方考古題（`origin: "official"`）區分。
- **題目文字檔**：格式見 `docs/text-question-format.md`，符合格式的系統直接解析匯入，不需要 AI；格式不符的交給 Claude Code 轉成 JSON。題目文字檔匯入為 `origin: "manual"`。
- 原始檔、草稿、解析完成的檔案**分三個資料夾放，不要混在一起**：`inbox/` → `drafts/` → `converted/`。

## 前端設計標準

品質目標：**Awwwards / Webby Awards / FWA 獲獎網站等級**，不是一般後台模板。

- 螢光筆效果統一用 `.marker` class（`--marker-color`、`--marker-scale` 控制顏色與長度），螢光色只當底色，文字一律用 `--ink`。
- 先在 `frontend/src/styles/` 定義 design tokens（色彩、字級比例、間距、圓角、陰影、動效時間與曲線），所有元件只用 token，不寫死數值。
- 日間／夜間模式：兩套都要獨立調色，夜間不是單純反轉顏色；預設跟隨系統，可手動切換並記住。
- 動效要有意義（引導注意力、回饋操作結果），並遵守 `prefers-reduced-motion`。
- 每完成一個頁面，依下列八個面向自我檢查，把發現的問題寫進 `CHECKLIST.md` 再修正，重複到沒有明顯可提升之處：
  1. **排版**：網格一致、對齊精準、閱讀長度適中（中文每行約 25–40 字）
  2. **留白**：間距節奏一致（使用 token），區塊有呼吸感、不擁擠
  3. **視覺層級**：一眼看出主要操作與資訊重點，字級／字重／顏色對比有明確層次
  4. **色彩**：日夜兩種模式都達 WCAG AA 對比，強調色克制使用，對錯回饋色清楚但不刺眼
  5. **動效**：轉場流暢（60fps）、時間與曲線統一、不拖慢操作
  6. **微互動**：hover/focus/active/disabled 狀態完整，作答、答對答錯、切換主題都有細緻回饋
  7. **響應式**：手機、平板、桌機都可用，觸控目標至少 44px，沒有水平捲動
  8. **原創性**：有自己的視覺語言與記憶點，避免看起來像現成模板
- 檢查時要實際在瀏覽器截圖確認（桌機與手機寬度、日夜兩種模式），不能只看程式碼判斷。

## 開發指令

在專案根目錄執行（需要 Python 3.13、uv、Node 22）：

| 指令 | 用途 |
|---|---|
| `npm run setup` | 第一次安裝：後端套件、建立資料庫、前端套件 |
| `npm run dev` | 同時啟動後端（:8000）與前端（:5173），開 http://localhost:5173 |
| `npm test` | 執行後端 pytest 與前端 Vitest（含模組邊界檢查） |
| `npm run migrate` | 套用資料庫 migration |
| `cd backend && uv run alembic revision --autogenerate -m "說明"` | 改了 models 後產生 migration |
| `cd frontend && npm run build` / `npm run lint` | 型別檢查＋建置 / oxlint |
| `npm run gen:api` | 後端 API 改了之後，重新產生前端型別 `frontend/src/lib/api-types.ts`（不要手改） |
| `cd frontend && MSYS_NO_PATHCONV=1 node scripts/screenshots.mjs <輸出資料夾> / /bank ...` | 設計自檢截圖（桌機／手機 × 日／夜），需先 npm run dev |

- 後端 API 文件：http://127.0.0.1:8000/docs
- 前端一律用 `@/lib/api` 以 `/api/...` 相對路徑呼叫後端，開發時由 Vite proxy 轉送。
- AI 相關設定（`LS_AI_PROVIDER`、`LS_AI_MODEL`、`LS_AI_MONTHLY_BUDGET_USD`、`LS_CLAUDE_CLI`）也在 config.py；測試一律用 `ai.service.set_provider(FakeProvider())`，**不要在測試中呼叫真的模型**。
- 可調參數在 `backend/app/core/config.py`，可用 `backend/.env` 覆寫（`LS_` 前綴，例如 `LS_MASTERY_STREAK=5`）。
- `alembic.ini` 必須維持純 ASCII（Windows cp950 讀到中文會失敗）。
- SQLite migration 用 batch 模式：新增的 ForeignKey／UniqueConstraint **一定要給 name**，否則升級失敗，而且 SQLite DDL 不在交易內，失敗前建好的資料表會殘留。
- 截圖或測試要造假資料時，複製 `data/` 到暫存區並用 `LS_DATA_DIR` 指向副本，**不要寫進使用者真正的資料庫**。
- uvicorn `--reload` 在 Windows 會留下 multiprocessing 子程序，關伺服器時要連子程序一起關，否則 8000 埠會被舊版程式佔住。
- Write 工具會把原始碼裡的 Unicode 跳脫序列（反斜線 u 加 4 碼）轉成實際字元；私有區字元（選項標記）要用 Python 腳本寫成跳脫序列。

### 新增一個功能模組

1. 後端：建立 `backend/app/modules/<名稱>/`（`__init__.py` 匯出 `router`，需要在伺服器啟動時做事可再匯出無參數的 `startup()`，加上 `service.py`、`schemas.py`，需要資料表再加 `models.py`），把名稱加到 `modules/registry.py` 的 `ENABLED_MODULES`。API 會自動掛在 `/api/<名稱>`。
2. 有新資料表時產生並套用 migration。
3. 前端：建立 `frontend/src/features/<名稱>/index.tsx` 匯出 `feature: FeatureDefinition`，會被自動收集，不用改其他檔案。
4. `npm test` 會檢查有沒有違反模組邊界。
