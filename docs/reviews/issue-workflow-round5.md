# 開發流程升級（/issue-triage、/issue）：審查第 5 輪

- 規格：本次為流程文件改動，沒有 `docs/specs/` 規格檔；驗收條件 AC1–AC12 見 PR #18 描述
- PR：#18
- 日期：2026-11-04
- 審查的版本：`70abd34`（`git diff 7dad5ce..HEAD`：`84a3280`、`70abd34`）
- 結果：**沒有阻擋項目**（Improvement Suggestion 3）

## 審查報告

> `acceptance-reviewer` 的報告原文，只調整了標題層級、精簡了查證紀錄。

只跑了唯讀指令：`git diff`、`git log`、`git show`、`git rev-parse`、`grep`、`gh api` GET（讀 PR 描述）、`python3 -I -m json.tool`。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過（這輪沒有改動） | `.claude/skills/issue-triage/SKILL.md:12-29`、`:33` |
| AC2 | 通過（只看文件） | `.claude/skills/issue-triage/SKILL.md:31-43` |
| AC3 | 通過 | `.claude/skills/issue/SKILL.md:13-33`；`.claude/skills/feature/SKILL.md:13-24` |
| AC4 | 通過 | `.claude/skills/issue/SKILL.md:30`；`docs/specs/README.md`「bug 簡化格式」；`.claude/skills/feature/SKILL.md:22`；`.claude/agents/acceptance-reviewer.md:11` |
| AC5 | 通過：標成「漏洞」的項目排除在外，也有開發者例外 | `.claude/skills/feature/SKILL.md:38`、`:42`、`:54-60`；`.claude/skills/issue/SKILL.md:36`；`docs/decisions/0003-issue-workflow.md:14`、`:23` |
| AC6 | 通過 | `.claude/skills/feature/SKILL.md:38`、`:40`、`:43`、`:45`、`:47-52`；`docs/decisions/0003-issue-workflow.md:17` |
| AC7 | 通過 | `.claude/skills/feature/SKILL.md:39`、`:41` |
| AC8 | 通過 | `.claude/settings.json:19-21`（JSON 格式正確）；`docs/decisions/0003-issue-workflow.md:29` |
| AC9 | 通過 | `.claude/agents/acceptance-reviewer.md:42-43`、`:47`；`.claude/skills/feature/SKILL.md:38`、`:64`、`:80` |
| AC10 | 通過 | `.claude/skills/feature/SKILL.md:66-67`、`:84-85`；`.claude/agents/feature-implementer.md:13`；`docs/reviews/README.md:5`、`:20` |
| AC11 | 通過；`acceptance-reviewer.md:19` 有一句舊文字，見 #1 | `.claude/skills/feature/SKILL.md:64`、`:68-80`；`docs/decisions/0003-issue-workflow.md:15`、`:26` |
| AC12 | 通過 | `.claude/skills/feature/SKILL.md:34`、`:87`、`:89`；`docs/reviews/README.md:24-28`；`.claude/agents/acceptance-reviewer.md:49`；`docs/decisions/0003-issue-workflow.md:16`、`:27` |

### 第 4 輪項目的處理確認

- **#1、#2、#7**：已解決。private fork 和 ruleset 相關內容已移除；grep `fork`、`bypass`、`安全問題不公開`、`私有 CI`，只剩 ADR 0003 第 26 行（「放棄的做法」，敘述正確）和歷史審查紀錄。
- **#3**：已解決。「漏洞」不論分類都阻擋（`.claude/skills/feature/SKILL.md:38`、`.claude/agents/acceptance-reviewer.md:42`）；實作 agent 發現漏洞時停下來、不修正（`.claude/agents/feature-implementer.md:13`）。
- **#4**：已解決。PR #18 描述的 AC5 已改成「標成『漏洞』的除外」，修改紀錄也記下了。
- **#6**：已解決（`.claude/skills/feature/SKILL.md:34`），相關小問題見 #3。
- **#8**：已解決（`.claude/skills/feature/SKILL.md:42`、`docs/decisions/0003-issue-workflow.md:14`、`:23`），和實作 agent 規則的小落差見 #2。
- **#9**：已解決（`docs/decisions/0003-issue-workflow.md:15`、`docs/reviews/issue-workflow-round3.md:46`）。
- **AC8**：已解決（`.claude/settings.json:20-21`）。

「漏洞的處理」、分類表、`/issue`、兩個 agent、`docs/reviews/README.md`、ADR 0003 對「一律阻擋、暫停並回報、開發者決定前不公開不推送、advisory 經確認才建立」寫法一致；唯一殘留見 #1。

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Improvement Suggestion | 否 | 否 | 審查 agent 的定義寫「主 session 存檔前會把細節改寫成 private advisory 編號」，好像每個漏洞都會建立 advisory；新規則是先改寫成一般性的描述，advisory 要開發者確認後才建立。實際做法不受影響 | `.claude/agents/acceptance-reviewer.md:19`；`.claude/skills/feature/SKILL.md:68`、`:84`；`docs/reviews/README.md:5` | 改成「改寫成一般性的描述（或開發者確認建立後的 advisory 編號）」 |
| 2 | Improvement Suggestion | 否 | 否 | 開發者要求在這個 PR 修不阻擋的發現時，實作 agent 的規則是不對應驗收條件的要求不做，`/feature` 也規定每項修正要對應驗收條件；兩邊都沒寫要先把這項寫成驗收條件 | `.claude/skills/feature/SKILL.md:42`、`:95`；`.claude/agents/feature-implementer.md:15` | 補一句：開發者要求在這個 PR 處理時，先寫成驗收條件、記修改紀錄，再交給實作 agent |
| 3 | Improvement Suggestion | 否 | 否 | 審查 agent 用 `git diff main...HEAD`，比對本機 `main`；`git fetch origin main` 只更新 `origin/main`。本機 `main` 比 `origin/main` 舊時，審查範圍會混進已合併的其他 PR 改動（實測 68 個檔案 vs 15 個） | `.claude/agents/acceptance-reviewer.md:7`；`.claude/skills/feature/SKILL.md:34` | 改用 `git diff origin/main...HEAD` |

補充（不列為發現）：PR #18 描述的檔案表沒有列 `.claude/settings.json`、`.claude/agents/feature-implementer.md`、`docs/reviews/README.md`。

## 處理結果

| # | 處理 | 決定者 | 根本原因 | commit / issue / advisory 編號 |
|---|---|---|---|---|
| 1–3 | 不阻擋，照「不阻擋的發現開 issue」自動開 issue | 規則 | — | #19（#1）、#20（#2）、#21（#3） |
| 補充 | 同步 PR #18 描述的檔案表 | 主 session（文件同步） | — | PR #18 描述 |
