# 0001. `/feature` 流程分開提需求、實作與審查的 agent

- 狀態：已採用（審查分類已被 [0005](0005-specification-review.md) 取代）
- 日期：2026-11-02

## 背景

原本 `/feature` 由同一個 agent 寫需求、計畫，再自己實作，只有驗收交給 `acceptance-reviewer`。實際開發工作效率頁面時（PR #10）發現兩個問題：

- 計畫漏掉的情境（載入失敗時頁面是空的），實作時也不會被發現，因為實作的人就是寫計畫的人。
- 驗收發現驗收條件本身有缺漏時，沒有規定要怎麼處理，結果被列成「範圍外」，差點被遺漏。

## 決定

分成三個角色：

- **主 session**：提需求方。寫規格、跟開發者確認、整理審查結果，不寫程式。
- **`feature-implementer`**：只拿到核准的規格，照規格實作、開 PR、等 CI；規格有問題就停下來回報。
- **`acceptance-reviewer`**：只讀。審查實作、測試與規格本身，每項發現標上分類與是否阻擋。

審查結果分成 Implementation Defect、Missing Acceptance Criteria、Test Gap、Improvement Suggestion 四類。Missing AC 一律回到開發者確認；開發者確認前，不能把 agent 推測的行為當成需求，也不能只改程式不改規格。

## 放棄的做法

- **同一個 agent 規劃加實作**（Claude Code 預設的 explore → plan → code）：不用交接、比較快，但規格寫得不完整時不會被發現。
- **審查發現的所有問題都問開發者**：Implementation Defect 已有核准的驗收條件可以判斷，每一項都問會讓開發者花時間在不需要決定的事情上。

## 影響

- 實作 agent 每次都從零讀程式碼，比較慢、比較花 token。
- 規格要寫到「不看討論過程也能照著做」，見 [0002](0002-specs-in-repo.md)。
- agent 和 skill 的定義要合併進 `main` 才會在每個分支上都能用；在只有某個分支才有定義的時候切換分支，agent 會暫時消失。
