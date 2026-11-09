# 文件的落點與交付：實作審查紀錄

- 規格：[docs/specs/issue-69-context-in-repo.md](../../specs/issue-69-context-in-repo.md)
- PR：#71
- 等級：標準
- 輪數：4（第 1 輪 2026-11-09 `e8cf227`；第 2 輪 2026-11-09 `42ba500`；第 3 輪 2026-11-09 `09efbcb`；第 4 輪 2026-11-09 `17ebd7f`，只審第 3 輪 #12 的修正）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：14 項（第 1 輪 5 項、第 2 輪 5 項、第 3 輪 3 項、第 4 輪 1 項）：Specification Defect 4、Missing AC 4、Implementation Defect 1、Improvement Suggestion 5；Minor 11、Info 3
- 開發者決策：10 項（#1、#2、#3、#5–#8、#11–#13）
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-09 `e8cf227` | #1–#5（#1–#4） | 規格新增需求 18–20：PR 編號由 implementer 補、修改既有術語要寫原定義與新定義、舊 scratchpad 不存在時依核准前後處理；規格審查紀錄補齊 |
| 2 | 2026-11-09 `42ba500` | #6–#10（#6–#8） | 第 1 輪 #1–#4 確認已修正；規格加「更新本 PR 的術語」、PR 還沒建立與文字修正的接續；AC3、AC14 條文對齊；#9 開 issue；#10 紀錄格式補齊 |
| 3 | 2026-11-09 `09efbcb` | #11–#13（#11、#12） | 第 2 輪 #6、#7 確認已修正，#8 部分修正；同一根本原因連續 3 輪阻擋，停止自動修改；開發者決定 #11、#13 開 [#73](https://github.com/Chen-Yihua/auto-scheduling-system/issues/73)，#12 在這個 PR 修 |
| 4 | 2026-11-09 `17ebd7f` | #14（無） | 第 3 輪 #12 確認已修正；#73 在規格「不做」、修改紀錄、PR 描述都有寫；#14 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 規格的「PR」編號沒有人能補，補了也會在下一次交付被蓋掉 | Specification Defect | Minor | 是 | 否 | 交付清單覆蓋 repo 端的修改 | implementer 建立 PR 後補編號、commit、push 並回報；主 session 以 PR 分支同步 scratchpad（需求 18、AC18） | 開發者 | 已修正（`42ba500`） |
| 2 | 1 | 刻意修改既有術語時 implementer 會一直停下來 | Specification Defect | Minor | 是 | 否 | 修改既有術語 | 交付清單分「新增」與「修改既有定義」，修改寫原定義與新定義，implementer 確認一致才改（需求 19、AC19） | 開發者 | 已修正（`42ba500`） |
| 3 | 1 | 舊 scratchpad 不存在時「從問答重新開始」不涵蓋核准後與輕量 | Missing AC | Minor | 是 | 否 | 舊 scratchpad 不存在時的接續 | 核准前依等級重新開始；核准後直接複製 PR 分支上的文件（需求 20、AC20） | 開發者 | 已修正（`42ba500`） |
| 4 | 1 | 規格審查紀錄少了「查證紀錄」「已接受的風險」，類型統計不對 | Implementation Defect | Minor | 是 | 否 | — | 主 session 補齊並改正統計 | 主 session | 已修正（`e2c9872`） |
| 5 | 1 | ADR 0009「放棄的做法」的理由是實作者依背景推的 | Improvement Suggestion | Info | 否 | 否 | — | 主 session 對照問答時提出的取捨，理由一致；開發者接受目前版本，不改、不開 issue | 開發者 | 不處理 |

