# 開 PR 時的描述檔和更新時用同一個 `.drafts/<功能>-pr-body.md`

- 狀態：已核准
- 等級：一般（改流程文件裡的規則：開 PR 時描述檔的位置；不改程式碼，不涉及資料一致性、認證授權、憑證保護，也不是重大架構決策）
- issue：#152
- PR：#153

## 簡短說明

開 PR 時，PR 描述也寫進 `.drafts/<功能>-pr-body.md`，再用 `gh pr create --body-file` 帶入，和更新 PR 描述用同一個檔案。

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/152

**問題**：流程只規定「更新」PR 描述用哪個檔案，沒規定「開 PR」時用哪個，同一份描述可能寫成兩份檔案。

**案例**：PR #150 開 PR 時，`feature-implementer` 把描述寫在 session scratchpad，之後更新時又寫了 `.drafts/` 的一份。開發者之後要改描述時不知道以哪份為準；scratchpad 那份不在暫存檔表上，`/feature`「清理暫存」不會刪。

**現在的規則**：

- `CLAUDE.md`「開發流程」第 3 點：開 PR 只寫「用 `gh pr create` 開 PR」；底下的子項規定更新 PR 描述用 `gh api -X PATCH … -F body=@.drafts/<功能>-pr-body.md`。
- `.claude/agents/feature-implementer.md` 步驟 3 第 4 小步：「push，用 `gh pr create` 開 PR。描述放『驗收條件、測試與結果的對照表』」，沒寫描述檔。
- `.claude/skills/feature/references/resume.md` 暫存檔表「PR 描述」那一列，「產生它的步驟」寫「回報、更新 PR 描述」，沒有開 PR。
- `.claude/settings.json` 已允許 `Bash(gh pr create *)`，加上 `--body-file` 不用改權限。

## 需求

1. `CLAUDE.md`「開發流程」第 3 點寫明：開 PR 時，描述寫進 `.drafts/<功能>-pr-body.md`，用 `gh pr create --body-file .drafts/<功能>-pr-body.md` 帶入。
2. `feature-implementer` 步驟 3 第 4 小步開 PR 時，照 `CLAUDE.md`「開發流程」第 3 點用這個描述檔。
3. 暫存檔表「PR 描述」那一列的「產生它的步驟」包括開 PR。
4. 主 session 在 PR 開好後、交給 `acceptance-reviewer` 前，為 issue #152 第二部分的第 1、2、3、5 點各開一個後續 issue，內容見「實作計畫」第 4 步。

## 不做

- 這份規格不改 issue #152 第二部分第 1、2、3、5 點的規則；這 4 點由需求 4 的後續 issue 處理。
- 不建立改 skill 時的情境驗證機制（issue #152 第二部分第 4 點），也不為它開 issue、不當其他點的前置條件：改完的 skill、agent 在之後的實際開發中使用，發現規則遺漏、誤判或流程退化時，依具體案例修正。
- 不改 `.claude/settings.json`。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 開發者讀 `CLAUDE.md`「開發流程」第 3 點，看得到開 PR 時描述寫進 `.drafts/<功能>-pr-body.md`、用 `gh pr create --body-file .drafts/<功能>-pr-body.md` 帶入 |
| AC2 | 開發者讀 `feature-implementer` 步驟 3 第 4 小步，看得到開 PR 時照 `CLAUDE.md`「開發流程」第 3 點用描述檔 |
| AC3 | 開發者讀暫存檔表「PR 描述」那一列，「產生它的步驟」是「開 PR、回報、更新 PR 描述」 |
| AC4 | issue #152 第二部分的第 1、2、3、5 點各有一個 open 的 issue，內容是「實作計畫」第 4 步列的該點方向 |
| AC5 | 這 4 個 issue 都寫明可以各自進行、第 4 點已決定不做，來源附 issue #152 與本 PR |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限、資料處理與一致性、同時操作、安全性 | 只改流程文件的文字，沒有改程式、畫面、資料與權限 |
| `.drafts/` 不存在 | 開 PR 前規格等草稿已在 `.drafts/`（`/feature`「硬規則」第 2 條），資料夾一定存在 |

