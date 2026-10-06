# 題目文字檔格式

照這個格式寫的 `.txt` 或 `.md` 檔，放進 `data/converted/` 後可以直接匯入，不需要 AI。範例：[`examples/sample-questions.txt`](examples/sample-questions.txt)。

```bash
cd backend
uv run python -m app.modules.ingest.cli check ../data/converted/我的題目.txt    # 先檢查
uv run python -m app.modules.ingest.cli import ../data/converted/我的題目.txt   # 匯入
```

## 開頭設定（放在第一題之前，每行一個）

| 設定 | 必填 | 說明 |
|---|---|---|
| `# 科目：程式設計` | ✔ | |
| `# 考試類型：期中考` | | 預設「期中考」，也可以寫期末考、小考… |
| `# 年度：115` | | 數字 |
| `# 類科：資訊處理` | | 多個用頓號分隔 |
| `# 標題：…` | | 顯示在題庫列表 |
| `# 考試時間：60` | | 分鐘，模擬考倒數用 |
| `# 代碼：prog-midterm-115` | | 英文小寫、數字、連字號。用來辨識同一份題目，**重新匯入時會更新而不是新增**。不填就用檔名產生 |

## 題目

```
1. 題幹（可以多行，支援 Markdown、程式碼區塊、LaTeX 公式 $x^2$）
(A) 選項一
(B) 選項二
(C) 選項三
(D) 選項四
答案：B
詳解：可以多行，選填
```

- 題號寫成 `1.`、`1、` 或 `1．` 都可以。
- 選項寫成 `(A)`、`A.`、`A)`、`（A）` 都可以，必須依序從 A 開始；選項數量不限（2 個以上）。
- `答案：` 寫一個字母是單選；寫多個（`A、B、D` 或 `ABD`）是複選，要全部選對才算對。
- 填空的地方寫 `{{blank}}`。
- 空行會被忽略。