| 6 | 2 | 核准後但 PR 還沒建立時舊 scratchpad 不存在，以及文字修正的接續，都沒有定義 | Missing AC | Minor | 是 | 否 | 舊 scratchpad 不存在時的接續 | 先找本機與 `origin` 的分支和工作目錄裡的規格，找不到請開發者選擇重寫或取消；文字修正依核准前後處理（需求 20、AC20） | 開發者 | 已修正（`09efbcb`） |
| 7 | 2 | 修改這個 PR 先前交付、`origin/main` 還沒有的術語，兩種標法都不適用 | Missing AC | Minor | 是 | 否 | 修改既有術語 | 新增「更新本 PR 的術語」，確認 PR 分支上的上一版一致才取代（需求 19、AC19） | 開發者 | 已修正（`09efbcb`） |
| 8 | 2 | AC3、AC14 的條文沒有隨 AC19、AC20 收窄；實作計畫沒列需求 18–20 | Specification Defect | Minor | 是 | 否 | 核准後修改的影響檢查 | AC3、AC14 對齊、實作計畫補上、修改紀錄補一列 | 開發者 | 部分修正（`09efbcb`）；測試對應見 #12 |
| 9 | 2 | 核准後接續時複製到 scratchpad 的術語表、ADR、審查紀錄的檔名與內容沒有寫 | Improvement Suggestion | Minor | 否 | 否 | — | 開 issue | 主 session | [#72](https://github.com/Chen-Yihua/auto-scheduling-system/issues/72) |
| 10 | 2 | 實作審查紀錄：阻擋項目 #2、#3 沒有根本原因名稱，#4 沒有問題說明 | Improvement Suggestion | Info | 否 | 否 | — | 主 session 補上根本原因名稱與 #4 的問題說明 | 主 session | 已修正（本紀錄） |
| 11 | 3 | 核准後、規格審查紀錄 commit 前舊 scratchpad 不見，紀錄草稿找不回來 | Missing AC | Minor | 是 | 否 | 舊 scratchpad 不存在時的接續 | 連續 3 輪阻擋，停止自動修改；依 ADR 0003 的先例另開 issue，這個 PR 不處理 | 開發者 | [#73](https://github.com/Chen-Yihua/auto-scheduling-system/issues/73) |
| 12 | 3 | 「測試對應」沒有跟著 AC19、AC20 的新情況更新 | Specification Defect | Minor | 是 | 否 | 核准後修改的影響檢查 | 測試對應 AC18–AC20 列補上新情況、修改紀錄補記 | 開發者 | 已修正（`17ebd7f`） |
| 13 | 3 | 文字修正核准後接續時，還沒套用的項目會從改動清單消失 | Improvement Suggestion | Minor | 否 | 否 | — | 和 #11 同一個 issue | 開發者 | [#73](https://github.com/Chen-Yihua/auto-scheduling-system/issues/73) |
| 14 | 4 | AC19 條文少了「更新本 PR 的術語也要對照 `origin/main`」（需求 19、實作、測試對應都有） | Improvement Suggestion | Info | 否 | 否 | — | 開 issue | 主 session | [#74](https://github.com/Chen-Yihua/auto-scheduling-system/issues/74) |

## 問題說明

### #1 交付清單覆蓋 repo 端的修改

規格開頭的「PR：#NN」要等 PR 建立後才有，但主 session 核准後不改產品文件（`.claude/skills/feature/SKILL.md:166`、`:191`），implementer 的規則只有照交付清單放檔案（`.claude/agents/feature-implementer.md:8`）。scratchpad 的規格沒有編號，下一次交付會把 repo 的編號蓋回「（待開）」。這個 PR 的 `f5e6be9` 就是沒有規則依據的補編號。

### #2、#7 修改既有術語

implementer 遇到 `origin/main` 上「同一個名稱不同定義」就停（`.claude/agents/feature-implementer.md:9`），交付清單只列名稱（`.claude/skills/feature/SKILL.md:186`），分不出開發者已確認的修改。第 2 輪：這個 PR 先前交付、`origin/main` 還沒有的術語被修改時，「新增」與「修改既有定義」都對不上，可能繞成迴圈或被覆蓋。

### #4 規格審查紀錄不符合紀錄檔格式

`docs/reviews/specification/issue-69-context-in-repo.md` 少了最後一輪的「查證紀錄」「已接受的風險」，「尚未處理」只有表頭，摘要的類型統計和表格不一致（`docs/reviews/README.md`「紀錄檔格式」）。

### #3、#6 舊 scratchpad 不存在

`.claude/skills/feature/SKILL.md:295`、`docs/README.md:29` 一律「從需求問答重新開始」，但輕量不做問答，核准後的文件已在 PR 分支。第 2 輪：規格核准後到 PR 建立前，PR 分支可能不存在；文字修正不經過 implementer，也沒有 PR 分支上的規格。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 規格的 PR 編號由誰補 | implementer 補並回報／核准後改用改動清單交付 | implementer 建立 PR 後補編號、commit、push、回報；主 session 以 PR 分支上已 commit 的版本同步 scratchpad | 避免之後的交付覆蓋 PR 編號 |
| 2 | 修改既有術語的衝突檢查 | — | 交付清單分「新增」與「修改既有定義（開發者已確認）」；修改要寫術語名稱、原定義、新定義；implementer 確認 `origin/main` 的既有定義和原定義一致才改，不一致就停下來回報 | 不讓開發者已確認的修改卡住，也不讓不一致的定義被直接覆蓋 |
| 3 | 舊 scratchpad 不存在 | — | 核准前：標準、高風險從需求問答、輕量從規格草稿重新開始；核准後：確認 PR 分支最新狀態，直接複製規格、術語表、相關 ADR、審查紀錄，不依記憶重新產生，C、Q 從 1 重新編號 | 正式文件以 PR 分支為準 |
| 5 | ADR 0009 的放棄理由 | 修改／不修改 | 接受目前版本，不修改，也不開 issue | — |
| 6 | 核准後但 PR 還沒建立時舊 scratchpad 不存在 | 依建議補規則 | 採納 | — |
| 7 | 修改這個 PR 先前交付的術語 | 依建議加「更新本 PR 的術語」 | 採納 | — |
| 8 | AC3、AC14 條文對齊 | 依建議修改 | 採納 | AC 表要能單獨驗收 |
| 11、13 | scratchpad 遺失的接續連續 3 輪阻擋 | (a) 這個 PR 加通用規則／(b) 另開 issue | (b)，#13 併進同一個 issue | 和 ADR 0003 的先例相同：每補一層規則就出現新的邊界情況，等實際遇到再一次設計 |
| 12 | 測試對應沒有更新 | 這個 PR 修／另開 issue | 這個 PR 修 | 測試對應要能單獨驗收 |

## 尚未處理

無。
