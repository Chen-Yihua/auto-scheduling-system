# <功能名稱>：<流程> 實驗紀錄

- 流程：`/feature` | `/feature-grill`
- 等級：輕量 | 標準 | 高風險（ADR 0007 以前的流程沒有等級，寫「無」）
- 實驗類型：探索性 | 比較（另一份：`records/<功能>-<另一個流程>.md`，本次是第 1 次／第 2 次做）
- 起始 commit：`<git rev-parse HEAD>`
- 流程版本：`<git log -1 --format=%h -- .claude>`（skill 與 agent 定義最後一次修改的 commit；不同版本的紀錄不能直接比較）
- 規格：`docs/specs/<功能>.md`
- PR：#NN
- 日期：YYYY-MM-DD

## 指標

| 指標 | 數值 | 怎麼算 |
|---|---|---|
| 需求釐清輪數 | | `/feature-grill`：第 0 節問了幾輪（含第 1 節補問）與總題數，寫成「N 輪 / M 題」。`/feature`：寫規格前問了幾次問題 |
| 人工介入次數 | | 預定的確認點以外，開發者必須出手的次數：回答核准後的規格問題、糾正 agent 方向、補充漏掉的資訊、中斷流程。回答問答輪、回答規格審查的問題、核准規格、決定合併不算 |
| 規格審查發現 | Factual Error N / Specification Defect N / Missing AC N / Improvement N | 核准前 `docs/reviews/specification/<功能>.md` 的發現，依 `docs/reviews/README.md`「分類」計算。用來看 grilling 留給規格審查的有多少 |
| Missing AC | Critical N / Major N / Minor N | 規格核准後才發現的 Missing Acceptance Criteria 與 Specification Defect，依根本原因分類，不看審查當時標的分類；明細列在下面 |
| 核准後的 Factual Error | N | 核准後才發現的規格事實錯誤。這是寫規格時沒查證，不是需求漏問，所以不算進 Missing AC |
| Review 輪數 | 規格審查 N / 實作審查 N | `docs/reviews/specification/<功能>.md` 與 `docs/reviews/implementation/<功能>.md` 的「輪數」 |
| 假設被否決數量 | 核准時：N / M；核准後：N | 核准時：規格「假設」交給開發者核准時，被否決或改寫的條數 / 假設總條數。核准後：之後因為審查或實作而被證明有問題、要修改的假設條數 |
| 需求變更次數 | | 規格核准後，「修改紀錄」的筆數 |
| Token | 主 session：釐清後 … / 結束時 …（output / cache read / cache creation）；subagent：… | 從 transcript 計算，方法見 `/feature-grill`「實驗紀錄」；`/feature` 只算結束時 |
| 開發時間 | 釐清：… / 規格：… / 實作與審查：… / 總計：… | 由各階段結束時記下的時間計算；等開發者回覆的時間包含在內 |

## Missing AC 明細

| # | 缺漏的情境 | 分類 | 嚴重程度 | 發現者（實作回報／審查第 N 輪／開發者／合併後） | 第 0 節有沒有問到 | 處理（這個 PR 補／issue #NN） |
|---|---|---|---|---|---|---|

「第 0 節有沒有問到」用來判斷 grilling 漏在哪裡：沒問到、問了但答案不完整、問了但沒寫進規格、決定在決策樹之外產生、新的決定改變了既有的 D 項卻沒有重新確認。`/feature` 的紀錄寫「不適用」。

## 觀察

- 問答中最有價值的問題（讓需求改變或發現原本沒想到的決定）：
- 多餘或重複的問題：
- 流程卡住或需要調整的地方：
