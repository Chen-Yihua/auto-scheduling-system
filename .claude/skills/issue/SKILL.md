---
name: issue
description: 針對指定的 GitHub Issue 執行和 /feature 相同的開發流程。用 /issue <issue 編號> 執行。
disable-model-invocation: true
argument-hint: <issue 編號>
---

# Issue 開發流程

參數：$ARGUMENTS

## 1. 讀取 issue

從參數取出第一個數字當作 N（`#16`、`16 修時區` 都是 16）；沒有數字時先問開發者要做哪個 issue。之後的指令一律用 N，不把原始參數放進 shell。

```bash
gh issue view <N> --json number,title,body,labels,comments,state
```

issue 已關閉時，先問開發者要不要繼續。提問照 `feature`「硬規則」第 4 條。

issue 是需求來源，但不是已核准的規格：「建議的驗收條件」「修法參考」也要寫進規格、經開發者核准。issue 只寫了程式狀態、沒寫使用者遇到的情境時（`docs/issues.md`），讀程式碼後在規格的「背景」補上，不改寫 issue。

## 2. 照 `/feature` 的流程執行

讀 `.claude/skills/feature/SKILL.md`，照它的流程做，差別只有：

| 項目 | `/issue` 的做法 |
|---|---|
| 規格檔 | `docs/specs/issue-<N>-<簡短名稱>.md`，開頭附 issue 連結 |
| 等級 | 依 issue 要改的範圍判斷；`bug`、`enhancement` 標籤不決定等級。有 `bug` 標籤時，規格另外照 `docs/specs/README.md`「修 bug 時」 |
| 需求問答 | issue 裡的現象可以當成查到的事實，但仍要讀程式碼確認。「建議的驗收條件」「修法參考」當成題目、附上建議答案問開發者。快速路徑不另外問，直接寫進短版規格，一起核准 |
| 分支 | `issue-<N>-<簡短名稱>` |
| PR 描述 | 要有 `Closes #<N>`，合併後 issue 才會自動關閉 |

`Closes #<N>` 照順序確認：

1. 交給 `feature-implementer` 時要求加上（文字修正由你開 PR 時加）。
2. 每次更新 PR 描述後，用 `gh api repos/{owner}/{repo}/pulls/<PR> --jq .body` 確認還在。
3. 不見了就以目前的描述為基礎補上一行，再 `gh api -X PATCH`。不能只送 `Closes #<N>`：PATCH 會用送出的內容取代整份描述。

開發中發現和這個 issue 無關的問題，照 `implement-and-review`「開 issue 追蹤」處理，不在這個 PR 修；漏洞照 CLAUDE.md「漏洞」，不開 issue。
