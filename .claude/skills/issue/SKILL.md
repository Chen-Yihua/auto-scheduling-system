---
name: issue
description: 針對指定的 GitHub Issue 執行開發流程（規格 → 實作 → 審查 → PR），流程與 /feature 相同，規格與審查的深度依等級調整
disable-model-invocation: true
argument-hint: <issue 編號>
---

# Issue 開發流程

參數：$ARGUMENTS

## 1. 讀取 issue

從參數取出第一個數字當作 N（`#16`、`16 修時區` 都是 16）；沒有數字時先問開發者要做哪個 issue。之後的指令一律用 N，不要把原始參數直接放進 shell。

```bash
gh issue view <N> --json number,title,body,labels,comments,state
```

issue 已關閉時停下來，問開發者要不要繼續。

這一節向開發者提問（沒有 issue 編號、issue 已關閉）也用 `/feature` 第 1 節「需求問答」的 ❓／➡️ 文字格式，不用 AskUserQuestion。

issue 的內容與留言就是需求來源，但不等於已核准的規格：issue 裡寫的「建議的驗收條件」「修法參考」也要寫進規格、經開發者核准。內容不足以寫出驗收條件時，照 `/feature` 第 3 節「規格問題的處理」問開發者。

issue 只寫了程式狀態、沒寫受影響的人遇到的情境時（格式見 `docs/issues.md`），讀程式碼後在規格的「背景」或「現象」補上，不改寫 issue。驗收條件照 `docs/specs/README.md`「驗收條件怎麼寫」。

## 2. 照 `/feature` 的流程執行

讀 `.claude/skills/feature/SKILL.md`，照第 1–4 節執行，差異只有：

| 項目 | `/issue` 的做法 |
|---|---|
| 規格檔 | `docs/specs/issue-<N>-<簡短名稱>.md`，開頭寫來源 issue 連結 |
| 等級與規格格式 | 等級照 `/feature` 第 1 節「判斷等級」，依 issue 要改的範圍判斷；`bug`、`enhancement` 標籤不決定等級。規格照 `docs/specs/README.md`「格式」與「各等級的規格」；issue 有 `bug` 標籤時，另外照「修 bug 時」。草稿與核准方式照 `/feature` 第 1 節（草稿寫在 scratchpad，開發者明確表示核准才算核准） |
| 需求問答 | 照 `/feature` 第 1 節「需求問答」，依同一個等級規則決定要不要做（標準、高風險才做）。issue 裡的現象與程式狀態可以當作查到的事實，但仍要讀程式碼確認；「建議的驗收條件」「修法參考」在問答裡當成題目、附上建議答案問開發者，不直接編成 Context 項 |
| 分支 | `issue-<N>-<簡短名稱>` |
| 審查紀錄 | `docs/reviews/implementation/issue-<N>-<簡短名稱>.md`；規格審查是 `docs/reviews/specification/issue-<N>-<簡短名稱>.md`。文字修正沒有規格檔與審查紀錄 |
| PR 描述 | 交給 `feature-implementer` 時明確要求 PR 描述加上 `Closes #<N>`（文字修正由你自己開 PR 時加上）；每次更新 PR 描述後（包括 `/feature` 第 4 節放驗收表時），用 `gh api repos/{owner}/{repo}/pulls/<PR> --jq .body` 確認描述裡有；沒有就以目前的描述為基礎補上一行，再 `gh api -X PATCH`，不要只送 `Closes #<N>` 把整份描述蓋掉。合併後 issue 會自動關閉 |

開發中發現和這個 issue 無關的問題，照 `/feature` 的「不阻擋的發現開 issue」規則開新 issue（可被利用的漏洞照「漏洞的處理」，不開 issue），不在這個 PR 修。