## 實作計畫

1. `CLAUDE.md`「開發流程」第 3 點改成：push 後，把 PR 描述寫進 `.drafts/<功能>-pr-body.md`，用 `gh pr create --body-file .drafts/<功能>-pr-body.md` 開 PR，再用 `gh pr checks --watch` 等 CI。底下更新 PR 描述的子項不變。規則只寫在這裡（照 PR #150「每條規則只寫一處」），其他檔案連過來。
2. `feature-implementer.md` 步驟 3 第 4 小步改成：push，照 `CLAUDE.md`「開發流程」第 3 點開 PR；描述放「驗收條件、測試與結果的對照表」。
3. `resume.md` 暫存檔表「PR 描述」列的「產生它的步驟」改成「開 PR、回報、更新 PR 描述」。
4. 主 session 在 PR 開好後、交給 `acceptance-reviewer` 前，照 `docs/issues.md` 開 4 個後續 issue（第 1、2、3、5 點），內容寫開發者核准的方向：
   - 第 1 點：實作審查每一輪的結果用 `gh pr comment --body-file` 貼成 PR 留言；規格審查的結果在 PR 開好後貼成第一則留言；不再 commit 進 `docs/reviews/`；既有檔案照 `docs/README.md`「生命週期」保留，`docs/reviews/README.md` 標記為已被取代；以後的讀者需要的決定照舊寫進規格的修改紀錄或 ADR；漏洞的細節不寫進公開留言。
   - 第 2 點：每項發現改用 Conventional Comments 的一個標籤（`issue`、`suggestion`、`nitpick`、`question`）加 blocking／non-blocking；阻擋的 `issue` 交回實作、`question` 問開發者、不阻擋但值得處理的開 issue、`nitpick` 由寫的人決定；漏洞照舊另外處理；拿掉嚴重程度、6 種類型與「輪數依根本原因計算」，改成連續 3 輪都還有阻擋就停下來問開發者。
   - 第 3 點：照 Anthropic〈Skill authoring best practices〉重寫 skill、agent：只寫 Claude 不知道的事、每條規則說明原因；只有容易出錯、難挽回的操作（漏洞、`git add`、合併、`.env`、刪除）寫固定步驟；「不做」的 6 步判斷順序、暫存檔遺失的審查豁免改成一兩句原則加原因；`CLAUDE.md`「寫作規則」加一條指向該文件，同時寫明這個 repo 不建立情境驗證、改完在實際開發中觀察（第 4 點的理由）。
   - 第 5 點：「一般」等級加快速路徑，條件是 issue 已寫清楚現象與預期、沒有要開發者決定的事、不碰高風險範圍；符合時規格用短版放在 PR 描述、不存 `docs/specs/`、不做規格審查、實作審查一次；開發者核准、測試、由 `feature-implementer` 實作照舊；部分推翻 ADR 0006、0012，另寫新 ADR。
   - 4 個 issue 都寫明可以各自進行、第 4 點已決定不做（不必等它），來源附 issue #152 與本 PR。
   - 開好後把 4 個 issue 的編號寫進 PR 描述（照 CLAUDE.md「開發流程」第 3 點更新）。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | 讀 `CLAUDE.md`「開發流程」第 3 點 | 寫著描述檔 `.drafts/<功能>-pr-body.md` 與 `gh pr create --body-file .drafts/<功能>-pr-body.md` |
| AC2 | 讀 `.claude/agents/feature-implementer.md` 步驟 3 第 4 小步 | 開 PR 時照 `CLAUDE.md`「開發流程」第 3 點 |
| AC3 | 讀 `.claude/skills/feature/references/resume.md` 暫存檔表「PR 描述」列 | 「產生它的步驟」是「開 PR、回報、更新 PR 描述」 |
| AC4 | 讀 PR 描述列出的 4 個 issue 編號，`gh issue view <號碼> --json state,title,body` 逐一讀 | 4 個都是 open，各對應一點，寫著「實作計畫」第 4 步該點的方向 |
| AC5 | 同上 | 每個 issue 都寫明可以各自進行、第 4 點已決定不做，來源附 #152 與本 PR |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
