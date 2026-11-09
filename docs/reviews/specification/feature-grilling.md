# `/feature` 不用 plan mode，標準、高風險先做需求問答：規格審查紀錄

- 規格：[docs/specs/feature-grilling.md](../../specs/feature-grilling.md)
- PR：#67
- 等級：標準
- 輪數：2（第 1 輪 2026-11-09 草稿；第 2 輪 2026-11-09 草稿）
- 最終結果：第 2 輪仍有阻擋，依 `/feature` 第 1 節不再自動審查；開發者決定後修改、核准。第 2 輪後開發者新增 D9（不用 plan mode），相關需求與 AC 未經規格審查，見「未經審查的驗收條件」

## 摘要

- 發現：16 項（第 1 輪 8 項、第 2 輪 8 項）：Specification Defect 7、Missing AC 3、Factual Error 2、Improvement Suggestion 4；Major 3、Minor 9、Info 4
- 開發者決策：3 項（第 1 輪 #2、#3；第 2 輪 #12）；之後 D9 取代了 #3、#12 的決定
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-09 草稿 | #1–#8（#1–#7） | 做過問答時業務規則不寫成假設；中途升級分三種情況；已在 plan mode 時請開發者退出；AC2 改寫；歷史文件從引用檢查排除；背景更正；issue 的建議 AC 當題目問；D 項加「產生階段」 |
| 2 | 2026-11-09 草稿 | #9–#16（#9–#13） | 背景照實驗紀錄的分類；升級限定從輕量或文字修正；文字修正的欄位值；之後開發者決定整個 `/feature` 不用 plan mode（D9），#10、#12 的前提消失 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `/feature`「假設」的寫法和問答的「決定交給開發者」衝突 | Specification Defect | Major | 是 | 否 | — | 做過問答時，業務規則回到決策樹、不寫成假設；「只有影響整體方向才問」限定在輕量（需求 5、AC7） | 主 session（流程規則，依審查建議） | 規格已修改 |
| 2 | 1 | 核准後升級、文字修正中途升級和問答規則的適用範圍衝突 | Specification Defect | Major | 是 | 否 | 中途升級的範圍 | 中途升級分三種情況；文字修正中途升級補做問答（D6） | 開發者 | 規格已修改 |
| 3 | 1 | 叫出 `/feature` 時已在 plan mode，問答無法照做 | Missing AC | Minor | 是 | 否 | plan mode 的提問限制 | 請開發者先退出（D7）；之後被 D9 取代 | 開發者 | 規格已修改 |
| 4 | 1 | AC2「流程和現在一樣」和輕量的改變矛盾 | Specification Defect | Minor | 是 | 否 | — | AC 改寫，列出例外（現 AC3） | 主 session | 規格已修改 |
| 5 | 1 | 引用檢查的 AC 和「不改歷史文件」衝突 | Specification Defect | Minor | 是 | 否 | — | 歷史文件與實驗 README 已結束的節從檢查排除（現 AC14） | 主 session | 規格已修改 |
| 6 | 1 | 背景對實驗紀錄的描述不符 | Factual Error | Minor | 是 | 否 | 背景對實驗紀錄的描述 | 更正（第 2 輪 #9 再修正） | 主 session（依查證依據） | 規格已修改 |
| 7 | 1 | issue 的建議驗收條件不能當成已決定，沒有對應的 AC | Missing AC | Minor | 是 | 否 | — | 在問答中當成附建議答案的題目（需求 7、AC9） | 主 session（流程規則，依審查建議） | 規格已修改 |
| 8 | 1 | 測試對應少了情境；記憶更新沒列待辦；欄位缺「產生階段」 | Improvement Suggestion | Info | 否 | 否 | — | 採用 | 主 session | 規格已修改 |
| 9 | 2 | 背景對 3 項資料處理缺漏的歸因和實驗紀錄不同 | Factual Error | Minor | 是 | 否 | 背景對實驗紀錄的描述 | 照紀錄的分類改寫 | 主 session（依查證依據） | 規格已修改 |
| 10 | 2 | plan mode 中重新問被改變的 D 項，規則要求的文字格式做不到 | Specification Defect | Major | 是 | 否 | plan mode 的提問限制 | 先改成「新增的決定」一節；之後 D9 拿掉 plan mode，問題不存在 | 開發者（D9） | 規格已修改 |
| 11 | 2 | 標準升高風險會重複補做問答 | Specification Defect | Minor | 是 | 否 | 中途升級的範圍 | 限定從輕量或文字修正升級（需求 6、AC8） | 主 session | 規格已修改 |
| 12 | 2 | 已在 plan mode 時只定義了一條分支 | Missing AC | Minor | 是 | 否 | plan mode 的提問限制 | 開發者先選「不退出就在 plan mode 問並註記」（D8）；之後被 D9 取代 | 開發者 | 規格已修改 |
| 13 | 2 | 文字修正沒有「寫進規格的哪裡」「產生階段」可填的值 | Specification Defect | Minor | 是 | 否 | — | 需求 8 補文字修正的欄位值 | 主 session | 規格已修改 |
| 14 | 2 | 已決定事項檔沒跟上規格改版 | Improvement Suggestion | Info | 否 | 否 | — | 核准後更新 scratchpad 的檔案 | 主 session | 已更新 |
| 15 | 2 | AC 沒涵蓋出處授權；測試對應少 `/issue`；第 1 節標題 | Improvement Suggestion | Info | 否 | 否 | — | 採用（AC5、實作計畫） | 主 session | 規格已修改 |
| 16 | 2 | 文字修正中途升級時已改的內容怎麼處理 | Improvement Suggestion | Info | 否 | 否 | — | 已改的內容保留、不再修改（需求 6） | 主 session | 規格已修改 |

