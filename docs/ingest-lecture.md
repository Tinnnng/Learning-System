# 由上課教材出題（給 Claude Code 照著做）

使用者把教材（PPTX／DOCX／PDF）放進 `data/inbox/lecture/`，請 Claude Code 出題。抽出的文字放 `data/drafts/lecture/`，出好的題目放 `data/converted/`。所有指令在 `backend/` 執行。

## 步驟

1. **抽出教材文字**（標示投影片編號或頁碼）：
   ```bash
   uv run python -m app.modules.ingest.cli extract ../data/inbox/lecture/第3章.pptx --out ../data/drafts/lecture/第3章.md
   ```
   有 `[圖片]` 標記的投影片，若圖片內容重要，用 PyMuPDF 或請使用者提供截圖確認。舊版 `.ppt`／`.doc` 請使用者先另存成新格式。
2. **詢問使用者**（沒說的話）：出幾題、難度、要涵蓋哪些章節。預設每份教材 10–20 題，均勻涵蓋各主題。
3. **出題**，寫成匯入檔 `data/converted/lecture-<英文代碼>.json`（格式即 `ImportBundle`，見下方範例）。
4. **檢查並匯入**：
   ```bash
   uv run python -m app.modules.ingest.cli check  ../data/converted/lecture-<代碼>.json
   uv run python -m app.modules.ingest.cli import ../data/converted/lecture-<代碼>.json
   ```

## 出題規則

- **只根據教材內容出題**，不加入教材沒教的知識；每題都要能在教材中找到依據。
- 每題必填：`explanation`（為什麼正確選項對、其他選項錯在哪）、`source_ref`（`file` 檔名＋`slide` 或 `page`；Word 檔用 `note` 寫章節標題）。檢查會擋下缺少這兩項的題目。
- `origin` 填 `generated`、`answer_source` 填 `generated`。
- 單選題 4 個選項，只有一個正確答案；誘答選項要合理（常見誤解），避免「以上皆是／皆非」。
- 正確答案的位置要平均分散在 A–D。
- 題幹清楚、不出現否定句陷阱以外的語意歧義；需要否定時用「何者**錯誤**」並加粗。
- 程式碼用 fenced code block，公式用 LaTeX `$...$`，填空用 `{{blank}}`。
- `tags` 填章節或主題名稱（例如 `指標`、`遞迴`），之後做弱點分析用。

## 匯入檔範例

```json
{
  "schema_version": 1,
  "paper": {
    "source_key": "lecture-prog-ch3",
    "origin": "generated",
    "exam_type": "期中考",
    "year": 115,
    "subject": "程式設計",
    "title": "第 3 章 指標（教材出題）",
    "categories": [],
    "source_files": ["第3章.pptx"]
  },
  "questions": [
    {
      "number": 1,
      "type": "single_choice",
      "stem": "宣告 `int *p = &x;` 之後，`*p` 代表什麼？",
      "options": ["x 的位址", "x 的值", "p 的位址", "p 所占的位元組數"],
      "answer": ["B"],
      "answer_source": "generated",
      "explanation": "`*p` 是解參考，取得 p 指向位置（也就是 x）的值。(A) 是 `p` 或 `&x`；(C) 是 `&p`；(D) 是 `sizeof(p)`。",
      "source_ref": { "file": "第3章.pptx", "slide": 7 },
      "tags": ["指標"]
    }
  ]
}
```
