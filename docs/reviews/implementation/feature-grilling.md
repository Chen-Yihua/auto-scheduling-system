# `/feature` 不用 plan mode，標準、高風險先做需求問答：實作審查紀錄

- 規格：[docs/specs/feature-grilling.md](../../specs/feature-grilling.md)
- PR：#67
- 等級：標準
- 輪數：2（第 1 輪 2026-11-09 `db9fc21`；第 2 輪 2026-11-09 `f857624`）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：6 項（第 1 輪 4 項、第 2 輪 2 項）：Specification Defect 1、Implementation Defect 1、Improvement Suggestion 4；Major 1、Minor 1、Info 4
- 開發者決策：2 項（#1、#4）
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-09 `db9fc21` | #1–#4（#1、#2） | ADR 草稿核准前放 scratchpad；`/issue` 第 1 節的提問用文字格式；文字修正的清理暫存對照 PR；「D 項」改成 Context／Frontier，所有等級的修改紀錄寫 C 編號 |
| 2 | 2026-11-09 `f857624` | #5、#6（無） | 第 1 輪 #1–#4 確認已修正；#5、#6 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 核准前「只寫 scratchpad」和「核准前寫 ADR 草稿進 `docs/decisions/`」衝突 | Specification Defect | Major | 是 | 否 | 不用 plan mode 後的核准前寫入範圍 | ADR 草稿核准前寫在 scratchpad，核准後存進 `docs/decisions/`，規格審查傳路徑（需求 1、AC1） | 開發者 | 已修正（`f857624`） |
| 2 | 1 | `/issue` 第 1 節在讀 `/feature` 前的提問沒規定格式 | Implementation Defect | Minor | 是 | 否 | — | `/issue` 第 1 節的提問照 `/feature` 的文字格式（需求 13、AC4） | 主 session | 已修正（`f857624`） |
| 3 | 1 | 文字修正的「清理暫存」找不到可對照的地方 | Improvement Suggestion | Info | 否 | 否 | — | 開發者決定在這個 PR 修：對照 PR 的改動與描述（需求 14、AC16） | 開發者 | 已修正（`f857624`） |
| 4 | 1 | 假設 2 的理由和「修改紀錄的 D 編號只限標準、高風險」不一致 | Improvement Suggestion | Info | 否 | 否 | — | 開發者決定改用 grill-me 的 Context（C 編號）與 Frontier（Q 編號），所有等級共用，修改紀錄一律寫 C 編號（需求 8、12、AC15、AC16） | 開發者 | 已修正（`f857624`） |

| 5 | 2 | Context／Frontier 的定義放在標題寫「標準、高風險」的節裡，輕量與文字修正可能找不到 | Improvement Suggestion | Info | 否 | 否 | — | 開 issue | 主 session | [#68](https://github.com/Chen-Yihua/auto-scheduling-system/issues/68) |
| 6 | 2 | 修改紀錄引用的 C 編號只存在不 commit 的 scratchpad，repo 裡查不到 | Improvement Suggestion | Info | 否 | 否 | — | 開 issue | 主 session | [#69](https://github.com/Chen-Yihua/auto-scheduling-system/issues/69) |

## 問題說明

### #1 不用 plan mode 後的核准前寫入範圍

需求 1 是第 2 輪規格審查後才加的，規定核准前只寫 scratchpad；`/feature` 原有的「核准前寫成 `docs/decisions/` 的 ADR 草稿」在 plan mode 時只會寫在 plan 檔，拿掉 plan mode 後兩條規則直接衝突。依據：`.claude/skills/feature/SKILL.md:20,109`。

### #4 D 編號的範圍

開發者問 D 編號是什麼，認為定義不夠清楚，決定改用 grill-me 的兩個概念：Context（已確認的資訊）與 Frontier（從 Context 推出、下一批要問的問題）。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | ADR 草稿的位置 | 照建議放 scratchpad | 照建議 | 讓核准前不改 repo 對所有等級成立 |
| 3 | 不阻擋的改善要不要在這個 PR 修 | 開 issue／這個 PR 修 | 這個 PR 修 | — |
| 4 | 輕量的修改紀錄要不要寫編號 | (a) 都寫／(b) 只改理由 | 改用 Context／Frontier；Context 編號 C1…、只收開發者確認的資訊、檔案 `<功能>-grill.md` 含 Frontier、Q 連續編號、所有等級共用 | 用 grill-me 確定需求，同時保留 `/feature` 的流程 |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
