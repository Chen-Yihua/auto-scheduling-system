# 開發流程升級（/issue-triage、/issue）：審查第 4 輪

- 規格：本次為流程文件改動，沒有 `docs/specs/` 規格檔；驗收條件 AC1–AC11 見 PR #18 描述
- PR：#18
- 日期：2026-11-04
- 審查的版本：`59982a2`（`git diff 148716c..HEAD`：`b66a199`、`59982a2`）
- 結果：**有阻擋**（AC8、Missing AC 4）

## 審查報告

> `acceptance-reviewer` 的報告，依原文整理：驗收表與發現表的結論、分類、阻擋判定與依據都保留，敘述有精簡。內容是流程文件的缺漏，不是可被利用的程式漏洞，不改寫。

只跑了唯讀指令：`gh api` 的 GET（repo、rulesets、`--paginate` 查 advisory）、`git ls-remote`、`python3 -m json.tool`。沒有建立 advisory 或 fork。第 3 輪 #3–#7 已解決；#1 大致解決但 fork 流程本身有缺漏；#2 是 AC8；#8、#9 只剩小地方。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過（這輪沒有改動） | `.claude/skills/issue-triage/SKILL.md:14-18`、`:30`、`:34` |
| AC2 | 通過（只看文件） | `.claude/skills/issue-triage/SKILL.md:36-44` |
| AC3 | 通過 | `.claude/skills/issue/SKILL.md:14`、`:26-34` |
| AC4 | 通過 | `.claude/skills/feature/SKILL.md:15`、`:22`；`.claude/skills/issue/SKILL.md:31`；`.claude/agents/acceptance-reviewer.md:11` |
| AC5 | 通過（只看文件），但文字和 AC9 對不起來，見 #4 | `.claude/skills/feature/SKILL.md:41`、`:54-60` |
| AC6 | 通過 | `.claude/skills/feature/SKILL.md:39`、`:45`、`:47-52`；`docs/decisions/0003-issue-workflow.md:16` |
| AC7 | 通過 | `.claude/skills/feature/SKILL.md:38`、`:40` |
| AC8 | 不通過 | `.claude/settings.json:16-20`（工作目錄）：deny 沒有 `Bash(gh api *merge*)` |
| AC9 | 通過（只看文件；只跑過 GET），和 AC11 有矛盾，見 #3 | `.claude/skills/feature/SKILL.md:42`、`:73-85`、`:96` |
| AC10 | 通過（只看文件），fork 裡的規格檔合併後會公開，見 #1 | `.claude/skills/feature/SKILL.md:64`、`:71`、`:96-97`；`.claude/agents/feature-implementer.md:13`；`.claude/agents/acceptance-reviewer.md:19`、`:42-43`；`docs/reviews/README.md:5`、`:20` |
| AC11 | 不通過：fork 流程照文件做不出來（#1、#2）；「本 PR 新增」和不阻擋漏洞的規則矛盾（#3） | `.claude/skills/feature/SKILL.md:66-71`、`:87-92`；`docs/decisions/0003-issue-workflow.md:15`、`:34` |

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Missing Acceptance Criteria | 是 | 安全 | fork 流程沒寫本機怎麼操作 fork：唯一的 remote 是公開的 `origin`，`git push`、`gh pr create` 都在 allow 裡不會跳確認，照 implementer 的預設流程會把修正推到公開 repo。fork 裡 commit 的規格檔合併後會公開。fork 流程要不要走 plan mode 規格核准也沒寫 | `.claude/skills/feature/SKILL.md:87-92`；`.claude/agents/feature-implementer.md:8`、`:10`、`:13`；`.claude/settings.json:8-9` | 選項由開發者決定，例如：另一個目錄 clone fork、push 與 PR 一律指定 fork；規格只寫一般性描述或不放進 fork |
| 2 | Missing Acceptance Criteria | 是 | 安全／架構 | main 的 ruleset 要求三項 status check 且沒有 bypass；fork 不跑 Actions，check 不會產生，從 advisory 合併可能會被擋（唯讀無法實測） | `.claude/skills/feature/SKILL.md:90`、`:92`；`docs/decisions/0003-issue-workflow.md:34`；ruleset `26308934` | 選項由開發者決定：合併時暫時加 bypass、advisory 公開後再走一般 PR，或其他做法 |
| 3 | Missing Acceptance Criteria | 是 | 安全 | 「不阻擋、標成漏洞、只在本 PR 新增」的項目：分類表說只建 advisory，「漏洞所在」表說要在同一個 PR 修，implementer 又規定沒有 AC 就不修，新漏洞可能隨 PR 合併 | `.claude/skills/feature/SKILL.md:42`、`:71`、`:73`；`.claude/agents/feature-implementer.md:15` | 選項由開發者決定：本 PR 新增的漏洞不論分類都當成阻擋並問開發者；或只建 advisory 並寫明接受合併 |
| 4 | Missing Acceptance Criteria | 是 | 否 | AC5 寫「涉及安全的除外」，但 AC9 已改成只涵蓋「漏洞」，不阻擋的「安全」類發現兩條 AC 都沒管到（skill 的做法本身一致） | 計畫檔與 PR #18 的 AC5；`.claude/skills/feature/SKILL.md:41` | AC5 改成「標成『漏洞』的除外」並記修改紀錄 |
| 5 | Improvement Suggestion | 否 | 否 | PATCH advisory 會整段取代 description；建立 fork 是非同步的（202） | `.claude/skills/feature/SKILL.md:75`、`:89` | 先 GET 再接上新內容；等 fork 可存取再交給 implementer |
| 6 | Improvement Suggestion | 否 | 否 | `git show origin/main:<檔案>` 前沒有先 fetch | `.claude/skills/feature/SKILL.md:66`；`.claude/agents/acceptance-reviewer.md:42` | 主 session 先 `git fetch origin main` |
| 7 | Improvement Suggestion | 否 | 否 | Missing AC 第 2 步的選項沒排除 main 已有的漏洞（不能在公開 PR 修） | `.claude/skills/feature/SKILL.md:50-52`、`:70` | 第 2 步加上 main 已有漏洞的選項 |
| 8 | Improvement Suggestion | 否 | 否 | 本 PR 把不阻擋的發現在 PR 裡修了，和新規則「不阻擋一律開 issue」不一致，文件沒有開發者例外條款 | `.claude/skills/feature/SKILL.md:41`；`docs/decisions/0003-issue-workflow.md:22`；`docs/reviews/issue-workflow-round3.md:50-56` | 寫明「開發者明確要求時可在當前 PR 修」，或註明這次是規則生效前的例外 |
| 9 | Improvement Suggestion | 否 | 否 | ADR 0003 少列「docstring」；第 3 輪紀錄的欄名是舊的 | `docs/decisions/0003-issue-workflow.md:15`；`docs/reviews/issue-workflow-round3.md:46` | 補上 |
| 10 | Improvement Suggestion | 否 | 否 | 本機計畫檔的「改動」一節是舊版 | `/root/.claude/plans/binary-roaming-charm.md` | 要沿用再同步 |

## 處理結果

| # | 處理 | 決定者 | commit / issue / advisory 編號 |
|---|---|---|---|
| 1–10 | 待開發者決定 | 開發者 | 待處理 |
