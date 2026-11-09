# scratchpad 遺失時以暫存產物為單位的通用恢復規則：規格審查紀錄

- 規格：[docs/specs/issue-73-scratchpad-loss.md](../../specs/issue-73-scratchpad-loss.md)
- PR：#75
- 等級：標準
- 輪數：2（第 1 輪 2026-11-09 `aedbdbf`；第 2 輪 2026-11-09 `aedbdbf`；兩輪都審 scratchpad 的規格草稿，commit 是當時的 main）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：16 項（第 1 輪 9 項、第 2 輪 7 項）：Specification Defect 6、Missing AC 1、Improvement Suggestion 9；Major 3、Minor 8、Info 5
- 開發者決策：4 項（#1–#2、#3、#4、#16）
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-09 `aedbdbf` | #1–#9（#1–#4、#6） | 恢復步驟加「告知依據來源、確認還沒交付的項目」；被豁免的情況寫在「已接受的風險」，`docs/reviews/README.md` 加例外與「已接受的風險」；規格審查紀錄不補時的交接；術語、ADR 要修改時才從 PR 分支複製；單一來源擴大到所有暫存檔列舉；ADR 0009 不改 |
| 2 | 2026-11-09 `aedbdbf` | #10–#16（#10、#11） | 重跑審查的發現分核准前後；補 `Closes #72` 與「影響」；清單改以第 2 步找到的正式版本為準、補核准後的產生步驟、術語只複製要改的條目；第 5 步照清單該列的選項；刪除假設 1；`docs/README.md`「取消」也改成指向 `/feature` |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 正式版本比遺失的暫存檔舊時，已核准但還沒交付的修改會悄悄消失 | Specification Defect | Major | 是 | 否 | 恢復時沒有確認還沒交付的項目 | 用正式版本或部分成果時，告知依據的分支、commit 與未 commit 的改動，請開發者確認還沒交付的項目，沒有依據的重新核准（需求 1 第 4 步、AC6） | 開發者 | 規格已修改 |
| 2 | 1 | 部分成果的項目清單本身遺失時，看不到的項目會消失 | Missing AC | Major | 是 | 否 | 恢復時沒有確認還沒交付的項目 | 和 #1 同一步：項目清單遺失時由開發者補上（需求 1 第 4 步、AC6） | 開發者 | 規格已修改 |
| 3 | 1 | 審查豁免和 `docs/reviews/README.md`「分類」的一律阻擋規則矛盾 | Specification Defect | Major | 是 | 否 | — | 被豁免的情況不列成發現，寫在報告的「已接受的風險」；「分類」加例外指向 `/feature`；`acceptance-reviewer` 檢查表與實作審查紀錄格式加「已接受的風險」（需求 6、AC11） | 開發者 | 規格已修改 |
| 4 | 1 | 規格審查紀錄不補時，和交給 `acceptance-reviewer` 前要確認已 commit 矛盾 | Specification Defect | Minor | 是 | 否 | — | 交接時寫明沒有紀錄與原因、跳過確認；PR 描述記錄遺失與不補的決定，實作審查紀錄寫在「已接受的風險」，「尚未處理」若列出註明已決定不補（需求 1 第 6 步、需求 4、AC7、AC8） | 開發者 | 規格已修改 |
| 5 | 1 | ADR 不複製，和核准後修改 ADR 要從 scratchpad 交付衝突 | Improvement Suggestion | Minor | 否 | 否 | — | 要修改時才從 PR 分支複製到 scratchpad 再改（需求 2、AC3） | 主 session | 規格已修改 |
| 6 | 1 | 單一來源不完整：`docs/README.md:23`、`/feature` 的括號仍各自列舉暫存檔 | Specification Defect | Minor | 是 | 否 | — | 所有列舉都改成指向 `/feature` 第 4 節的清單（需求 7、AC12） | 主 session | 規格已修改 |
| 7 | 1 | Context 的產生步驟漏了輕量與文字修正 | Improvement Suggestion | Minor | 否 | 否 | — | 分等級寫出（需求 2） | 主 session | 規格已修改 |
| 8 | 1 | 重跑審查的發現怎麼處理、算不算一輪沒有寫 | Improvement Suggestion | Info | 否 | 否 | — | 加處理方式，重跑同一輪不另計輪數（需求 2、AC9）；第 2 輪 #10 再分核准前後 | 主 session | 規格已修改 |
| 9 | 1 | ADR 0009 沒寫遺失時的處理，狀態行可能不用改 | Improvement Suggestion | Info | 否 | 否 | — | 不改 ADR 0009，ADR 0010 背景寫明是補充（需求 8、AC13） | 主 session | 規格已修改 |
| 10 | 2 | 核准前重跑規格審查時，發現被指向第 3 節，和第 1 節「規格審查」的處理表矛盾 | Specification Defect | Minor | 是 | 否 | 重跑審查的處理 | 核准前照第 1 節「規格審查」的處理表，核准後照第 3 節；清單改成「審目前的規格」（需求 2、AC9） | 主 session | 規格已修改 |
| 11 | 2 | 已確認的決定沒有完整寫進規格：PR 描述加 `Closes #72`、不補時記錄影響 | Specification Defect | Minor | 是 | 否 | — | 實作計畫與 AC15 加兩行 `Closes`；需求 1 第 6 步與 AC7 加「影響」 | 主 session | 規格已修改 |
| 12 | 2 | 清單只寫「以 PR 分支為準」，和第 2 步的四個位置不一致；術語表複製的內容沒寫 | Improvement Suggestion | Minor | 否 | 否 | — | 改成「以正式版本（第 2 步找到的位置）為準」；術語只複製要修改的條目、不含檔頭（需求 2、AC3） | 主 session | 規格已修改 |
| 13 | 2 | 清單「產生它的步驟」只寫核准前的步驟 | Improvement Suggestion | Minor | 否 | 否 | — | 術語、ADR、規格、Context 補上核准後的產生點（需求 2） | 主 session | 規格已修改 |
| 14 | 2 | 第 5 步的「重做或不補」和清單各列的選項重複而且不同 | Improvement Suggestion | Info | 否 | 否 | — | 第 5 步改成照清單該列的選項，清單沒寫的選重做或不補（需求 1） | 主 session | 規格已修改 |
| 15 | 2 | 假設 1 其實是開發者的決定 | Improvement Suggestion | Info | 否 | 否 | — | 刪除，需求 6 已寫 | 主 session | 規格已修改 |
| 16 | 2 | `docs/README.md` 的「取消」仍抄了一份 `/feature` 的規則 | Improvement Suggestion | Info | 否 | 否 | — | 一起改成一句說明並指向 `/feature` 第 4 節「取消」（需求 7、AC12） | 開發者 | 規格已修改 |

