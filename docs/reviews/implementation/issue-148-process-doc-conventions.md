# 流程文件對照常見寫法、每條規則只寫一處、草稿改放 `.drafts/`：實作審查紀錄

- 規格：[docs/specs/issue-148-process-doc-conventions.md](../../specs/issue-148-process-doc-conventions.md)
- PR：#150
- 等級：一般
- 輪數：2（第 1 輪 2026-11-20 `cec1c89`；第 2 輪 2026-11-20 `fcfb8eb`）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：5 項（規格內容互相矛盾或沒有依據 2、沒有錯，但可以更好 3；一般操作就會遇到的錯 1、影響小的問題 2、不影響功能，只供參考 2）
- 開發者決策：2 項
- 尚未處理：1 項（開 issue）

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-20 `cec1c89` | #1–#3（#1、#2） | 暫存檔表加「PR 描述」、`CLAUDE.md:28` 與 advisory 指令改用暫存檔表的檔名、新增 AC27；漏洞定義直接連到原文；`docs/reviews/README.md:10` 刪「主 session 的」（`fcfb8eb`） |
| 2 | 2026-11-20 `fcfb8eb` | #4、#5（無） | #4、#5 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 「只建立表上的暫存檔」和要寫成檔案的 PR 描述、advisory 更新衝突 | 規格內容互相矛盾或沒有依據 | 一般操作就會遇到的錯 | 是 | 否 | 暫存檔表漏了工具輸入檔 | 暫存檔表加「PR 描述」`<功能>-pr-body.md`；`CLAUDE.md:28`、advisory 的 PATCH 與 POST 用暫存檔表的檔名；新增 AC27 | 開發者 | `fcfb8eb` |
| 2 | 1 | 漏洞的定義要連跳兩個檔案 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 否 | 引用層數 | 需求 17 改成直接連到 `docs/reviews/README.md`「涉及安全／架構」 | 開發者 | `fcfb8eb` |
| 3 | 1 | 寫法：`docs/reviews/README.md:10` 還寫「主 session 的草稿資料夾」 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 刪掉「主 session 的」 | 規則 | `fcfb8eb` |
| 4 | 2 | advisory 指令的 `--input` 沒有寫 `.drafts/` | 沒有錯，但可以更好 | 影響小的問題 | 否 | 否 | — | 開 issue（#151）；之後開發者決定在這個 PR 修，不另外審查 | 開發者 | [#151](https://github.com/Chen-Yihua/auto-scheduling-system/issues/151)、`56a7aff` |
| 5 | 2 | 開 PR 時的描述檔沒有指定位置 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 開 issue | 規則 | [#152](https://github.com/Chen-Yihua/auto-scheduling-system/issues/152) |

## 問題說明

### #1 「只建立表上的暫存檔」和要寫成檔案的 PR 描述、advisory 更新衝突

`feature` 硬規則 2 改成只建立暫存檔表上的暫存檔（`.claude/skills/feature/SKILL.md:35`），但更新 PR 描述要先寫成檔案（`CLAUDE.md:28` 的 `-F body=@<檔案>`），更新已有的 advisory 也要 `--input <檔案>`（`.claude/skills/implement-and-review/SKILL.md:129`）；暫存檔表（`.claude/skills/feature/references/resume.md:22-31`）沒有這兩種檔。主 session 只能違反規則，或自己決定放哪裡，清理時也不會刪到。規格審查時這兩種檔案還在 scratchpad 這個詞底下，要等換詞刪光後才看得出沒有位置。

### #2 漏洞的定義要連跳兩個檔案

`.claude/skills/implement-and-review/SKILL.md:125` 寫「漏洞的定義…見 CLAUDE.md「漏洞」」，`CLAUDE.md:49` 又寫「見 `docs/reviews/README.md`「涉及安全／架構」」，定義在 `docs/reviews/README.md:66-67`。規格審查第 1 輪把定義移到 reviews README 時，需求 17 的這一句沒有跟著改，AC16 在這一處不成立。

### #3 寫法：`docs/reviews/README.md:10` 還寫「主 session 的草稿資料夾」

`.drafts/` 是整個 repo 共用的（ADR 0014「影響」），「主 session 的」不準確。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 要先寫成檔案再交給 `gh` 的內容放哪裡 | 這個 PR 補進暫存檔表／另開 issue | 這個 PR 補：暫存檔表加「PR 描述」、advisory 用 `<功能>-advisory.json`、新增 AC27 | 維持「只建立表上的暫存檔」，不另開例外 |
| 2 | 漏洞的定義連兩層 | 這個 PR 改需求 17／另開 issue | 這個 PR 改 | 讓引用直接連到原文（AC16） |
| 4 | advisory 指令少了 `.drafts/`（#151） | 這個 PR 修／照 issue 之後修 | 這個 PR 修，不另外審查 | 改動只有兩個路徑 |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 5 | 不阻擋，照規則開 issue | #152 |
