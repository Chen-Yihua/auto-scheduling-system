# 文件的落點與交付：實作審查紀錄

- 規格：[docs/specs/issue-69-context-in-repo.md](../../specs/issue-69-context-in-repo.md)
- PR：#71
- 等級：標準
- 輪數：1（第 1 輪 2026-11-09 `e8cf227`）
- 最終結果：仍有阻擋（#1–#3，規格已修改，交給實作）

## 摘要

- 發現：5 項：Specification Defect 2、Missing AC 1、Implementation Defect 1、Improvement Suggestion 1；Minor 4、Info 1
- 開發者決策：4 項（#1、#2、#3、#5）
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-09 `e8cf227` | #1–#5（#1–#4） | 規格新增需求 18–20：PR 編號由 implementer 補、修改既有術語要寫原定義與新定義、舊 scratchpad 不存在時依核准前後處理；規格審查紀錄補齊 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 規格的「PR」編號沒有人能補，補了也會在下一次交付被蓋掉 | Specification Defect | Minor | 是 | 否 | 交付清單覆蓋 repo 端的修改 | implementer 建立 PR 後補編號、commit、push 並回報；主 session 以 PR 分支同步 scratchpad（需求 18、AC18） | 開發者 | 規格已修改，交給實作 |
| 2 | 1 | 刻意修改既有術語時 implementer 會一直停下來 | Specification Defect | Minor | 是 | 否 | — | 交付清單分「新增」與「修改既有定義」，修改寫原定義與新定義，implementer 確認一致才改（需求 19、AC19） | 開發者 | 規格已修改，交給實作 |
| 3 | 1 | 舊 scratchpad 不存在時「從問答重新開始」不涵蓋核准後與輕量 | Missing AC | Minor | 是 | 否 | — | 核准前依等級重新開始；核准後直接複製 PR 分支上的文件（需求 20、AC20） | 開發者 | 規格已修改，交給實作 |
| 4 | 1 | 規格審查紀錄少了「查證紀錄」「已接受的風險」，類型統計不對 | Implementation Defect | Minor | 是 | 否 | — | 主 session 補齊並改正統計 | 主 session | 已修正（`e2c9872`） |
| 5 | 1 | ADR 0009「放棄的做法」的理由是實作者依背景推的 | Improvement Suggestion | Info | 否 | 否 | — | 主 session 對照問答時提出的取捨，理由一致；開發者接受目前版本，不改、不開 issue | 開發者 | 不處理 |

## 問題說明

### #1 交付清單覆蓋 repo 端的修改

規格開頭的「PR：#NN」要等 PR 建立後才有，但主 session 核准後不改產品文件（`.claude/skills/feature/SKILL.md:166`、`:191`），implementer 的規則只有照交付清單放檔案（`.claude/agents/feature-implementer.md:8`）。scratchpad 的規格沒有編號，下一次交付會把 repo 的編號蓋回「（待開）」。這個 PR 的 `f5e6be9` 就是沒有規則依據的補編號。

### #2 修改既有術語

implementer 遇到 `origin/main` 上「同一個名稱不同定義」就停（`.claude/agents/feature-implementer.md:9`），交付清單只列名稱（`.claude/skills/feature/SKILL.md:186`），分不出開發者已確認的修改。

### #3 舊 scratchpad 不存在

`.claude/skills/feature/SKILL.md:295`、`docs/README.md:29` 一律「從需求問答重新開始」，但輕量不做問答，核准後的文件已在 PR 分支。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 規格的 PR 編號由誰補 | implementer 補並回報／核准後改用改動清單交付 | implementer 建立 PR 後補編號、commit、push、回報；主 session 以 PR 分支上已 commit 的版本同步 scratchpad | 避免之後的交付覆蓋 PR 編號 |
| 2 | 修改既有術語的衝突檢查 | — | 交付清單分「新增」與「修改既有定義（開發者已確認）」；修改要寫術語名稱、原定義、新定義；implementer 確認 `origin/main` 的既有定義和原定義一致才改，不一致就停下來回報 | 不讓開發者已確認的修改卡住，也不讓不一致的定義被直接覆蓋 |
| 3 | 舊 scratchpad 不存在 | — | 核准前：標準、高風險從需求問答、輕量從規格草稿重新開始；核准後：確認 PR 分支最新狀態，直接複製規格、術語表、相關 ADR、審查紀錄，不依記憶重新產生，C、Q 從 1 重新編號 | 正式文件以 PR 分支為準 |
| 5 | ADR 0009 的放棄理由 | 修改／不修改 | 接受目前版本，不修改，也不開 issue | — |

## 尚未處理

無。
