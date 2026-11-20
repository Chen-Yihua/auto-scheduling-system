# 審查結果改留在 PR 留言，不再 commit 進 `docs/reviews/`

- 狀態：已核准
- 等級：一般（改流程文件裡的規則：審查結果放在哪裡、誰 commit；另在允許清單加一個指令。不改程式碼，不涉及資料一致性、認證授權、憑證保護，也不是重大架構決策。推翻 ADR 0005、0009 的一部分，另寫 ADR 0015）
- issue：#154
- PR：#158

## 簡短說明

規格審查與實作審查的每一輪結果，貼成 PR 上的一則公開留言，不再整理成 `docs/reviews/` 的紀錄檔 commit。

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/154

**問題**：每一輪審查完，主 session 要照 60 多行的格式（`docs/reviews/README.md`「紀錄檔格式」）把報告整理成紀錄檔，commit、push，再等一次 CI。

**案例**：PR #153 只改了 3 行文件，審查紀錄就多了 3 個 commit（規格審查紀錄、實作審查紀錄、修正紀錄裡寫錯的 commit 編號），每個 commit 都跑了一次完整的 CI。

**現在的規則**：

- `implement-and-review`「審查紀錄的 commit」「每一輪都更新紀錄檔」：主 session 把紀錄檔 commit 並 push 到 PR 分支。
- `write-spec`「審查紀錄」：規格審查的結果先整理在 `.drafts/<功能>-spec-review.md`，PR 開好後存成 `docs/reviews/specification/<功能>.md` commit。
- `docs/README.md`「生命週期」：`reviews/specification/`、`reviews/implementation/` 永久保存。
- CLAUDE.md「漏洞」第 2 點：不能寫漏洞細節的地方包括 `docs/reviews/`，沒有 PR 留言。
- `acceptance-reviewer` 只能讀檔、跑 `git` 的唯讀指令和測試（`.claude/agents/acceptance-reviewer.md` 「回報格式」前一段）。
- `.claude/settings.json` 已允許 `Bash(gh pr view *)`，沒有 `gh pr comment`。
- 一般做法：Google eng-practices〈[The Standard of Code Review](https://google.github.io/eng-practices/review/reviewer/standard.html)〉把討論的結果記成 CL 上的留言。

## 需求

1. 每一輪審查（規格審查、實作審查）貼一則公開的 PR 留言，用 `gh pr comment <PR> --body-file <留言檔>`。
2. 留言檔和報告原文分開：報告原文 `<功能>-spec-review-r<N>.md`、`<功能>-impl-review-r<N>.md` 不動；留言檔 `<功能>-spec-review-r<N>-comment.md`、`<功能>-impl-review-r<N>-comment.md` 是原文加一節「處理」，第一行寫 `## <功能>：規格審查第 N 輪` 或 `## <功能>：實作審查第 N 輪（commit <sha>）`；報告的「技術證據」一節包在收合區塊（`<details><summary>技術證據</summary>` … `</details>`）裡。
3. 留言檔裡標成「漏洞」的內容，貼出前改寫成一般性的描述（或 advisory 編號）。
4. 「處理」一節每項發現寫：處理方式、決定者、根本原因（只有阻擋的項目寫）、結果；開發者決定的項目另外寫選項與理由。上一輪「結果」是「交回實作」的項目，在這一輪的表另列一行：「#」寫「第 N 輪 #M」，「結果」寫修正的 commit。
5. 每一輪先處理完發現（決定處理方式、開好要開的 issue），再貼留言；交回實作的項目「結果」寫「交回實作」，修正的 commit 寫在下一輪留言的「處理」。留言貼出後不修改。
5a. 最後一輪之後還有修正或開發者決定時（例如「寫法：」的修正、開發者要求在這個 PR 處理的不阻擋發現），另外貼一則補充留言，第一行寫 `## <功能>：實作審查補充`，寫這些 commit 與決定。
6. 規格審查在 PR 開之前做，在 PR 開好後、交給 `acceptance-reviewer` 前，依輪次貼出留言。
7. 改到驗收條件的開發者決定：規格審查時直接改草稿，寫在那一輪留言的「處理」；實作審查時或核准後，照現行規則記在規格的「修改紀錄」。其他的開發者決定寫在那一輪留言的「處理」。
8. `acceptance-reviewer` 用 `gh pr view <PR> --json comments` 讀規格審查與前幾輪實作審查的留言。
9. 從審查開的 issue，「來源」寫 `PR #NN 第 N 輪規格審查／實作審查 #M`。
10. 回報附審查留言的連結（`gh pr comment` 成功時印出的網址）。
11. 主 session 不再 commit 審查紀錄檔，也不再新增 `docs/reviews/specification/`、`docs/reviews/implementation/` 的檔案。
12. `docs/reviews/README.md` 刪掉「紀錄檔格式」一節，開頭改寫成審查結果貼在 PR 留言；新增「處理」一小節，放需求 4 的欄位、原本「決定者」能填什麼的規則，以及「結果」的可填值（commit、issue、advisory 編號、「交回實作」、「規格已修改」、「開發者決定不採用」）；「分類」「報告格式」保留。
13. CLAUDE.md「漏洞」第 2 點的清單加上 PR 留言，拿掉 `docs/reviews/`。
14. `.claude/settings.json` 的允許清單加上 `Bash(gh pr comment *)`，禁止清單加上 `Bash(gh pr comment *--edit-last*)`。
15. 新增 ADR 0015；ADR 0005、0009 只改狀態行，註明哪一部分被 0015 取代。

## 不做

- 不改「分類」「報告格式」的內容（審查發現的分類由 #155 處理），只改這兩節裡提到紀錄檔的句子。
- 不刪除、不改寫 `docs/reviews/` 底下既有的紀錄檔。
- 不把已合併 PR 的紀錄搬到 PR 留言。
- 不允許 `gh api` 寫入類的指令。
- 這個 PR（#154）自己的審查照新規則貼留言；第 1、2 輪規格審查的報告原文沒有存檔，留言用發現清單加「處理」，並在留言註明原文沒有保留。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 開發者讀 `implement-and-review`，看得到每一輪實作審查後用 `gh pr comment <PR> --body-file <留言檔>` 貼一則留言 |
| AC2 | 開發者讀 `implement-and-review`，看得到留言檔是報告原文加「處理」一節，報告原文不動 |
| AC2a | 開發者讀 `implement-and-review`，看得到留言檔第一行標明審查種類與輪數（實作審查另外寫 commit） |
| AC2b | 開發者讀 `implement-and-review`，看得到留言檔的「技術證據」包在 `<details>` 收合區塊裡 |
| AC3 | 開發者讀 `implement-and-review`，看得到貼留言前要把留言檔裡「漏洞」的內容改寫 |
| AC4 | 開發者讀 `implement-and-review`，看得到先處理完發現、開好 issue 才貼留言，修正的 commit 寫在下一輪留言，留言貼出後不修改 |
| AC4a | 開發者讀 `implement-and-review`，看得到最後一輪之後的修正與決定另外貼一則「實作審查補充」留言 |
| AC5 | 開發者讀 `write-spec`「審查紀錄」，看得到規格審查每一輪的留言在 PR 開好後、交給 `acceptance-reviewer` 前貼出 |
| AC6 | 開發者讀 `docs/reviews/README.md`「處理」，看得到需求 4 的欄位、「決定者」能填什麼與「結果」的可填值 |
| AC7 | 開發者讀 `clarify-requirements`「記錄決定」，看得到需求 7 |
| AC8 | 開發者讀 `acceptance-reviewer` 的定義，看得到用 `gh pr view <PR> --json comments` 讀規格審查與前幾輪的留言，限制那一段也允許這個指令 |
| AC9 | 開發者讀 `docs/issues.md` 與 `implement-and-review`「不阻擋的發現開 issue」，看得到「來源」寫 `PR #NN 第 N 輪…審查 #M` |
| AC10 | 開發者讀 `feature`「回報」，看得到附審查留言的連結 |
| AC11 | 在 `CLAUDE.md`、`.claude/`、`docs/README.md`、`docs/issues.md`、`docs/reviews/README.md` 用 `grep -rn "docs/reviews\|reviews/\|紀錄檔\|審查紀錄"` 找到的句子，沒有一句要求主 session commit 審查紀錄檔、新增紀錄檔，或說明紀錄檔每輪更新 |
| AC12 | 開發者讀 `docs/reviews/README.md`，沒有「紀錄檔格式」一節 |
| AC13 | 開發者讀 `docs/reviews/README.md` 開頭，看得到審查結果貼在 PR 留言，「分類」「報告格式」兩節還在 |
| AC14 | 開發者讀暫存檔表，沒有「規格審查紀錄草稿」那一列；有留言檔那一列，正式版本是 PR 留言 |
| AC15 | 開發者讀 `docs/README.md` 的 `reviews/` 那一列與「生命週期」，看得到既有紀錄檔保留，之後的審查結果在 PR 留言 |
| AC16 | 開發者讀 CLAUDE.md「漏洞」第 2 點，清單有 PR 留言，沒有 `docs/reviews/` |
| AC17 | `.claude/settings.json` 的允許清單多了 `Bash(gh pr comment *)`，禁止清單多了 `Bash(gh pr comment *--edit-last*)`，沒有其他改動 |
| AC18 | `docs/decisions/0015-*.md` 存在，`docs/decisions/README.md` 清單有 0015 |
| AC19 | 0005、0009 的狀態行與 `docs/decisions/README.md` 清單的狀態欄註明被 0015 取代的部分，ADR 內文沒有改 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限、資料處理與一致性、同時操作 | 只改流程文件與允許清單，沒有改程式、畫面與資料 |
| 安全性 | 漏洞細節不公開由需求 3、13 與 AC3、AC16 涵蓋；允許清單只加貼留言、禁止修改最後一則留言，不加 `gh api`（「不做」） |
| 貼留言失敗 | 留言檔還在 `.drafts/`，重貼即可；暫存檔遺失的恢復見暫存檔表（AC14） |

## 實作計畫

用 AC11 的 `grep` 找到的每一處逐一改寫或刪除（ADR 本文、規格、既有紀錄檔不改）。主要的改動：

1. **`implement-and-review`**
   - 「步驟」第 2 步改成：PR 建立後，照「審查留言」貼規格審查每一輪的留言；第 4、5 步改成：處理完發現後，照「審查留言」貼這一輪的留言。
   - 刪掉「Commit 責任」表的「審查紀錄」列。
   - 「審查紀錄的 commit」改成「審查留言」：需求 1～5a，留言連結取 `gh pr comment` 印出的網址。
   - 「交給 acceptance-reviewer 審查」：附規格審查留言與前幾輪留言的連結，取代紀錄檔路徑。
   - 「不阻擋的發現開 issue」第 3 步的來源照需求 9；第 5 步改成在這一輪留言檔的「處理」寫 issue 連結。
   - 「審查紀錄與重新審查」：「寫進紀錄檔前」改成「貼留言前，在留言檔改寫」，報告原文不動；刪掉「每一輪都更新紀錄檔」裡紀錄檔與 commit 的規定。
   - 「輪數依根本原因計算」第 1 步：根本原因寫在留言的「處理」。
   - 「交給 acceptance-reviewer 審查」的「規格審查紀錄草稿遺失、開發者決定不補」改成「規格審查的留言檔遺失、還沒貼出，開發者決定不補」。
2. **`write-spec`「審查紀錄」**：每輪報告原文存成 `<功能>-spec-review-r<N>.md`，處理完寫留言檔 `<功能>-spec-review-r<N>-comment.md`；PR 開好後照 `implement-and-review`「審查留言」依序貼出。不再整理 `<功能>-spec-review.md`。
3. **`clarify-requirements`「記錄決定」**：最後一句改成需求 7。
4. **`feature`**：「回報」的「審查紀錄的檔案連結」改成「審查留言的連結」；「清理暫存」「文字修正的流程」「可以決定要不要合併」裡的「審查紀錄」改成「審查留言」。
5. **`feature/references/resume.md`**：刪掉「規格審查紀錄草稿」列；「審查報告原文」列的恢復方式改成：已貼出的以 PR 留言為準（`gh pr view <PR> --json comments`），還沒貼出的請開發者選擇重跑或不補；新增「審查留言」列（`<功能>-spec-review-r<N>-comment.md`、`<功能>-impl-review-r<N>-comment.md`，產生步驟：處理完該輪發現；正式版本：PR 留言）；第 6 步的「實作審查紀錄的已接受的風險」改成「該輪留言的『處理』」。
6. **兩個 reviewer agent**：「回報格式」的第一句改成主 session 會把報告貼成公開的 PR 留言；`acceptance-reviewer` 的輸入改成規格審查留言與前幾輪留言（ADR 0015 以前的 PR 仍用 `docs/reviews/`），限制那一段加上 `gh pr view <PR> --json comments`；「完整格式的規格卻沒有規格審查紀錄」改成「沒有規格審查留言」。
7. **`feature-implementer`** 步驟 3 第 3 小步：刪掉「`docs/reviews/` 的審查紀錄由主 session commit」這句。
8. **`/issue`**：刪掉「審查紀錄」那一列。
9. **`docs/issues.md`**：「來源」那一行照需求 9。
10. **`docs/reviews/README.md`**：開頭的表與說明改寫成需求 12；刪掉「紀錄檔格式」；新增「處理」小節；「報告格式」「分類」裡提到紀錄檔的句子改成留言。
11. **`docs/README.md`**：`reviews/` 那一列（第 12 行）、「生命週期」的永久保存列與「暫存」列（「審查紀錄的 commit」那半句改指向「審查留言」）。
12. **CLAUDE.md**「漏洞」第 2 點照需求 13。
13. **`.claude/settings.json`**：照需求 14。
14. **ADR**：新增 `docs/decisions/0015-review-results-in-pr-comments.md`（交付清單）；0005、0009 的狀態行加註；`docs/decisions/README.md` 清單加 0015，0005、0009 的狀態欄同步加註。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | 讀 `implement-and-review`「步驟」「審查留言」 | 每輪用 `gh pr comment <PR> --body-file <留言檔>` |
| AC2 | 同上 | 留言檔＝原文＋「處理」，原文不動 |
| AC2a | 同上 | 第一行是 `## <功能>：規格審查第 N 輪` 或 `## <功能>：實作審查第 N 輪（commit <sha>）` |
| AC2b | 同上 | 「技術證據」包在 `<details><summary>技術證據</summary>` … `</details>` |
| AC3 | 讀 `implement-and-review`「審查留言」「審查紀錄與重新審查」 | 貼出前在留言檔改寫「漏洞」 |
| AC4 | 讀 `implement-and-review`「步驟」「審查留言」 | 先處理發現、開 issue，再貼；commit 寫在下一輪；不修改已貼出的留言 |
| AC4a | 讀 `implement-and-review`「審查留言」 | 最後一輪之後的修正與決定貼成 `## <功能>：實作審查補充` |
| AC5 | 讀 `write-spec`「審查紀錄」 | PR 開好後、交給 `acceptance-reviewer` 前依序貼出 |
| AC6 | 讀 `docs/reviews/README.md`「處理」 | 有處理方式、決定者、根本原因、結果、選項與理由，以及「決定者」能填什麼；上一輪「交回實作」的項目另列一行，「#」寫「第 N 輪 #M」，「結果」寫修正的 commit |
| AC7 | 讀 `clarify-requirements`「記錄決定」 | 寫著需求 7 |
| AC8 | 讀 `.claude/agents/acceptance-reviewer.md` 輸入與限制 | 用 `gh pr view <PR> --json comments`；限制允許這個指令 |
| AC9 | 讀 `docs/issues.md`「來源」、`implement-and-review`「不阻擋的發現開 issue」第 3 步 | `PR #NN 第 N 輪…審查 #M` |
| AC10 | 讀 `.claude/skills/feature/SKILL.md`「回報」 | 附審查留言的連結 |
| AC11 | 跑 AC11 的 `grep`，逐行看 | 沒有一句要求主 session commit 審查紀錄檔、新增紀錄檔，或說明紀錄檔每輪更新（指向 `docs/reviews/README.md`「分類」「報告格式」等說明的句子照常保留） |
| AC12 | 讀 `docs/reviews/README.md` 的標題 | 沒有「紀錄檔格式」 |
| AC13 | 讀 `docs/reviews/README.md` 開頭與標題 | 開頭寫貼在 PR 留言；有「分類」「報告格式」 |
| AC14 | 讀 `resume.md` 暫存檔表 | 沒有「規格審查紀錄草稿」；有「審查留言」列，正式版本是 PR 留言 |
| AC15 | 讀 `docs/README.md` 第 12 行附近與「生命週期」 | 既有紀錄檔保留，之後在 PR 留言 |
| AC16 | 讀 CLAUDE.md「漏洞」第 2 點 | 有「PR 留言」，沒有 `docs/reviews/` |
| AC17 | `git diff origin/main -- .claude/settings.json` | allow 多一行 `Bash(gh pr comment *)`，deny 多一行 `Bash(gh pr comment *--edit-last*)` |
| AC18 | `ls docs/decisions/0015-*`；讀 `docs/decisions/README.md` 清單 | 檔案存在；清單有 0015 |
| AC19 | `git diff origin/main -- docs/decisions/0005-* docs/decisions/0009-* docs/decisions/README.md` | 0005、0009 只改狀態行；清單的狀態欄同步 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-20 | 需求 4、AC6 的測試對應加上：上一輪交回實作的項目另列一行（「第 N 輪 #M」＋修正 commit） | 實作審查第 1 輪 #1：每輪重新編號，下一輪留言沒有寫上一輪修正 commit 的位置 → 需求 4、AC6；檢查過 AC4（修正 commit 寫在下一輪，不變）、AC4a、需求 9（「來源」格式一致）不用改 | 開發者 |

## 請你決定

無
