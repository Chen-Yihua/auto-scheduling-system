# 架構決策紀錄（ADR）

記錄「之後的人會想問為什麼不用 X」的決定。一個決定一個檔案，檔名 `NNNN-<簡短名稱>.md`，編號遞增、不重複使用。

決定被推翻時不要刪掉舊檔：新增一份新的 ADR，並把舊檔的狀態改成「已被 NNNN 取代」；只推翻一部分時，在狀態後面用括號寫哪一部分被哪一份取代。舊檔的背景、決定、放棄的做法保留原樣，它記錄的是當時的判斷。

核准前只維護草稿資料夾（`.drafts/`）裡的一份工作草稿（ADR 0008、ADR 0014），核准後才轉成正式文件 commit。

## 格式

```markdown
# NNNN. 標題

- 狀態：已採用 | 已被 NNNN 取代
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
| [0001](0001-separate-feature-roles.md) | `/feature` 流程分開提需求、實作與審查的 agent | 已採用（審查分類已被 0005 取代；文字修正的例外見 0007） |
| [0002](0002-specs-in-repo.md) | 功能規格放進 repo，和程式碼同一個 PR | 已採用（文字修正不寫規格的例外見 0007；快速路徑的規格只寫在 PR 描述，見 0018） |
| [0003](0003-issue-workflow.md) | 用 GitHub Issues 管理待辦，`/issue` 共用 `/feature` 的流程 | 已採用（bug 簡化規格已被 0006 取代；審查發現自動開 issue、漏洞一律阻擋與安全改善分開分類、審查輪數依根本原因計算、暫停的條件裡的漏洞與「安全」兩項，已被 [0017](0017-review-findings-conventional-labels.md) 取代） |
| [0004](0004-subtask-order-on-parent.md) | 子任務的階段順序存在主任務上 | 已採用 |
| [0005](0005-specification-review.md) | 規格核准前加入規格審查，審查分類依根本原因區分 | 已採用（bug 不審查的例外已被 0006 取代；紀錄檔位置已改，見 0005 狀態；規格審查紀錄的存放位置已被 [0015](0015-review-results-in-pr-comments.md) 取代；審查分類依根本原因、不阻擋的發現在同一則訊息裡一起問後才開 issue，已被 [0017](0017-review-findings-conventional-labels.md) 取代；所有等級都做規格審查，已被 [0019](0019-simplify-spec-review-and-ac-derivation.md) 取代） |
| [0006](0006-bugs-use-full-spec.md) | bug 也用完整規格格式並做規格審查 | 已採用（文字修正與輕量等級的例外見 0007；快速路徑的 bug 用短版規格、不做規格審查，已被 0018 取代；bug 的規格一律做規格審查，已被 [0019](0019-simplify-spec-review-and-ac-derivation.md) 取代） |
| [0007](0007-process-depth-by-risk.md) | 依變更碰到的範圍決定規格與審查的深度 | 已採用（文字修正在 plan mode 列改動已被 0008 取代；輕量與標準分級、輕量只審 1 輪與「未經審查」已被 0012 取代；「放棄的做法」裡的輕量不做規格審查，快速路徑的例外見 0018） |
| [0008](0008-grilling-without-plan-mode.md) | 標準、高風險寫規格前先做需求問答，`/feature` 不用 plan mode | 已採用（修改紀錄寫 C 編號已被 0009 取代；Context／Frontier 與 C、Q 編號的記錄方式，以及輕量不做問答，已被 0012 取代；核准前只寫 scratchpad 已被 [0014](0014-drafts-folder.md) 取代；開發者確認 Context 後才寫規格草稿，已被 [0019](0019-simplify-spec-review-and-ac-derivation.md) 取代） |
| [0009](0009-docs-delivery-and-glossary.md) | 修改紀錄寫決定與落點、引進術語表、產品文件照交付清單由 implementer commit | 已採用（C、Q 編號規則已被 0012 取代；不引用 scratchpad 的原則沿用；接續時把暫存檔複製到新的 scratchpad 已被 [0014](0014-drafts-folder.md) 取代；審查紀錄由主 session commit 的分工已被 [0015](0015-review-results-in-pr-comments.md) 取代；交付清單的「更新本 PR 的術語」分類，已被 [0019](0019-simplify-spec-review-and-ac-derivation.md) 取代） |
| [0010](0010-scratchpad-loss-recovery.md) | scratchpad 遺失時以暫存產物為單位恢復，審查不逐一要求特定案例 | 已採用（暫存產物表的位置已移到 `feature/references/resume.md`，見 0012；遺失的對象（scratchpad）已被 [0014](0014-drafts-folder.md) 取代；審查豁免的「並阻擋」與「三種實際風險仍然阻擋」已被 [0017](0017-review-findings-conventional-labels.md) 取代） |
| [0011](0011-api-error-status-codes.md) | API 錯誤回應：狀態碼表示類別，error_code 表示原因 | 已採用 |
| [0012](0012-simplify-process-levels.md) | 簡化等級、審查分流與決定記錄，`/feature` 拆成階段 skill | 已採用（決定 3 審查發現的去處只有四種、只有涉及產品行為等才問開發者，已被 [0017](0017-review-findings-conventional-labels.md) 取代；決定 2 的一般等級，快速路徑的例外見 0018；決定 4 規格審查的次數，已被 [0019](0019-simplify-spec-review-and-ac-derivation.md) 取代） |
| [0013](0013-scheduled-sync-trigger.md) | 外部平台定時同步由 GitHub Actions 觸發 | 已採用 |
| [0014](0014-drafts-folder.md) | 核准前的草稿放在 repo 內被 git 排除的 `.drafts/` | 已採用 |
| [0015](0015-review-results-in-pr-comments.md) | 審查結果改留在 PR 留言 | 已採用（決定 1 的留言時機與補充留言，已被 [0019](0019-simplify-spec-review-and-ac-derivation.md) 取代） |
| [0016](0016-path-filtered-ci.md) | CI 依改到的檔案決定要跑的測試與部署 | 已採用 |
| [0017](0017-review-findings-conventional-labels.md) | 審查發現改用 Conventional Comments 標籤 | 已採用 |
| [0018](0018-fast-path.md) | 需求清楚的改動走快速路徑 | 已採用 |
| [0019](0019-simplify-spec-review-and-ac-derivation.md) | 規格審查依需要才做、驗收條件依需求推導、精簡審查留言 | 已採用 |