## 問題說明

### #1、#2 恢復時沒有確認還沒交付的項目

以正式版本為準時，正式版本可能比遺失的暫存檔舊（例如核准後改了規格、還沒交付）；文字修正的改動清單遺失時，沒有任何地方列出還沒套用的項目。兩者都會讓已確認的內容在開發者不知情下消失。

### #3 審查豁免和分類規則矛盾

`docs/reviews/README.md:28-29` 規定 Specification Defect、Missing AC 一律阻擋，豁免的情況若照字面分類仍會阻擋。

### #4 規格審查紀錄不補時的交接

`.claude/skills/feature/SKILL.md:216` 要求交給 `acceptance-reviewer` 前確認規格審查紀錄已 commit、push；選擇不補時這一步無法完成。

### #6 單一來源不完整

暫存檔清單除了 `/feature:20`，還出現在 `/feature:301` 的括號與 `docs/README.md:23`。

### #10 重跑審查的處理

核准前的規格審查發現照 `/feature` 第 1 節「規格審查」的處理表（`.claude/skills/feature/SKILL.md:152-158`，Improvement Suggestion 不開 issue），第 3 節（`:231-236`）是核准後的流程。

### #11 已確認的決定沒寫進規格

`/issue` 只會加正在開發的 issue 的 `Closes`（`.claude/skills/issue/SKILL.md:39`）。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1、2 | 以正式版本或部分成果恢復時，如何避免還沒交付的項目消失 | 每次告知來源並確認／整份重寫重新核准 | 告知依據的分支、commit 與未 commit 的改動，確認還沒交付的項目並逐項標狀態，沒有依據的重新核准；項目清單遺失也照這一步 | — |
| 3 | 被豁免的情況怎麼回報 | (a) 列成 Improvement Suggestion／(b) 寫在「已接受的風險」／(c) 不回報 | (b)，`docs/reviews/README.md`「分類」加例外 | — |
| 4 | 規格審查紀錄不補時 | 依建議 | 採納；PR 描述記錄遺失與不補的決定，實作審查紀錄寫在「已接受的風險」，「尚未處理」若列出註明已決定不補 | 避免被誤認為還有待辦 |
| 16 | `docs/README.md`「取消」也是 `/feature` 的複本 | 一起改／不改 | 一起改成一句說明加指向 | 避免兩份內容不一致 |

