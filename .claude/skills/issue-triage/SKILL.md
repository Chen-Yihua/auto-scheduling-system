---
name: issue-triage
description: 整理所有開著的 GitHub Issues：分類、建議優先度、相依性與處理順序；開發者確認後才加 priority 標籤，不開始開發
disable-model-invocation: true
---

# Issue 整理

只整理、不開發：不開分支、不改程式、不執行 `/issue`。

## 1. 讀取

```bash
gh issue list --state open --limit 100 --json number,title,labels,createdAt
gh issue view <N> --json number,title,body,labels,comments,state
```

每個 issue 都要讀內容與留言，不能只看標題。`gh issue view` 一定要加 `--json`，原因見 CLAUDE.md「開發流程」。需要判斷影響範圍時，可以讀程式碼與 `docs/`。

## 2. 整理成表格給開發者

| issue | 類型 | 建議優先度 | 理由 | 相依 | 建議順序 |
|---|---|---|---|---|---|

- **類型**：沿用既有標籤 `bug` / `enhancement`；沒有標籤的，寫出建議的類型。
- **建議優先度**：`priority:high` / `priority:medium` / `priority:low`。理由要寫具體影響，例如「使用者看到錯誤的日期」「每次啟動都會失敗」，不要只寫「重要」。已有 `priority:*` 標籤的，寫出現有值，並說明是否建議調整。
- **相依**：哪個 issue 要先做，或彼此會改到同一處（例如定時同步的排程機制取決於部署平台）。
- **建議順序**：考慮優先度與相依性後的處理順序，每一列附上要執行的指令（`/issue <N>`）。

表格後另外列出：內容不足以開始開發、要先補資訊的 issue，包括沒寫受影響的人遇到的情境或驗收方式的（格式見 `docs/issues.md`；只標出缺什麼，不改寫）；看起來重複或已經不需要的 issue（只建議，不關閉）。

## 3. 開發者確認後才加標籤

開發者可以修改建議的優先度。沒有確認前，不建立標籤、不改任何 issue。

確認後：

1. 缺少的標籤先建立：`gh label create "priority:high" --color B60205`（medium `FBCA04`、low `0E8A16`）。
2. issue 已有別的 `priority:*` 標籤時，先移除：`gh api -X DELETE repos/{owner}/{repo}/issues/<N>/labels/<舊標籤>`（標籤名稱裡的 `:` 要 URL encode 成 `%3A`）。
3. 加上新標籤：`gh api -X POST repos/{owner}/{repo}/issues/<N>/labels -f "labels[]=priority:high"`。

不用 `gh issue edit`：原因見 CLAUDE.md「開發流程」。

4. 檢查：`gh issue view <N> --json labels --jq '[.labels[].name | select(startswith("priority:"))]'`，每個 issue 要剛好一個 `priority:*` 標籤；不是的話（例如移除成功、加上失敗），修正後再檢查一次。

完成後回報每個 issue 的標籤變更，附上 issue 連結。
