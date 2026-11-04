# 開發流程升級（/issue-triage、/issue）：審查第 3 輪

- 規格：本次為流程文件改動，沒有 `docs/specs/` 規格檔；驗收條件 AC1–AC10 見 PR #18 描述
- PR：#18
- 日期：2026-11-04
- 審查的版本：`47d6a48`（`git diff 290029f..HEAD`：`fb2c0a4`、`47d6a48`）
- 結果：**有阻擋**（AC8、Missing AC 1）

## 審查報告

> `acceptance-reviewer` 的報告，依原文整理：驗收表、發現表的每一項結論、分類、阻擋判定與依據都保留，敘述有精簡。報告提到的安全問題是流程文件本身的缺漏，不是可被利用的程式漏洞，所以不改寫。

審查範圍：`git diff 290029f..HEAD`。驗收條件 AC1–AC10 依計畫檔與 PR #18 描述，兩邊一致。`.claude/settings.json` 依工作目錄現況判斷，尚未 commit。第 2 輪的 #1–#6 都已解決。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | `.claude/skills/issue-triage/SKILL.md:14-18`、`:30`、`:34` |
| AC2 | 通過（只看文件） | `.claude/skills/issue-triage/SKILL.md:36-44` |
| AC3 | 通過 | `.claude/skills/issue/SKILL.md:14`、`:22`、`:26-34` |
| AC4 | 通過 | `docs/specs/README.md:51-92`；`.claude/skills/feature/SKILL.md:15`、`:22`；`.claude/agents/acceptance-reviewer.md:11` |
| AC5 | 通過（只看文件） | `.claude/skills/feature/SKILL.md:41`、`:54-60` |
| AC6 | 通過 | `.claude/skills/feature/SKILL.md:39`、`:45`、`:47-52`；`docs/decisions/0003-issue-workflow.md:16` |
| AC7 | 通過 | `.claude/skills/feature/SKILL.md:38`、`:40` |
| AC8 | 不通過 | `.claude/settings.json:16-20`（工作目錄，尚未 commit）：deny 還沒有 `Bash(gh api *merge*)`；allow `:10-14` 已加上，`:10`、`:11`、`:13` 行尾有多餘空白。`docs/decisions/0003-issue-workflow.md:26` 的描述目前還不成立 |
| AC9 | 通過（只看文件，POST 沒有實際送出） | `.claude/skills/feature/SKILL.md:42`、`:66-78`、`:82` |
| AC10 | 不通過 | 保密規定已寫入 `.claude/skills/feature/SKILL.md:52`、`:64`、`:80`、`:82`、`:84`；`.claude/agents/feature-implementer.md:13`；`.claude/agents/acceptance-reviewer.md:19`；`docs/reviews/README.md:5`、`:20`；`docs/decisions/0003-issue-workflow.md:15`。但在這個 PR 修時，規格檔、測試名稱、PR 驗收表會寫出細節，見發現 #1 |

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Missing Acceptance Criteria | 是 | 安全 | 開發者決定在這個 PR 修安全問題時，其他規則會把細節公開：(a) Missing AC 第 3 步要把驗收條件寫進公開的規格檔與修改紀錄，這條 AC 本身就是漏洞描述；(b) implementer 的測試名稱要看得出對應哪條 AC；(c) PR 描述要放驗收表（AC → 測試 → 結果），和 AC10 直接矛盾；(d) 修正的 diff 本身就公開在 PR 上，漏洞在 main 已有的程式裡時，PR 開出來到合併之前就已公開。AC10 的禁止範圍沒有列規格檔與測試 | `.claude/skills/feature/SKILL.md:51`、`:64`、`:80`、`:97`；`.claude/agents/feature-implementer.md:9`、`:10`、`:13` | 選項由開發者決定：**1** 漏洞在 main 已有的程式時，改用 advisory 的 temporary private fork 修正；**2** 接受 diff 會公開，AC10 擴大到規格檔、測試名稱、PR 驗收表，一律用一般性描述；**3** 只有 main 已有的程式才保密（推翻第 2 輪的範圍 A）。不論選哪個，相關規則都要一致並更新 AC10 |
| 2 | Implementation Defect | 是（AC8） | 安全 | deny 還沒有 `Bash(gh api *merge*)`；allow 的修改也還沒 commit | `.claude/settings.json:16-20`、`:10-14` | 加上 deny 後和 allow 一起 commit，清掉行尾空白 |
| 3 | Improvement Suggestion | 否 | 否 | 「安全問題不公開」沒有區分「可被利用的漏洞」與「流程或文件本身的安全缺漏」，第 2 輪的紀錄只能自己加豁免說明，和「唯一的例外」不一致 | `.claude/skills/feature/SKILL.md:64`、`:82`；`docs/reviews/issue-workflow-round2.md:11` | 寫明只改寫可被利用的漏洞，或讓 reviewer 另外標「是否為可被利用的漏洞」 |
| 4 | Improvement Suggestion | 否 | 否 | 查到重複 advisory 之後要做什麼沒寫；查詢沒有 `--paginate` | `.claude/skills/feature/SKILL.md:68`、`:56` | 已有相同的就沿用 GHSA 編號、需要時 PATCH 補充；查詢加 `--paginate` |
| 5 | Improvement Suggestion | 否 | 否 | 流程沒有一步要記錄建立了哪些 advisory | `.claude/skills/feature/SKILL.md:84`、`:97`；`docs/reviews/README.md:24-28` | 處理結果與回報加上 advisory 編號 |
| 6 | Improvement Suggestion | 否 | 否 | 審查紀錄改寫後，下一輪 reviewer 看不到原本的問題 | `.claude/skills/feature/SKILL.md:80`、`:82`、`:86` | 重新審查時由主 session 把原始內容寫進給 reviewer 的指示 |
| 7 | Improvement Suggestion | 否 | 否 | implementer 只有「指示裡寫明」時才保密，自己發現的安全問題可能先寫進 commit | `.claude/agents/feature-implementer.md:13` | 改成「修正或發現涉及安全的問題時」 |
| 8 | Improvement Suggestion | 否 | 否 | ADR 0003 寫「一律」開 issue 與安全例外矛盾；公開場所少列「程式註解」 | `docs/decisions/0003-issue-workflow.md:14`、`:15` | 補上例外與「程式註解」 |
| 9 | Improvement Suggestion | 否 | 否 | 本機計畫檔的驗證步驟、settings 清單沒同步 | `/root/.claude/plans/binary-roaming-charm.md` | PR 描述已是最新版；計畫檔要沿用再同步 |

