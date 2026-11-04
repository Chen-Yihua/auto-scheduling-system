# 0003. 用 GitHub Issues 管理待辦，`/issue` 共用 `/feature` 的流程

- 狀態：已採用
- 日期：2026-11-04

## 背景

PR #10 開發時，審查找到的改善建議與原本就有的問題只列在回報裡，由開發者逐項決定要不要開 issue，結果不少項目沒有追蹤。另外，issue 累積後需要整理優先度，也需要能直接針對某個 issue 開發。

## 決定

- **`/issue-triage`**：只整理 issue 的類型、優先度、相依性與處理順序；開發者確認後才加 `priority:*` 標籤，不開始開發。
- **`/issue <N>`**：讀 issue 後照 `/feature` 的流程執行，不另寫一套。bug 用簡化規格（重現步驟＋回歸測試），一樣要開發者核准。PR 描述加 `Closes #N`。
- **不阻擋的審查發現自動開 issue**（Improvement Suggestion，包括原本就有的問題，以及不阻擋的 Test Gap；可被利用的漏洞除外，見下一點），不在當前 PR 順手修；開發者明確要求時才在當前 PR 處理。開之前先查重複。
- **只定義安全邊界，不定義漏洞修復流程**：repo 是公開的。實際漏洞一律阻擋、暫停並回報開發者；開發者決定前，細節不出現在公開的 issue、PR 描述、commit、程式註解、規格檔、測試名稱與 docstring、`docs/reviews/`，也不把修正推送到公開 repo；可以提出建立 private security advisory，經開發者確認才建立。安全改善建議（不是漏洞）分開分類，照一般流程處理。
- **審查輪數依根本原因計算**：同一個根本原因連續 3 輪仍有阻擋就停下來問開發者，不因改了不同的驗收條件或規格版本而重新計算。
- **暫停的條件**：實際漏洞（一律阻擋）、需求缺漏、未定義的產品行為、標成「安全」的 Implementation Defect、重大架構決策，都要問開發者；其他 Implementation Defect 與阻擋的 Test Gap 仍自動交給實作 agent 修。
- **reviewer 維持只讀**。

## 放棄的做法

- **為 issue 另寫一套開發流程**：兩套流程會各自演變、越來越不一致。
- **不阻擋的發現在當前 PR 順手修**（開發者明確要求的除外）：等於擴大範圍，而且這些修改沒有經過規格核准。
- **由開發者逐項決定要不要開 issue**：PR #10 的經驗是容易遺漏；開 issue 的成本低，不需要的會在 `/issue-triage` 時標出來，由開發者關閉。
- **安全發現也開公開 issue**：漏洞會在修好之前公開。
- **在本 PR 設計完整的漏洞修復流程（temporary private fork、ruleset bypass、私有 CI、發布）**：PR #18 審查時每補一層規則就出現新的邊界情況，而且需要實際操作才能驗證。等第一次真的遇到 main 的漏洞時，再開獨立的 issue 設計與測試。
- **審查輪數依規格版本計算**：PR #18 每輪都改了驗收條件，照版本算會一直重置，同一個問題審了 4 輪才停下來。
- **讓 reviewer 直接修正**：審查的人自己修，就沒有人審它修的東西。
- **新增 agent 或 hook**：triage 只是讀取與整理，`/issue` 沿用現有的兩個 agent；合併靠 `.claude/settings.json` 的 deny 規則（`gh pr merge`、`gh api *merge*`、`gh api *Merge*`）擋下；main 的 ruleset 要求 PR 與 CI 通過、不要求核准，擋得住直接 push 到 main，但不能單獨防止 agent 透過 PR 合併。

## 影響

- 每個 PR 可能會開出幾個小 issue，要定期跑 `/issue-triage` 整理。
- issue 會出現 agent 推測的建議；這些建議要經過 `/issue` 的規格核准才算需求。
- 本機 gh 2.45 不能用 `gh issue edit`，改標籤用 `gh api`。
