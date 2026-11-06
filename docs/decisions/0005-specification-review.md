# 0005. 規格核准前加入規格審查，審查分類依根本原因區分

- 狀態：已採用
- 日期：2026-11-06

## 背景

[0001](0001-separate-feature-roles.md) 只在實作後審查一次，規格本身的問題也由 `acceptance-reviewer` 一起找。階段任務（PR #31）第 1 輪審查的 8 項發現裡，有 6 項是規格的問題：

- 寫錯現有行為（AC37 寫 401，現有的登入驗證回 403）。
- 驗收條件互相矛盾（AC26 和 AC23），或假設撐不住驗收條件（把階段編號存在子任務上，同時操作時排程的先後限制會失效）。
- 兩個決定交會的情境沒有定義（插入任意位置 × AI 推斷優先序的調整）。

實作 agent 第一次讀規格時就先指出了其中 5 項，可見寫程式之前就看得出來。但它們到實作後才處理，多了 2 次重新實作，資料模型也在 PR 中途改成 [0004](0004-subtask-order-on-parent.md)。

另外，原本的四種分類裡，Missing Acceptance Criteria 同時包含「事實寫錯」「規格矛盾」「真的漏了」三種情況；Improvement Suggestion 的定義太寬，有兩項會讓既有驗收條件失效的發現被歸成 Improvement，由開發者手動改成在 PR 裡修。

## 決定

- 新增 `specification-reviewer` agent：規格交給開發者核准前，查證規格裡的事實、檢查一致性與缺漏，不審查實作。它的查證紀錄和「已接受的風險」交給實作後的 `acceptance-reviewer`，後者不再逐項重做情境涵蓋與事實查證，只回報實作中才看得出來的規格問題。
- 審查分類改成依根本原因：Factual Error、Specification Defect、Missing Acceptance Criteria、Implementation Defect、Test Gap、Improvement Suggestion，定義只寫在 `docs/reviews/README.md`。會讓某條驗收條件在某個條件下不成立的發現，不能歸成 Improvement Suggestion。
- 涉及產品行為、權限、安全性、資料處理或架構的決定，主 session 和 reviewer 可以附建議與理由，但開發者要選定選項，只回「是」不算。
- 流程已經停下來等開發者決定時，不阻擋的發現在同一則訊息裡一起問，回答後才開 issue。

## 放棄的做法

- **讓 `acceptance-reviewer` 加一個「規格模式」**：規格審查的時機、輸入（沒有 diff）、可用的分類都不同，放在同一份指示裡，容易在審查規格時去找實作，或在審查實作時重做規格檢查。
- **另外做 `/spec-review` skill 或用 hook 強制執行**：規格審查只會從 `/feature` 內部呼叫，用 agent 就夠；這次的問題是規則沒寫到，不是規則被違反。
- **bug 簡化格式也做規格審查**：規格很短，而且回歸測試要求改程式前先失敗，已經驗證了重現步驟。

## 影響

- 每個功能多一次 agent 執行（約一次實作後審查的成本），換來在實作前處理規格問題。
- 規格審查的紀錄存成 `docs/reviews/<功能>-spec-round<N>.md`。
- 規格審查之後才導入的功能，Missing AC 的數量不能直接和導入前的功能比較。
- 本 ADR 取代 0001「決定」一節裡的四種審查分類；0001 的三個角色分工照舊。