## 處理結果

| # | 處理 | 決定者 | commit / issue / advisory 編號 |
|---|---|---|---|
| 1 | 漏洞在 main 已有的程式 → advisory 的 temporary private fork 修；只在本 PR 新增的程式 → 同一個 PR 修，所有公開文字一般化。AC10 範圍加上規格檔與測試名稱，新增 AC11 | 開發者（選「private fork 修 main 的漏洞」「新程式在同一個 PR 修，文字一般化」） | `b66a199` |
| 2 | 待開發者在 `.claude/settings.json` 加 deny `Bash(gh api *merge*)` 並 commit | 開發者 | 待處理 |
| 3 | reviewer 的「涉及安全／架構」分成「漏洞」（可被利用，要保密）與「安全」（規格或流程缺漏，可公開） | 開發者（選「在這個 PR 修」） | `b66a199` |
| 4 | 查 advisory 加 `--paginate`；有重複就沿用 GHSA 編號、需要時 PATCH 補充 | 同上 | `b66a199` |
| 5 | 處理結果與回報記錄 advisory 編號 | 同上 | `b66a199` |
| 6 | 重新審查時由主 session 把原始內容寫進給 reviewer 的指示 | 同上 | `b66a199` |
| 7 | implementer 修正或發現漏洞時不必等指示就遵守保密 | 同上 | `b66a199` |
| 8 | ADR 0003 補上漏洞例外、程式註解，以及 private fork 的做法 | 同上 | `b66a199` |
| 9 | 本機計畫檔同步（AC1–AC11、`gh issue comment`） | 同上 | 計畫檔不在 repo |
