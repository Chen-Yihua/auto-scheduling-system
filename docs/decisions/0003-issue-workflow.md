# 0003. 用 GitHub Issues 管理待辦，`/issue` 共用 `/feature` 的流程

- 狀態：已採用
- 日期：2026-11-04

## 背景

PR #10 開發時，審查找到的改善建議與原本就有的問題只列在回報裡，由開發者逐項決定要不要開 issue，結果不少項目沒有追蹤。另外，issue 累積後需要整理優先度，也需要能直接針對某個 issue 開發。

## 決定

- **`/issue-triage`**：只整理 issue 的類型、優先度、相依性與處理順序；開發者確認後才加 `priority:*` 標籤，不開始開發。
- **`/issue <N>`**：讀 issue 後照 `/feature` 的流程執行，不另寫一套。bug 用簡化規格（重現步驟＋回歸測試），一樣要開發者核准。PR 描述加 `Closes #N`。
- **不阻擋的審查發現一律自動開 issue**（Improvement Suggestion，包括原本就有的問題，以及不阻擋的 Test Gap），不在當前 PR 順手修。開之前先查重複。
- **暫停的條件**：需求缺漏、未定義的產品行為、涉及安全的 Implementation Defect、重大架構決策，都要問開發者；其他 Implementation Defect 與阻擋的 Test Gap 仍自動交給實作 agent 修。
- **reviewer 維持只讀**。

## 放棄的做法

- **為 issue 另寫一套開發流程**：兩套流程會各自演變、越來越不一致。
- **不阻擋的發現在當前 PR 順手修**：等於擴大範圍，而且這些修改沒有經過規格核准。
- **由開發者逐項決定要不要開 issue**：PR #10 的經驗是容易遺漏；開 issue 的成本低，不需要的可以在 `/issue-triage` 時關掉。
- **讓 reviewer 直接修正**：審查的人自己修，就沒有人審它修的東西。
- **新增 agent 或 hook**：triage 只是讀取與整理，`/issue` 沿用現有的兩個 agent；合併已經有 deny 規則與 main 的 ruleset 擋著。

## 影響

- 每個 PR 可能會開出幾個小 issue，要定期跑 `/issue-triage` 整理。
- issue 會出現 agent 推測的建議；這些建議要經過 `/issue` 的規格核准才算需求。
- 本機 gh 2.45 不能用 `gh issue edit`，改標籤用 `gh api`。
