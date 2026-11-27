# 架構決策紀錄（ADR）

記錄之後的人會想問「為什麼不用 X」的架構決定。開發流程的規則寫在 `CLAUDE.md` 與 `.claude/skills/`，不寫 ADR。

- 一個決定一個檔案，檔名 `NNNN-<簡短名稱>.md`，編號遞增、不重複使用。
- 核准前寫在草稿資料夾（`.drafts/`），核准後才 commit。
- 決定被推翻時，新增一份 ADR，把舊檔的狀態改成「已被 NNNN 取代」（只推翻一部分時寫「部分被 NNNN 取代」），其他內容不改。

## 格式

```markdown
# NNNN. 標題

- 狀態：已採用 | 部分被 NNNN 取代 | 已被 NNNN 取代
- 日期：YYYY-MM-DD

## 背景
遇到什麼問題、有什麼限制。

## 決定
做了什麼選擇。

## 放棄的做法
考慮過但沒選的做法，以及沒選的原因。

## 影響
這個決定帶來的代價和之後要遵守的規則。
```

## 清單

| 編號 | 標題 | 狀態 |
|---|---|---|
| [0001](0001-subtask-order-on-parent.md) | 子任務的階段順序存在主任務上 | 已採用 |
| [0002](0002-api-error-status-codes.md) | API 錯誤回應：狀態碼表示類別，error_code 表示原因 | 部分被 [0005](0005-merge-api-error-codes.md) 取代 |
| [0003](0003-scheduled-sync-trigger.md) | 外部平台定時同步由 GitHub Actions 觸發 | 已採用 |
| [0004](0004-path-filtered-ci.md) | CI 依改到的檔案決定要跑的測試與部署 | 已採用 |
| [0005](0005-merge-api-error-codes.md) | 對外 error_code 只分會改變處理方式的原因，外部服務錯誤用共用規則轉換 | 已採用 |
