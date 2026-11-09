# 0008. 標準、高風險寫規格前先做需求問答，`/feature` 不用 plan mode

- 狀態：已採用
- 日期：2026-11-09

## 背景

`/feature-grill`（[實驗](../experiments/feature-grill/README.md)）在 `/feature` 寫規格前多一節 grilling 問答：把需求畫成決策樹，每一輪問完所有前提已定的問題，決定編成 D 項。實驗原本規定結束、開發者看過結果前不整合進正式流程，也預定要和 `/feature` 做比較實驗。

證據只有一筆探索性紀錄（`docs/experiments/feature-grill/records/staged-tasks-feature-grill.md`），沒有比較實驗，所以不能說明問答是否降低了 Missing AC。這筆紀錄看得到的是：

- 問答帶出了會大幅改變範圍的決定，例如「階段之間強制先後順序」；刪除與失敗處理的決定問得很完整。
- 8 項 Missing AC 中，3 項來自在 plan mode 中補問、沒有回到決策樹的決定，1 項是兩個決定之間的交互作用沒有追問，1 項是 agent 自行推導的假設，3 項沒問到或答案不完整。
- plan mode 只能用選單（AskUserQuestion）提問，所以寫規格時的補問沒照問答的文字格式。

`/feature` 原本在 plan mode 寫規格、用 ExitPlanMode 請開發者核准。把問答併進來時，規格審查連續兩輪都在補「plan mode 中怎麼問」的例外規則（`docs/reviews/specification/feature-grilling.md` #3、#10、#12）。

開發者在 2026-11-09 決定提前結束實驗，把問答併進 `/feature`；同時決定整個 `/feature` 不再使用 plan mode。

## 決定

- 標準、高風險在判斷等級之後、寫規格之前做需求問答，開發者確認 D 項後才寫規格草稿；輕量、文字修正不做。規則只寫在 `/feature` 第 1 節「需求問答」，`/issue` 照同一個等級規則。
- D 項確認之後，任何階段出現需要開發者決定的事，都編成新的 D 項、做影響檢查，既有 D 項被改變時重新問開發者（「新的決定一律回到決策樹」）。
- `/feature`、`/issue` 不用 plan mode，也不用 ExitPlanMode。規格草稿（文字修正是改動清單）寫在 scratchpad 的 `<功能>-spec.md`；核准前只寫 scratchpad，不改 repo、不開分支；開發者明確表示核准才算核准。
- 所有等級、所有階段向開發者提問，都用問答的 ❓／➡️ 文字格式，不用 AskUserQuestion。
- 已決定事項所有等級都用 D 編號與同一組欄位，欄位只定義在 `/feature`。
- 刪除 `/feature-grill`。實驗的紀錄規則（起始 commit、時間、token、實驗紀錄檔）不搬進 `/feature`。

## 放棄的做法

- **所有等級都做問答**：輕量、文字修正的範圍小，問答的成本大於收益。
- **繼續實驗，等比較實驗完成再整合**：開發者決定先把問答用在正式流程；代價是之後沒有比較基準，見「影響」。
- **保留兩個入口（`/feature` 與 `/feature-grill`）**：和 [0003](0003-issue-workflow.md)、[0007](0007-process-depth-by-risk.md) 不拆 `/issue` 的理由相同，兩套會各自演變；`/feature-grill` 靠一張差異表疊在 `/feature` 上，`/feature` 一改就要同步檢查。
- **保留 plan mode，只在問答時退出**：問答之後的寫規格、規格審查仍在 plan mode，補問只能用選單；規格審查兩輪都在補這個例外，規則越來越多（`docs/reviews/specification/feature-grilling.md` #3、#10、#12）。

## 影響

- 「核准前不改 repo」原本由 plan mode 的工具限制保證，現在只靠流程規則維持。
- 不再有 plan 檔；草稿、已決定事項、審查報告原文都在 scratchpad。開發者在 plan mode 中叫出流程時，要先退出 plan mode。
- 標準、高風險在寫規格前多了問答的時間。
- [0007](0007-process-depth-by-risk.md) 的「文字修正由主 session 在 plan mode 列出改動」由本 ADR 取代：改成在 scratchpad 寫改動清單、以文字核准；0007 的其他決定照舊。
- 問答的效果沒有比較實驗的數據；之後要評估時，只能用導入後的紀錄（規格修改紀錄、審查紀錄的 Missing AC）和導入前比較，兩者的流程版本不同。
- 實驗的 TEMPLATE 與 records 引用的 `/feature-grill` 規則，從 commit `23c56c9` 的 `.claude/skills/feature-grill/SKILL.md` 找。
