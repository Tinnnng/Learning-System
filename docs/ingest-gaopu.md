# 高普考題目轉檔流程（給 Claude Code 照著做）

所有指令都在 `backend/` 執行，`<資料夾>` 是放高普考 PDF 的資料夾，預設放在 `data/inbox/gaopu/`（子資料夾命名為 `115普考QA-一般行政` 這種格式；考試支援高考、普考、地方特考，地方特考把等別寫進類科，例如 `114地方特考QA-四等一般行政`。考選部下載的資料夾若叫「特種考試」，複製進來時改名）。

**使用者在匯入頁上傳的試卷**放在 `data/inbox/gaopu/uploads/`（底下一樣是 `115普考QA-類科` 子資料夾），`<資料夾>` 用它就好。
使用者可能已經在網頁上按過「自動轉檔」或「AI 校對後轉檔」，`data/converted/<source_key>.json` 會有 `review_notes`（要確認的地方）；
使用者請你轉時，照下面流程重新產生草稿、逐題校對後 build，覆蓋掉系統轉的檔案（build 出來的檔案不會有 `review_notes`）。

資料夾分工：原始 PDF 放 `data/inbox/`，草稿在 `data/drafts/`，解析完成的匯入檔在 `data/converted/`，三者不要混放。

```bash
uv run python -m app.modules.ingest.cli scan  <資料夾>                 # 1. 看有哪些試卷、哪些是選擇題
uv run python -m app.modules.ingest.cli draft <資料夾> <source_key>    # 2. 自動產生草稿
#                                                                        3. 對照 PDF 校對草稿（本文件重點）
uv run python -m app.modules.ingest.cli build <資料夾> <source_key>    # 4. 補上答案、截圖、圖片 → data/converted/<source_key>.json
uv run python -m app.modules.ingest.cli import ../data/converted/<source_key>.json   # 5. 匯入題庫
```

- 答案、配分、考試時間、試題代號都由程式從 PDF 解析，**校對時不要動答案**。
- 申論題（scan 顯示 `[申論]`）沒有官方答案，不走 draft／build，照文末「申論題」一節手動寫成匯入檔。`[混合]` 的試卷選擇題部分照上面流程轉，申論題部分另外處理。
- 草稿位置：`data/drafts/<source_key>.draft.json`。已存在的草稿不會被 `draft` 覆蓋（除非加 `--force`），避免校對成果被蓋掉。

## 草稿格式

```json
{
  "source_key": "gaopu-115080-0114",
  "reviewed": false,
  "questions": [
    {
      "number": 1,
      "page": 1,
      "type": "single_choice",
      "passage": null,
      "stem": "題幹",
      "options": ["選項A", "選項B", "選項C", "選項D"],
      "figures": [{ "page": 2, "bbox": [195, 623, 425, 731], "kind": "image", "caption": null }],
      "tags": [],
      "review_notes": ["自動產生時標記的提醒"]
    }
  ],
  "answer_overrides": {}
}
```

## 校對規則

**每一題都要對照 PDF 原圖確認**（用 Read 工具讀 PDF 指定頁），不能只看草稿文字。只修正抽取錯誤，不改寫題目內容、不修正原題的用字。

1. **題幹 `stem`**：完整題目文字，不含題號。檢查換行接合是否正確：中文直接相連；英文單字之間要有一個空格，不能黏在一起或多出空格。英數字與中文之間的空格（例如「民國83 年」「AI 產出」）照 PDF 原樣保留，不增不減。
2. **選項 `options`**：順序與 PDF 的 (A)(B)(C)(D) 完全一致，不含標號。選項文字不可以混入下一題或題組文章。
3. **空格**：PDF 中的填空底線會在抽取時消失，一律補成 `{{blank}}`。克漏字的編號空格寫成 `{{blank:41}}`（41 是對應題號）。不要用底線 `___`（Markdown 會誤判成粗體）。
4. **題組（閱讀測驗、克漏字）**：共用的文章放進該題組**每一題**的 `passage`（內容完全相同，打亂出題時才能各自顯示），`stem` 只放該題的問題。
   - 文章前的說明（例如「請依下文回答第 46 題至第 50 題」）放在 `passage` 第一行。
   - 克漏字題目若 PDF 沒有題幹，`stem` 寫成：`選出最適合填入 {{blank:41}} 的答案`。
   - 段落之間用空行分隔。
