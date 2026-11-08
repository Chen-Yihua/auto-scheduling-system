# acceptance-reviewer 的審查範圍改以 origin/main 為基準：規格審查紀錄

- 規格：[docs/specs/issue-21-reviewer-diff-origin-main.md](../../specs/issue-21-reviewer-diff-origin-main.md)
- PR：[#58](https://github.com/Chen-Yihua/auto-scheduling-system/pull/58)
- 等級：標準
- 輪數：1（第 1 輪 2026-11-08 草稿）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：3 項（Factual Error 1、Improvement Suggestion 2；Minor 1、Info 2）
- 開發者決策：0 項（#2、#3 兩項建議由開發者在規格核准後決定採用）
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-08 草稿 | #1–#3（#1） | 修正「背景／原因」第 3 點的檔案參照；沒有新增或改寫驗收條件，不跑第 2 輪。核准後開發者決定採用 #2、#3，只改「測試對應」AC1 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 「原因」第 3 點的「同一個檔案的 `:28`」照字面會指到 `SKILL.md:28` | Factual Error | Minor | 是 | 否 | 檔案代稱不明 | 改成明寫 `acceptance-reviewer.md:28`、`:7` | 主 session（依查證依據，不改變行為） | 規格已修改 |
| 2 | 1 | AC1 的手動驗證只比較檔案數，沒確認多出來的就是本機 `main` 與 `origin/main` 之間的改動 | Improvement Suggestion | Info | 否 | 否 | — | 核准後採用：「測試對應」AC1 加上比對多出來的檔案清單 | 開發者 | 規格已修改（見規格「修改紀錄」） |
| 3 | 1 | AC1 的驗證方式沒照 issue 用 worktree 移動 `main`，規格沒寫原因 | Improvement Suggestion | Info | 否 | 否 | — | 核准後採用：「測試對應」AC1 寫明不用 worktree 的原因（worktree 共用分支，移動 `main` 會改到真正的本機 `main`） | 開發者 | 規格已修改（見規格「修改紀錄」） |

## 問題說明

### #1 「原因」第 3 點的檔案參照

- 問題：「同一個檔案的 `:28`」接在講 `.claude/skills/feature/SKILL.md:72` 的句子後面，照字面會讀成 `SKILL.md:28`（「判斷不確定時取較高的等級」），實際要指的是 `.claude/agents/acceptance-reviewer.md:28`、`:7`。
- 影響：不影響任何 AC 或實作計畫，只會讓讀者找錯檔案。

## 開發者決策

無

## 尚未處理

無

## 查證紀錄

| 規格中的事實（AC／假設編號） | 結果 | 依據（檔案:行號） |
|---|---|---|
| 背景／原因 1：`acceptance-reviewer.md:7` 用 `git diff main...HEAD` | 正確 | `.claude/agents/acceptance-reviewer.md:7` |
| 背景／原因 2：`SKILL.md:72` 交給 reviewer 前 `git fetch origin main`，只更新 `origin/main`、不更新本機 `main` | 正確 | `.claude/skills/feature/SKILL.md:72`；git 的 fetch 行為 |
| 背景／原因 3：`acceptance-reviewer.md:28` 與 `SKILL.md:146` 用 `origin/main`，只有 `acceptance-reviewer.md:7` 用本機 `main` | 正確（第 1 輪修正後） | `.claude/agents/acceptance-reviewer.md:7`、`:28`；`.claude/skills/feature/SKILL.md:146` |
| 重現步驟出處：PR #18 審查第 5 輪 #3 | 正確 | `docs/reviews/issue-workflow-round5.md:50` |
| 重現步驟：本機 `main` `5ae21a7`、`origin/main` `e3286b8`，68 個檔案對 15 個 | 正確（實際重算） | `git diff --name-only 5ae21a7...70abd34`（68）、`e3286b8...70abd34`（15）；`70abd34` 是 PR #18 加入第 5 輪紀錄前的 HEAD |
| 不做 1：reviewer 唯讀 | 正確 | `.claude/agents/acceptance-reviewer.md:15`；issue #21「必要條件」 |
| 不做 2：`feature-implementer.md:8` 不在範圍內 | 正確 | `.claude/agents/feature-implementer.md:8`；issue #21「待調查」 |
| 假設 1：reviewer 只經由 `/feature` 第 3 節（含 `/issue`）叫起 | 正確 | `.claude/skills/feature/SKILL.md:72`；`.claude/skills/issue/SKILL.md:26-28`；`.claude/` 裡沒有其他地方叫起 |
| AC2：`.claude/` 裡 `<基準>...HEAD` 的寫法只有一處 | 正確 | `git grep` 只命中 `.claude/agents/acceptance-reviewer.md:7` |
| AC2 測試的 grep：修正前命中 `:7`，修正後的新文字不會命中 | 正確 | 對照 `acceptance-reviewer.md:7` 與實作計畫第 2 步 |
| AC3 測試：`grep -n 'git fetch origin main' SKILL.md` 只命中第 3 節 | 正確（`:146` 是 `git fetch origin`） | `.claude/skills/feature/SKILL.md:72`、`:146` |
| 不適用 3：分支從舊的本機 `main` 開時，`origin/main...HEAD` 只有分支自己的 commit | 正確 | 三點 diff 以 merge-base 為起點；`git merge-base --is-ancestor 5ae21a7 e3286b8` 成立 |
| 修 bug 格式與標準等級各節齊全 | 正確 | `docs/specs/README.md:71-78`、`:89` |

## 已接受的風險

- 開發者沒經過 `/feature` 第 3 節、直接叫 reviewer 又沒先 fetch 時，`origin/main` 可能是舊的（假設 1）；只有 `origin/main` 舊於分支的 merge-base 時範圍才會多出來，實際上很難發生。
- `feature-implementer` 從可能落後的本機 `main` 開分支不在這次範圍內；依「不適用的情境」第 3 列，這不會讓 `origin/main...HEAD` 的審查範圍變多或變少，實作審查不要把它當成 AC1 的新發現。
