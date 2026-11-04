# 開發流程升級（/issue-triage、/issue）：審查第 1 輪

- 規格：本次為流程文件改動，沒有 `docs/specs/` 規格檔；驗收條件 AC1–AC8 見 PR #18 描述
- PR：#18
- 日期：2026-11-04
- 審查的版本：`9b3f076`（`git diff origin/main...HEAD`，8 個檔案）
- 結果：**有阻擋**（Implementation Defect 2、Missing Acceptance Criteria 2）

## 審查報告

> `acceptance-reviewer` 的報告原文，只調整了標題層級。

執行過的唯讀查證（gh 2.45.0）：`gh issue view 16 --comments`、`gh issue view 16 --json ...`、`gh issue list --state all --search ...`、`gh label list`、`gh help api`、`gh repo view --json visibility`、讀取 main ruleset。沒有執行任何會改 GitHub 的指令。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 不通過 | 輸出內容與「確認前不改 issue」都有寫（`.claude/skills/issue-triage/SKILL.md:9`、`:22-30`、`:34`）。但讀取指令 `.claude/skills/issue-triage/SKILL.md:15` 的 `gh issue view <N> --comments` 在本機 gh 2.45 實測會失敗（`GraphQL: Projects (classic) is being deprecated ... (repository.issue.projectCards)`，exit 1），照文件做會讀不到 issue 內容。見發現 #1 |
| AC2 | 通過（只看文件） | `.claude/skills/issue-triage/SKILL.md:34-42`。用 `gh help api` 查證過 `-f "labels[]=..."` 這種陣列寫法和 `{owner}/{repo}` 佔位符都支援；DELETE 路徑裡的 `:` 編碼成 `%3A` 可以用。目前 repo 沒有任何 `priority:*` 標籤（`gh label list`），所以第 1 步「先建立標籤」一定會跑到。寫入的指令沒有實際執行 |
| AC3 | 通過 | `.claude/skills/issue/SKILL.md:9`、`:14`（`--json` 版本實測可用）、`:23-31`；`.claude/skills/feature/SKILL.md:15`、`:22`。`Closes #N` 要由誰寫進 PR 描述沒有講清楚，見發現 #6 |
| AC4 | 通過 | `docs/specs/README.md:50-91`（AC1 固定在 `:75-77`，回歸測試在 `:82-84`、`:91`）；`.claude/skills/issue/SKILL.md:28`。格式和既有規則有衝突，見發現 #4 |
| AC5 | 通過（只看文件） | `.claude/skills/feature/SKILL.md:39`、`:51-57`、`:28`、`:72`；`.claude/agents/acceptance-reviewer.md:42`；`.claude/skills/issue/SKILL.md:33`。`gh issue list --state all --search` 實測可用。`gh issue create` 和 `gh issue comment` 在 gh 2.45 會不會撞到同一個 projectCards 錯誤，因為是寫入指令沒有測，無法確認。settings 的 allow 也沒有加（見發現 #2），所以「自動開 issue」每次都會跳出權限確認 |
| AC6 | 通過（限 AC 寫到的範圍） | `.claude/skills/feature/SKILL.md:37`、`:40`、`:42`、`:47`；`.claude/agents/acceptance-reviewer.md:13`、`:40`。但「涉及安全、卻不是 Implementation Defect 的發現」會被自動開成公開 issue，見發現 #3 |
| AC7 | 通過 | `.claude/skills/feature/SKILL.md:36`、`:38` |
| AC8 | 不通過 | `.claude/settings.json:11-15` 沒有改，deny 只有 `Bash(gh pr merge *)`，沒有 `Bash(gh api *merge*)`；目前只有文字規則 `.claude/skills/feature/SKILL.md:68` 和 `CLAUDE.md:30`。已知原因：修改 `.claude/settings.json` 被 auto mode 擋下，需要開發者手動處理。見發現 #2 |

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Implementation Defect | 是 | 否 | `/issue-triage` 用 `gh issue view <N> --comments` 讀每個 issue。本機 gh 2.45 不加 `--json` 時，會去查已停用的 classic Projects 欄位（`repository.issue.projectCards`），實測失敗（exit 1）。加上 `--json`（`/issue` 的寫法）就能用。結果是 AC1「每個 issue 都要讀內容與留言」照文件做不到。CLAUDE.md 只寫了 `gh pr edit` / `gh issue edit` 會失敗，沒提到不加 `--json` 的 `view` 也會失敗，之後寫新指令的人還會踩到 | `.claude/skills/issue-triage/SKILL.md:15`；`CLAUDE.md:28`；對照 `.claude/skills/issue/SKILL.md:14` | 改成 `gh issue view <N> --json number,title,body,labels,comments,state`；CLAUDE.md 第 28 行補上「`gh issue view` / `gh pr view` 要加 `--json`」 |
| 2 | Implementation Defect | 是 | 安全（權限） | AC8 沒完成：`.claude/settings.json` 沒有加 deny `Bash(gh api *merge*)`，也沒有加計畫中的 allow（`gh issue view/list/create`、`gh label list`）。查證過 main ruleset 的 `required_approving_review_count` 是 0，所以 CI 通過後，agent 用 `gh api -X PUT repos/{owner}/{repo}/pulls/<N>/merge` 就能合併，現在只有文字規則擋著。另外，ADR 0003 寫「合併已經有 deny 規則與 main 的 ruleset 擋著」，在 settings 改好之前這句話不成立。已知 auto mode 擋下了這項修改 | `.claude/settings.json:3-15`；`docs/decisions/0003-issue-workflow.md:24` | 由開發者手動在 `.claude/settings.json` 的 deny 加 `Bash(gh api *merge*)`、allow 加計畫中的四項，再用 `python -m json.tool` 檢查格式。改好之前，ADR 0003 第 24 行不要寫成已經擋住 |
| 3 | Missing Acceptance Criteria | 是 | 安全 | 缺漏的情境：涉及安全、但被分成 Improvement Suggestion 或不阻擋 Test Gap 的發現（例如原本就有的權限漏洞、憑證寫進 log），以及 implementer 回報的「發現但沒處理的問題」裡跟安全有關的項目。現在的規則只有「Implementation Defect（涉及安全）」會暫停，其他一律自動開 issue。這個 repo 是 **PUBLIC**（`gh repo view` 查證），漏洞的位置（`檔案:行號`）和利用方式會在開發者知道之前就公開。reviewer 定義裡寫「主 session 會依這欄決定要不要暫停」，但 `/feature` 只對 Implementation Defect 和架構有對應規則，兩邊對不上。影響範圍：`/feature` 和 `/issue` 的審查與實作回報流程 | `.claude/skills/feature/SKILL.md:28`、`:37`、`:39`、`:42`；`.claude/agents/acceptance-reviewer.md:40` | 建議的驗收條件（尚待開發者確認，不是已定的需求）：「任何一項發現的『涉及安全／架構』是『安全』時，不論分類都暫停問開發者，不自動開公開 issue；由開發者決定在這個 PR 修、開 issue，或走 GitHub private security advisory」。這項涉及安全性與資料處理（漏洞資訊要不要公開），選項要由開發者決定 |
| 4 | Missing Acceptance Criteria | 是 | 否 | 缺漏的情境：bug 簡化格式沒有「不適用的情境」「假設」「實作計畫」這幾段，但 `/issue` 是照 `/feature` 第 1 節寫規格，第 1 節要求逐一想過失敗、空資料、未登入等情境，不適用的寫進「不適用的情境」，也要列計畫與假設。reviewer 第 3 項也用「不適用的情境」來判斷 Missing AC。照文件做，有兩種可能：主 session 不知道這些內容該寫在哪；或 reviewer 每份 bug 規格都回報 Missing AC，開發者每次都被打斷。影響範圍：所有 `bug` 標籤的 `/issue` | `docs/specs/README.md:54-89`；`.claude/skills/feature/SKILL.md:18-20`；`.claude/agents/acceptance-reviewer.md:11` | 建議的驗收條件（尚待確認）：二選一。(a) bug 格式加上「假設」「不適用的情境」「修正方式（要改的檔案）」三段；(b) 在 `feature/SKILL.md` 第 1 節和 reviewer 第 3 項寫明 bug 格式的豁免範圍。這項不涉及產品行為、權限或資料處理 |
| 5 | Improvement Suggestion | 否 | 否 | `/issue` 直接把 `$ARGUMENTS` 塞進 shell 指令。開發者打 `/issue #16` 時，`#16` 在 bash 裡會被當成註解開頭，變成執行不帶編號的 `gh issue view`，結果報錯；沒給參數，或多打說明文字（`/issue 16 修時區`）也會失敗。另外沒有 `argument-hint`，輸入 `/issue` 時看不到要填什麼 | `.claude/skills/issue/SKILL.md:1-5`、`:9`、`:14` | frontmatter 加 `argument-hint: <issue 編號>`；內文寫「從參數取出第一個數字當 N（去掉 `#`）；沒有數字時先問開發者」，之後的指令都用 N |
| 6 | Improvement Suggestion | 否 | 否 | `/issue` 規定 PR 描述要有 `Closes #<N>`，但 PR 是 `feature-implementer` 開的，它只拿到規格路徑和分支名稱，而且規格是它唯一的需求來源。完整格式的規格開頭也沒有 issue 欄位（只有 bug 格式有）。沒有寫明由誰、在哪一步加上 `Closes #N`，可能漏掉，合併後 issue 就不會自動關閉 | `.claude/skills/issue/SKILL.md:27`、`:31`；`.claude/skills/feature/SKILL.md:26`；`.claude/agents/feature-implementer.md:6`、`:10`；`docs/specs/README.md:12-13` | 在 `/issue` 寫明：交給 implementer 時附上「PR 描述加 `Closes #N`」，或由主 session 在第 4 節用 `gh api -X PATCH` 補上並確認；完整格式的開頭也加 `issue：#NN` 欄位 |
| 7 | Improvement Suggestion | 否 | 否 | ADR 0003 寫「不需要的 issue 可以在 `/issue-triage` 時關掉」，但 `/issue-triage` 規定看起來重複或不需要的 issue「只建議，不關閉」。兩份文件對「誰關 issue」的說法不一樣 | `docs/decisions/0003-issue-workflow.md:22`；`.claude/skills/issue-triage/SKILL.md:30` | ADR 改成「在 `/issue-triage` 時標出來，由開發者關閉」 |
| 8 | Improvement Suggestion | 否 | 否 | 開 issue 時要附「審查紀錄的連結」，但審查紀錄檔只在 PR 分支上。連到分支上的檔案，分支合併並刪除後連結就失效 | `.claude/skills/feature/SKILL.md:55` | 改成附 PR 連結加上檔案路徑（`docs/reviews/<名稱>-round<N>.md`，合併後在 main 也是同一個路徑），不要用分支的 blob URL |
| 9 | Improvement Suggestion | 否 | 否 | 改優先度的流程是先 DELETE 舊標籤、再 POST 新標籤。如果 POST 失敗，issue 會沒有任何 priority 標籤；也沒有確認「每個 issue 只有一個 `priority:*` 標籤」的步驟 | `.claude/skills/issue-triage/SKILL.md:39-42` | 完成後用 `gh issue view <N> --json labels` 檢查每個 issue 剛好只有一個 `priority:*` 標籤，再回報 |
| 10 | Improvement Suggestion | 否 | 否 | 有幾處小幅超出計畫，內容彼此一致，也沒有和 CLAUDE.md、ADR 0001、0002 衝突：CLAUDE.md 除了計畫裡的措辭修改，還多加了「改 issue 標籤用 `gh api .../labels`」一句；bug 格式多了「不做」一段；reviewer 多了第 5 項「安全與架構」檢查，並把這欄套用到所有發現，不只 Implementation Defect；`/feature` 第 3 節多了「不可合併 PR」限制 | `CLAUDE.md:28`；`docs/specs/README.md:79-80`；`.claude/agents/acceptance-reviewer.md:13`、`:28`、`:40`；`.claude/skills/feature/SKILL.md:68` | 保留即可，在 PR 描述註明這些是計畫外的補充 |

