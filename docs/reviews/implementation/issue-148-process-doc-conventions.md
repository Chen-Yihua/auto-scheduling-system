# 流程文件對照常見寫法、每條規則只寫一處、草稿改放 `.drafts/`：實作審查紀錄

- 規格：[docs/specs/issue-148-process-doc-conventions.md](../../specs/issue-148-process-doc-conventions.md)
- PR：#150
- 等級：一般
- 輪數：1（第 1 輪 2026-11-20 `cec1c89`）
- 最終結果：仍有阻擋（#1、#2，等開發者確認）

## 摘要

- 發現：3 項（規格內容互相矛盾或沒有依據 2、沒有錯，但可以更好 1；一般操作就會遇到的錯 1、影響小的問題 1、不影響功能，只供參考 1）
- 開發者決策：0 項（2 項等確認）
- 尚未處理：3 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-20 `cec1c89` | #1–#3（#1、#2） | 等開發者確認 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 「只建立表上的暫存檔」和要寫成檔案的 PR 描述、advisory 更新衝突 | 規格內容互相矛盾或沒有依據 | 一般操作就會遇到的錯 | 是 | 否 | 暫存檔表漏了工具輸入檔 | 等開發者確認 | — | — |
| 2 | 1 | 漏洞的定義要連跳兩個檔案 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 否 | 引用層數 | 等開發者確認 | — | — |
| 3 | 1 | 寫法：`docs/reviews/README.md:10` 還寫「主 session 的草稿資料夾」 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 等第 1、2 項一起交給 `feature-implementer` 在這個 PR 改 | 規則 | — |

## 問題說明

### #1 「只建立表上的暫存檔」和要寫成檔案的 PR 描述、advisory 更新衝突

`feature` 硬規則 2 改成只建立暫存檔表上的暫存檔（`.claude/skills/feature/SKILL.md:35`），但更新 PR 描述要先寫成檔案（`CLAUDE.md:28` 的 `-F body=@<檔案>`），更新已有的 advisory 也要 `--input <檔案>`（`.claude/skills/implement-and-review/SKILL.md:129`）；暫存檔表（`.claude/skills/feature/references/resume.md:22-31`）沒有這兩種檔。主 session 只能違反規則，或自己決定放哪裡，清理時也不會刪到。規格審查時這兩種檔案還在 scratchpad 這個詞底下，要等換詞刪光後才看得出沒有位置。

### #2 漏洞的定義要連跳兩個檔案

`.claude/skills/implement-and-review/SKILL.md:125` 寫「漏洞的定義…見 CLAUDE.md「漏洞」」，`CLAUDE.md:49` 又寫「見 `docs/reviews/README.md`「涉及安全／架構」」，定義在 `docs/reviews/README.md:66-67`。規格審查第 1 輪把定義移到 reviews README 時，需求 17 的這一句沒有跟著改，AC16 在這一處不成立。

### #3 寫法：`docs/reviews/README.md:10` 還寫「主 session 的草稿資料夾」

`.drafts/` 是整個 repo 共用的（ADR 0014「影響」），「主 session 的」不準確。

## 開發者決策

無

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 1 | 等開發者確認 | 無 |
| 2 | 等開發者確認 | 無 |
| 3 | 和 #1、#2 一起交給 `feature-implementer` | 無 |