## 尚未處理

無。

## 查證紀錄

| 規格中的事實 | 結果 | 依據 |
|---|---|---|
| 背景：「暫停與接續」依時間點列了四種情況 | 正確 | `.claude/skills/feature/SKILL.md:301-306` |
| 背景：`docs/README.md:29` 抄了同一套規則 | 正確 | `docs/README.md:29` |
| 背景：`docs/README.md:23`、`/feature:20`、`:301` 各列了一次暫存檔清單（AC12） | 正確 | 同左 |
| 背景：PR #71 實作審查中「舊 scratchpad 不存在時的接續」連續 3 輪阻擋 | 正確 | `docs/reviews/implementation/issue-69-context-in-repo.md:30`、`:34`、`:39` |
| 背景：ADR 0003 的先例 | 正確 | `docs/decisions/0003-issue-workflow.md`「放棄的做法」 |
| 背景：#72 的內容 | 正確 | issue #72；`docs/reviews/implementation/issue-69-context-in-repo.md:37` |
| 背景、需求 8：ADR 0009 只寫了舊路徑存在時的接續 | 正確 | `docs/decisions/0009-docs-delivery-and-glossary.md:29` |
| 需求 4：`acceptance-reviewer` 已有沒有規格審查紀錄時的情境檢查 | 正確 | `.claude/agents/acceptance-reviewer.md:11` |
| 需求 4：交給 `acceptance-reviewer` 前要確認規格審查紀錄已 commit | 正確 | `.claude/skills/feature/SKILL.md:216` |
| 需求 6：「分類」規定 Specification Defect、Missing AC 一律阻擋 | 正確 | `docs/reviews/README.md:28-29` |
| 需求 6：`acceptance-reviewer` 的檢查表與實作審查紀錄格式目前沒有「已接受的風險」 | 正確 | `docs/reviews/README.md:132-133`、`:152-193`、`:202` |
| 需求 2：`<功能>-glossary.md` 只寫這次確定的術語、不含檔頭 | 正確 | `.claude/skills/feature/SKILL.md:121` |
| 假設 2：ADR 草稿和規格一起核准 | 正確 | `.claude/skills/feature/SKILL.md:20` |

## 已接受的風險

以下都是 scratchpad 遺失的情況，需求 1–4 能合理處理，不會造成已核准的決定被推翻、正式文件被憑記憶重寫、開發者沒被告知決定或成果遺失（需求 6）：

1. 規格審查紀錄不補時，實作審查只補做情境檢查，不補事實查證：開發者選擇不補時已被告知。
2. 規格審查紀錄不補時，第 2 節「審查紀錄的 commit」的檔案不存在：需求 4 已跳過確認，跳過 commit 是合理的解讀。
3. Context 核准後以規格為準，不涵蓋審查紀錄「開發者決策」與文字修正改動清單裡的決定：第 4 步會確認還沒寫進紀錄的項目。
4. 第 2 步可能以工作目錄未 commit 的檔案為正式版本：第 4 步會告知。
5. PR 還沒建立時就決定不補：建立 PR 後再寫進描述。
6. 不補的決定比實作審查紀錄早：建立紀錄時寫進「已接受的風險」。
7. 核准前 Context 遺失、規格草稿還在：第 5 步請開發者選擇，不會自動推翻。
8. 正式版本比遺失的草稿舊、項目清單遺失：第 4 步要求告知來源並由開發者補上，仍依賴開發者的記憶，這是無法避免的限制。
9. 對已核准的規格重跑規格審查，發現要改規格時：照第 3 節，每項修改都要開發者確認。