## 問題說明

### #2、#11 中途升級的範圍

問答規則原本只適用「做過問答的等級」，但變更可能在寫規格、規格審查、修改中或核准後才升級。第 1 輪分成三種情況，第 2 輪發現「升級成標準或高風險」也涵蓋標準升高風險，會重複問答。依據：`.claude/skills/feature/SKILL.md` 第 1 節「判斷等級」的升級規則與「文字修正的流程」。

### #3、#10、#12 plan mode 的提問限制

plan mode 裡只能用 AskUserQuestion，用不了問答的 ❓／➡️ 文字格式；實驗紀錄也記下這個限制（`docs/experiments/feature-grill/records/staged-tasks-feature-grill.md:56`）。兩輪都在補 plan mode 下的例外規則，開發者最後決定整個 `/feature` 不用 plan mode（D9），例外規則全部移除。

### #6、#9 背景對實驗紀錄的描述

背景把紀錄裡範圍有限的觀察寫成一般結論，第 2 輪改成照紀錄第 54 行的 Missing AC 分類。依據：`docs/experiments/feature-grill/records/staged-tasks-feature-grill.md:32-39,51,54`。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 2 | 文字修正中途升級要不要補做問答 | 補做／不補做 | 補做（D6） | 還沒有規格，等同新的標準或高風險變更 |
| 3 | 叫出時已在 plan mode | 請開發者退出／用 AskUserQuestion 問 | 請開發者退出（D7，之後被 D9 取代） | 問答格式完整 |
| 12 | 開發者不退出 plan mode | 用 AskUserQuestion 問／停下來等 | 在 plan mode 問並註記（D8，之後被 D9 取代） | — |
| — | 核准前的 ExitPlanMode 被開發者拒絕 | 整個 `/feature` 不用 plan mode／只有問答不用 | 整個 `/feature` 不用 plan mode，問答和 grilling 一樣（D9） | 避開 plan mode 只能用選單提問的限制 |

## 未經審查的驗收條件

D9 是第 2 輪之後的決定，下列內容沒有經過規格審查，由實作審查補做事實查證、一致性與缺漏檢查（開發者核准時同意）：需求 1、4、9、11；AC1、AC3、AC4、AC11、AC13、AC14。

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