5. **數學與符號**：上下標、公式用 LaTeX 行內語法 `$...$`，例如 `$(535)_8$`、`$2^{10}$`、`$X \oplus Y$`。一般文字中的金錢符號 `$` 要寫成 `\$`。
6. **程式碼**：行內用反引號；多行程式用 fenced code block（```c ... ```），保留縮排。
7. **表格**：轉成 Markdown 表格放在 `stem`（或 `passage`）。
8. **圖片**：`review_notes` 提到的內嵌圖片已自動加入 `figures`，確認 bbox 有完整框住圖（含圖說、不含其他題目文字）。向量圖形若是圖（電路圖、流程圖、樹）就加到 `figures`；若是表格就轉成 Markdown 表格。座標可用 `cli layout <pdf> --page N` 查。
9. **圈號**：①②③ 保留原樣。
10. **標籤 `tags`**：「法學知識與英文」每題標一個：`憲法`、`法學緒論` 或 `英文`。其他科目可留空。
11. 處理完一題的提醒就把該題 `review_notes` 清空；全部校對完把 `reviewed` 改成 `true`。build 會拒絕 `reviewed` 不是 true 或還有 `review_notes` 的草稿。
12. `answer_overrides` 只有在 build 回報「答案有更正但備註無法自動解析」時才填，例如 `{"19": ["B", "C"]}`。

## 檢查清單

- [ ] 題數與試卷宣告的一致（build 會檢查）
- [ ] 每題 4 個選項、沒有空白選項
- [ ] 英文題的空格都補上 `{{blank}}`
- [ ] 題組文章沒有黏在前一題的選項裡
- [ ] 上下標、公式改成 LaTeX
- [ ] 圖片範圍正確
- [ ] `review_notes` 全部清空、`reviewed: true`

## 申論題

官方不公布申論題答案，由 Claude Code 匯入時撰寫**參考答案與得分要點**，使用者作答後對照要點自評（也可以請系統內 AI 建議）。

1. 原始 PDF 複製到 `data/inbox/gaopu/<source_key>/`，頁面截圖用 `app.modules.ingest.pdf.render_page` 存成 `data/assets/<source_key>/page-N.png`，程式碼截圖、網頁畫面等圖片用 `crop_region` 裁成 `q00N-1.png`（座標用 `cli layout` 查）。
2. 直接寫匯入檔 `data/converted/<source_key>.json`（ImportBundle），每個**子題**一題：
   - `type: "essay"`、`answer_source: "reference"`、`options`／`answer` 留空。
   - `label`：顯示題號，例如 `一(一)`；沒有子題的大題寫 `三`。`number` 從 1 連號。
   - 大題的共同題幹（「某校計畫…請回答以下問題：」）放 `passage`，子題本身放 `stem`。
   - 試題裡的程式碼**轉成 Markdown 程式碼區塊**（標註語言），不要只放圖片；輸出畫面、網頁畫面這類非文字內容才放 `assets`。
   - `points`：子題配分。`explanation`：參考答案（Markdown，可用表格、程式碼）。
   - `rubric`：得分要點 `[{"text": "...", "points": 4}]`，**分數加總必須等於 points**（check 會擋）。要點寫成可以勾選判斷的具體內容（例如「教學實驗室：192.168.10.0/25」），不要寫「說明完整」這種模糊的。
3. 程式追蹤題的輸出一定要實際執行或逐行模擬驗證，不要只靠推理。
4. `cli check` → `cli import`，匯入前先用 `backup` 模組備份。
5. paper 的 `answer_note` 註明「申論題沒有官方答案；參考答案與得分要點由 Claude Code 匯入時撰寫，僅供參考。」