### 其他檢查結果（沒有發現問題）

- 引用都存在：`/issue` 引用的 `/feature`「第 1–4 節」（`.claude/skills/feature/SKILL.md:13`、`:24`、`:30`、`:70`）、「Missing AC 的處理」（`:44`）、「不阻擋的發現開 issue」（`:51`）；`docs/specs/README.md:50` 的「bug 簡化格式」；`CLAUDE.md:21` 的「開發流程」。
- 審查紀錄檔名一致：`.claude/skills/issue/SKILL.md:30` 的 `issue-<N>-<簡短名稱>-round<M>.md`，符合 `docs/reviews/README.md:3`「和規格檔同名」的規則。
- 兩個新 skill 都有 `disable-model-invocation: true`，只能由開發者觸發。`/issue` 是讀 `feature/SKILL.md` 這個檔案，不是呼叫 skill，所以不受這個設定影響。
- 和 ADR 0001、0002 沒有衝突：維持三個角色與四種分類，reviewer 仍然只讀；規格仍然放在 `docs/specs/`。

## 處理結果

| # | 處理 | 決定者 | commit / 連結 |
|---|---|---|---|
| 1 | `/issue-triage` 改用 `gh issue view --json`；CLAUDE.md 補上 `view` 要加 `--json` | 規則（不涉及安全的 Implementation Defect） | `c1d1b84` |
| 2 | ADR 0003 改成如實描述合併的防護方式；`.claude/settings.json` 待開發者手動修改（agent 修改自己的權限被 auto mode 擋下） | 開發者（涉及安全，暫停詢問） | ADR：`c1d1b84`；settings：待開發者 |
| 3 | 涉及安全的不阻擋發現改開 private security advisory，不開公開 issue；審查紀錄與 PR 描述只寫 advisory 編號，不留細節 | 開發者（選擇「自動開 private security advisory」） | 見下一個 commit |
| 4 | 在 `/feature` 第 1 節與 reviewer 第 3 項寫明 bug 簡化格式的豁免範圍 | 開發者（選擇「寫明豁免範圍」） | 見下一個 commit |
| 5–9 | 在本 PR 直接修：`/issue` 加 `argument-hint` 並從參數取出數字；寫明 `Closes #N` 由誰加與確認；ADR 與 triage 對「誰關 issue」一致；issue 附檔案路徑而非分支連結；改標籤後檢查每個 issue 只有一個 `priority:*` | 開發者（選擇「在這個 PR 直接修」，因為新規則尚未合併、內容都是本 PR 新增） | 見下一個 commit |
| 10 | 在 PR 描述註明計畫外的補充 | 開發者（同上） | PR #18 描述 |
