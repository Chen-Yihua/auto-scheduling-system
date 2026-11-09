# `/feature-grill` 實驗

實驗已在 2026-11-09 結束，問答併進了 `/feature`，見下面「結論」。以下的指標與進行方式保留實驗當時的內容。

確認寫規格前先做 grilling 問答（`/feature-grill`），是否真的讓需求理解更完整、降低 Missing AC，而不只是增加訪談時間。

## 結論

- **結束日期**：2026-11-09。
- **開發者決定提前結束**：原本的規則是實驗結束、開發者看過結果並決定前，不把 grilling 整合進正式流程；開發者在還沒做比較實驗時，決定把問答併進 `/feature`，只用在標準與高風險等級。
- **證據的限制**：只有一筆探索性紀錄（[records/staged-tasks-feature-grill.md](records/staged-tasks-feature-grill.md)），沒有和 `/feature` 的比較實驗，所以不能說明問答是否降低了 Missing AC。這筆紀錄看得到的是：問答帶出了會大幅改變範圍的決定；8 項 Missing AC 中有 3 項來自在 plan mode 中補問、沒有回到決策樹的決定；plan mode 只能用選單提問。
- **整合後的規則**：`.claude/skills/feature/SKILL.md` 第 1 節「需求問答」；決定與放棄的做法見 [ADR 0008](../../decisions/0008-grilling-without-plan-mode.md)。
- **`/feature-grill` 已刪除**：最後一版在 commit `23c56c9` 的 `.claude/skills/feature-grill/SKILL.md`（`git show 23c56c9:.claude/skills/feature-grill/SKILL.md`）。[TEMPLATE.md](TEMPLATE.md) 與 `records/` 引用的 `/feature-grill` 規則（例如「實驗紀錄」的 token 計算）從這一版找。

## 指標

主要指標是 **Missing AC**：審查或開發者在規格核准後才發現、規格沒寫到或互相矛盾的情境，也就是 [docs/reviews/README.md](../../reviews/README.md)「分類」裡的 Missing Acceptance Criteria 與 Specification Defect，依根本原因認定。Factual Error（規格寫錯現有行為）是寫規格時沒查證，另外計算。只看數量不夠，每一項都要標嚴重程度：

| 嚴重程度 | 定義 |
|---|---|
| Critical | 漏掉會造成資料錯誤或遺失、權限或安全問題，或主要流程無法使用 |
| Major | 使用者在一般操作下會遇到的行為缺漏或錯誤，但有替代做法 |
| Minor | 少見的邊緣情境、訊息文字、操作細節 |

其他指標用來判斷代價與副作用，定義見 [TEMPLATE.md](TEMPLATE.md)：需求釐清輪數、人工介入次數、規格審查發現、Review 輪數、假設被否決數量、需求變更次數、Token、開發時間。

規格核准前有規格審查（[ADR 0005](../../decisions/0005-specification-review.md)），兩個流程都會經過，所以比較仍然公平；但導入前後的紀錄不能直接比較，紀錄裡要寫「流程版本」。`staged-tasks` 是導入前唯一的一筆。

如果 Missing AC 沒有下降、只有釐清輪數和時間增加，就表示 grilling 只是延長了訪談。

## 進行方式

### 探索性實驗（已結束）

先用 1～2 個功能跑 `/feature-grill`，目的是看流程能不能順利走完、指標拿不拿得到，不和 `/feature` 比較。每個功能填一份紀錄，放在 `records/<功能>-feature-grill.md`。

### 比較實驗（已結束，沒有進行）

同一個功能分別用 `/feature` 和 `/feature-grill` 各做一次時，要避免兩次互相影響：

1. **相同起點**：兩次都從同一個 commit 開始。先記下 `git rev-parse origin/main`，再用 `git worktree add <目錄> -b <分支> <commit>` 各開一個 worktree，分支名稱加上流程名稱以便區分（例如 `feature/<功能>-grill`）。
2. **不共用對話**：兩次各開新的 Claude Code session，不在同一個對話裡做，也不把其中一次的規格、審查紀錄貼給另一次。
3. **開發者本身的偏差**：開發者第二次回答時已經想過一次，第二次的需求理解自然會比較好。紀錄裡要寫哪個流程先做；做兩個以上功能時，輪流調換先後順序。
4. **只合併一個 PR**：兩次都會開 PR。比較完之前兩個都不合併，比較完由開發者決定保留哪一個，另一個關掉。

`/feature` 不會自動填紀錄（不修改正式流程），所以用 `/feature` 的那一次，結束後照模板手動填一份，存成 `records/<功能>-feature.md`。

## 紀錄的提交（已結束）

紀錄不放進功能本身的 PR，因為比較實驗中有一個 PR 會被關掉，放在裡面的紀錄會跟著消失。實驗結束後，把 `records/` 和結果整理成一個 PR 提交。
