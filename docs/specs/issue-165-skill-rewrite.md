# feature skill 改成原則加原因（逐檔重寫第 1 批）

- 狀態：已核准（2026-11-21）
- 等級：一般（改定義流程的文件：`feature` skill、`resume.md` 的寫法，以及刪掉 `CLAUDE.md`「開發流程」第 6 點。不改程式碼，不涉及資料一致性、認證授權、憑證保護，也不是重大架構決策。把條列改寫成原則時判斷結果可能改變，所以不算文字修正；issue 有 3 項待決定，不走快速路徑）
- issue：#165
- PR：

## 簡短說明

照 `CLAUDE.md`「寫作規則」第 6 條改寫 `.claude/skills/feature/SKILL.md` 與 `.claude/skills/feature/references/resume.md`：判斷結果不變，只改寫法。另外刪掉 `CLAUDE.md`「開發流程」第 6 點，並為其他 4 批改寫各開一個 issue。

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/165

**問題**：開發者讀或修改 `/feature`、`/issue` 用的 skill 時，規則是一個情況加一條寫出來的，要讀完整段才看得出原則；每補一條，也要回頭檢查其他規則的先後與例外。

**實際案例**：`.claude/skills/feature/SKILL.md:57-94`「快速路徑」有 3 組編號清單，共 14 項，其中條件、規格階段的做法、核准後的做法混在一起；「規格階段」6 項彼此不重疊，卻寫成編號步驟。`.claude/skills/feature/SKILL.md:106`「文字修正的流程」把 5 個有先後的步驟寫成一段。

**和這次相關的現況**：

- `CLAUDE.md`「寫作規則」第 5 條：有先後順序的條件寫成編號清單；第 6 條（#156，PR #166）：只寫 Claude 不知道的事，只有容易出錯、出錯難挽回的操作寫固定步驟，說明重要指示背後的原因。
- `feature/SKILL.md` 裡屬於 #165「必要條件」7 項固定步驟的：核准前只寫草稿資料夾（`:35`）、核准的定義（`:36`）、漏洞（`:38`）、不合併 PR（`:39`）、暫存檔只刪暫存檔表上的檔名（`:125`）。其他 2 項不在這兩個檔：`git add` 在 `CLAUDE.md:26`，`.env` 在 `CLAUDE.md`「跨前後端的連動」最後一點。
- `resume.md:9-16` 暫存檔遺失時的 6 個步驟是固定步驟：做錯會讓已核准的內容被推翻或憑記憶重寫（ADR 0010）。
- 其他使用中的文件引用 `feature`、`resume.md` 段落的地方（`origin/main`；ADR、規格、審查紀錄、實驗紀錄是歷史紀錄，不列）：
  - 「判斷等級」：`.claude/agents/specification-reviewer.md:10`、`.claude/skills/implement-and-review/SKILL.md:165`、`.claude/skills/issue/SKILL.md:35`、`.claude/skills/write-spec/SKILL.md:47`、`docs/reviews/README.md:10`、`docs/specs/README.md:3`、`:95`
  - 「快速路徑」：`.claude/skills/clarify-requirements/SKILL.md:47`、`.claude/skills/issue/SKILL.md:36`、`.claude/skills/write-spec/SKILL.md:8`、`docs/specs/README.md:106`
  - 「回報」：`.claude/skills/implement-and-review/SKILL.md:22`、`:66`、`:79`、`.claude/skills/issue/SKILL.md:38`
  - 「重大架構決策」：`.claude/agents/acceptance-reviewer.md:23`、`.claude/skills/implement-and-review/SKILL.md:99`、`.claude/skills/write-spec/SKILL.md:24`、`docs/reviews/README.md:40`
  - 「文字修正的流程」：`.claude/skills/implement-and-review/SKILL.md:33`、`.claude/skills/write-spec/SKILL.md:8`
  - 「硬規則」：`.claude/skills/clarify-requirements/SKILL.md:59`（第 2 條）、`.claude/skills/issue/SKILL.md:22`（第 4 條）、`:35`、`.claude/skills/write-spec/SKILL.md:58`
  - 「清理暫存」：`docs/README.md:23`
  - 「取消」：`docs/README.md:26`、`:28`
  - `resume.md` 的暫存檔表、恢復步驟（沒有加「」）：`docs/README.md:23`、`docs/reviews/README.md:57`
- `CLAUDE.md:31`「開發流程」第 6 點是「PR 合併後確認來源分支已刪除；若 GitHub 沒有自動刪除，就手動刪除該分支。」這是最後一點，`.claude/`、`docs/`（規格與審查紀錄以外）、`CLAUDE.md` 沒有其他地方引用它。GitHub 上已合併的分支（`issue-155-review-labels`、`issue-156-skill-authoring`、`issue-157-fast-path`）都已自動刪除。
- 各條規則的原因來源：硬規則第 2 條見 ADR 0014；開始前檢查舊暫存檔見 ADR 0014；快速路徑見 ADR 0018；暫存檔遺失見 ADR 0010。

## 需求

1. `.claude/skills/feature/SKILL.md` 換成「附錄 A」的全文。
2. `.claude/skills/feature/references/resume.md` 照「附錄 B」改一句，其他行不動。
3. 兩個檔裡被其他檔案引用的段落名稱不改；「硬規則」6 條的編號與順序不改。
4. 有先後順序、而且兩個條件可能同時成立、順序會改變結果的判斷：保留編號清單，清單前寫一句排這個順序的原因。
5. 條件彼此不重疊、順序不影響結果的判斷：改寫成原則加原因。
6. 本次改寫只處理實際修改的段落，不延伸重寫其他未修改的段落。
7. 清單被其他地方用編號引用時（例如「條件 2」），保留編號，即使條件彼此不重疊。
8. 照順序做的步驟寫成編號清單，清單前寫一句排這個順序的原因。
9. 下面這些固定步驟在改寫後仍寫成固定步驟，位置不變：
   1. 核准前只寫草稿資料夾（硬規則第 2 條）。
   2. 開發者明確表示核准才算核准（硬規則第 3 條）。
   3. 漏洞照 `CLAUDE.md`「漏洞」（硬規則第 5 條）。
   4. 合併由開發者決定（硬規則第 6 條）。
   5. 刪暫存檔時只刪暫存檔表上的檔名（「清理暫存」）。
   6. 暫存檔遺失時的恢復步驟（`resume.md`「暫停與接續」）。
10. 刪掉 `CLAUDE.md`「開發流程」第 6 點整條，原因：開發者不一定在 `/feature`、`/issue` 結束後馬上合併，清理本機分支是開發者自己的工作習慣。
11. 為其他 4 批各開一個 issue（照 `docs/issues.md`），每個 issue 寫：
   1. 要改的檔案：
      - 第 2 批：`.claude/skills/clarify-requirements/SKILL.md`
      - 第 3 批：`.claude/skills/implement-and-review/SKILL.md`
      - 第 4 批：`.claude/skills/write-spec/SKILL.md`、`.claude/skills/issue/SKILL.md`、`.claude/skills/issue-triage/SKILL.md`
      - 第 5 批：`.claude/agents/acceptance-reviewer.md`、`.claude/agents/feature-implementer.md`、`.claude/agents/specification-reviewer.md`
   2. 照需求 3～8 的寫法（需求 6 指那一批實際修改的段落）。
   3. 要保留的固定步驟：漏洞（照 `CLAUDE.md`「漏洞」與 `docs/reviews/README.md`「漏洞」，阻擋照「阻擋」判斷，不一律阻擋）、`git add` 只加這次要 commit 的檔案、合併由開發者決定、不讀不複製不改 `.env`、刪除（草稿資料夾的暫存檔只刪暫存檔表上的檔名；`docs/` 永久保存的文件不刪、只標記取代；dev server 可能開著時不刪 `.nuxt`、`.output`）、開發者明確表示核准才算核准、核准前只寫草稿資料夾。
   4. 驗收方式：規格列出舊檔每條規則的「情況 → 結果」對照表，改寫後逐列確認結果相同；`grep` 確認該檔原有的固定步驟都還在。
   5. 範圍不含 `docs/reviews/README.md`、`docs/specs/README.md`。
   6. 來源：#165。

## 不做

- 不改其他 skill、agent：留給需求 11 的 issue，每批一兩個檔，審查時才看得出判斷結果有沒有變。
- 不改 `docs/reviews/README.md`、`docs/specs/README.md`：這兩份文件開發者也當流程說明讀，讀者不同；之後實際開發中發現同樣的問題再另開 issue。
- 不把清理本機分支的方法（例如 git alias）寫進 repo：那是開發者個人的工作習慣。
- 不新增或刪除任何流程規則，也不改 ADR：判斷結果不變，只改寫法（需求 10 除外）。
- 不改其他規格、審查紀錄等歷史文件（`docs/README.md`「生命週期」）。
- 發現上面以外的問題，先回報開發者，不在這個 PR 修。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 開發者讀 `.claude/skills/feature/SKILL.md`，內容和附錄 A 相同 |
| AC2 | 開發者讀 `.claude/skills/feature/references/resume.md`，「暫停與接續」第 2 段是附錄 B 改後的文字，其他行和改前相同 |
| AC3 | 「新舊規則對照」的每一列，在新的 `feature/SKILL.md`、`resume.md` 裡都找得到，判斷結果和舊檔相同 |
| AC4 | 需求 9 的 6 項固定步驟在新檔裡仍是固定步驟，位置和需求 9 寫的相同 |
| AC5a | 背景列出的每一處引用（`.claude/`、`CLAUDE.md`、`docs/README.md`、`docs/specs/README.md`、`docs/reviews/README.md`、`docs/issues.md` 裡引用 `feature`、`resume.md` 段落的地方），在新檔都找得到同名的段落 |
| AC5b | 被用編號引用的「硬規則」第 2、4 條，規則和舊檔相同（第 2 條只多了原因） |
| AC6 | 開發者讀 `CLAUDE.md`「開發流程」，只有 5 點，沒有刪除來源分支的規則 |
| AC7 | GitHub 上有 4 個新 issue，各對應第 2～5 批，內容有需求 11 的 6 項 |
| AC8 | 這個 PR 改到的檔案只有：`.claude/skills/feature/SKILL.md`、`.claude/skills/feature/references/resume.md`、`CLAUDE.md`、新規格 |
| AC9 | 新的 `feature/SKILL.md` 裡，和舊檔不同的段落（空行除外）只有「開頭」「流程」第 2 段、「硬規則」第 2 條、「快速路徑」「文字修正的流程」；這些段落裡的編號清單，不是被用編號引用的條件，就是前面有一句排順序原因的步驟 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限、資料處理與一致性、同時操作、安全性 | 只改流程文件，不改程式行為與資料 |
| 和既有規則交會 | 其他檔案的引用由 AC5a、AC5b 涵蓋；固定步驟由 AC4 涵蓋；判斷結果不變由 AC3 涵蓋 |

## 實作計畫

1. 主 session 在核准後照需求 11 開 4 個 issue，把編號放進交付給 `feature-implementer` 的指示。
2. `feature-implementer` 從 `main` 開分支 `issue-165-skill-rewrite`。
3. 照需求 1 把附錄 A 程式碼區塊裡的內容（不含外層的 ```` 標記）寫成 `feature/SKILL.md` 全文；照需求 2 改 `resume.md` 一句。
4. 照需求 10 刪 `CLAUDE.md:31`。
5. 規格存成 `docs/specs/issue-165-skill-rewrite.md`，狀態改「已核准」，填 PR 編號。
6. 只改 `.md`，不用跑後端、前端的檢查；PR 描述加 `Closes #165`，並列出需求 11 的 4 個 issue。

主要的寫法改動（其他段落只補原因或拆句，判斷不變）：

- 「快速路徑」：條件與「符合時寫什麼」放前面；「規格階段」6 項彼此不重疊，合成一段原則；「核准後」的開發者兩種選擇寫成一句；只有「改走完整流程」的 5 步有先後（每一步要用到前一步的結果，實作要等新規格核准），保留編號清單。
- 「文字修正的流程」：一段文字拆成 5 個有先後的步驟，清單前寫原因（需求 8）。
- 「快速路徑」的 3 個條件保留編號：附錄 A 與 ADR 0018 用「條件 2」「條件 1、2」引用（需求 7）。
- 開始前的檢查、硬規則第 2 條：補上 ADR 0014 的原因。
- 「判斷等級」「重大架構決策」「回報」「清理暫存」「取消」沒有修改，不補原因（需求 6）。
- `resume.md`：恢復步驟不動；在步驟前補一句以暫存檔為單位的原因（ADR 0010）。

## 新舊規則對照

「舊」是改寫前 `main` 上的行號；「新」是附錄 A 的段落，以及 `resume.md` 改寫後的段落。

| # | 舊（檔案:行號） | 情況 → 結果 | 新 |
|---|---|---|---|
| 0 | feature:1-5 | frontmatter（`name`、`description`、`disable-model-invocation: true`） | frontmatter，不變 |
| 1 | feature:11 | 主 session 不寫程式，文字修正除外 | 開頭第 1 段 |
| 2 | feature:11 | 規格交給 `specification-reviewer`（快速路徑除外），實作交給 `feature-implementer`，實作後交給 `acceptance-reviewer` | 開頭第 1 段 |
| 3 | feature:11 | agent 看不到對話 → 規格寫到不看對話也能照做 | 開頭第 1 段 |
| 4 | feature:15 | 進入每個步驟前先載入該步驟的 skill | 「流程」第 1 段 |
| 5 | feature:17 | 草稿資料夾有這次的暫存檔 → 用需求問答格式問接續或刪掉重來；回答前不把內容當已確認 | 「流程」第 2 段 |
| 6 | feature:19-25 | 5 個步驟與各自載入的 skill | 「流程」表，不變 |
| 7 | feature:27 | 暫停、接續、暫存檔遺失 → 讀 `resume.md` | 「流程」表下一句 |
| 8a | feature:32 | 硬規則適用於任何階段、任何等級 | 「硬規則」第 1 句，不變 |
| 8 | feature:34-39 | 硬規則 1～6 的內容與編號 | 「硬規則」1～6，第 2 條補原因 |
| 9 | feature:43-49 | 依碰到什麼判斷、不依改動大小；先看高風險，再看文字修正，都不符合是一般；等級的定義與表 | 「判斷等級」表，不變 |
| 10 | feature:51-55 | 不確定取較高；可能改行為的不是文字修正；高風險看行為或保證；只升不降；等級只調整深度 | 「判斷等級」表下 5 點，不變 |
| 11 | feature:59、63-66 | 快速路徑只簡化規格階段，其他沿用一般流程，原因與放棄的做法見 ADR 0018；一般 ＋ 3 個條件都符合 → 快速路徑；改動大小不是條件 | 「快速路徑」第 1 段（ADR 0018 連結）與條件 |
| 12 | feature:67 | 符合時等級寫「一般（快速路徑：理由）」，和規格一起核准 | 「快速路徑」條件下一句 |
| 13 | feature:68-70 | 程式碼看不出來的事：業務規則 → 不符合條件 2；技術判斷 → 工程方案探索，寫進「修法」 | 「快速路徑」條件下一段的第 2 句 |
| 14 | feature:74-76 | 需求理解簡述；不建 grill、不另外確認；和短版規格同一則訊息核准一次；不做規格審查 | 「快速路徑」「規格階段」第 1 段 |
| 15 | feature:77-78 | 短版規格放 PR 描述不存 `docs/specs/`；更新 PR 描述時短版規格那段不動 | 「快速路徑」「規格階段」第 2 段 |
| 16 | feature:79 | 核准前發現有條件不符合 → 告訴開發者，改走完整流程（問答、完整規格、規格審查） | 「快速路徑」「規格階段」第 3 段 |
| 17 | feature:83 | 實作與實作審查同一般，只有交付與審查的輸入不同 | 「快速路徑」「核准後」第 1 段 |
| 18 | feature:84-86 | 核准後要改驗收條件、背景或修法 → 問開發者；這個 PR 補 → 完整流程；另開 issue → 留在快速路徑，短版規格不動 | 「快速路徑」「核准後」第 1 段 |
| 19 | feature:87-92 | 核准後改走完整流程的 5 步順序（只限核准後；核准前改走完整流程照第 16 列） | 「快速路徑」「核准後」編號清單，不變 |
| 20 | feature:93 | 只改措辭的 `nitpick` 不改短版規格 | 「快速路徑」「核准後」第 1 段 |
| 21 | feature:94 | 核准後改走完整流程後，退回快速路徑要開發者同意（只限核准後；核准前沒有這條規則） | 「快速路徑」最後一句 |
| 22 | feature:98-102 | 重大架構決策的定義、是高風險、ADR 草稿、審查才發現 | 「重大架構決策」，不變 |
| 23 | feature:106 | 文字修正：改動清單 → 核准 → 開分支自己改 → 檢查、開 PR、等 CI → 回報與清理；審查與對照表不適用 | 「文字修正的流程」1～5 步與下一句 |
| 24 | feature:108-110 | 文字修正中發現漏洞、無關的問題、會改變行為 | 「文字修正的流程」3 點，不變 |
| 25 | feature:114-119 | 回報內容與所有 open PR 的兩區 | 「回報」，不變 |
| 26 | feature:123-125 | 清理前確認；只刪表上的檔名；回報後要改從 PR 分支複製回來 | 「清理暫存」，不變 |
| 27 | feature:129-131 | 取消時術語的處理與刪暫存檔 | 「取消」，不變 |
| 28 | resume:7 | 暫停、接續直接用草稿資料夾的暫存檔 | 「暫停與接續」第 1 段，不變 |
| 29a | resume:9 | 以遺失了哪個暫存檔為單位處理，不依遺失的時間點 | 「暫停與接續」第 2 段第 1 句 |
| 29 | resume:9-16 | 暫存檔遺失的 6 個步驟 | 「暫停與接續」編號清單，不變；前面補原因 |
| 30 | resume:18-34 | 暫存檔表與重跑審查的處理 | 「暫存檔表」，不變 |
| 31 | resume:36-38 | 部分改動的完成狀態 | 「部分改動的完成狀態」，不變 |

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | 取出規格附錄 A 程式碼區塊裡的內容（不含外層的 ```` 標記），和 `.claude/skills/feature/SKILL.md` 做 `diff` | 沒有差異 |
| AC2 | `git diff origin/main -- .claude/skills/feature/references/resume.md` | 只有第 9 行改變，新內容和附錄 B 改後的文字相同 |
| AC3 | 逐列讀「新舊規則對照」，在新檔的「新」欄位置找對應文字 | 每一列都找得到，結果和「情況 → 結果」欄相同 |
| AC4 | `grep -n "核准前只寫草稿資料夾\|明確表示核准\|照 CLAUDE.md「漏洞」\|不可合併 PR\|暫存檔表列出的檔名" .claude/skills/feature/SKILL.md`；讀 `resume.md`「暫停與接續」 | 5 個字串都找得到，前 4 個在「硬規則」第 2、3、5、6 條，最後一個在「清理暫存」；另外「流程」第 2 段（暫存檔表列出的檔名）與「文字修正的流程」（照 CLAUDE.md「漏洞」）各多 1 行；`resume.md`「暫停與接續」有 6 個編號步驟 |
| AC5a | 跑下面「AC5a 的指令」，逐行對照 | 結果和背景列出的引用相同；每一個段落名稱在新的 `feature/SKILL.md` 或 `resume.md` 都有同名的 `##` 標題；暫存檔表、恢復步驟在 `resume.md`「暫存檔表」「暫停與接續」 |
| AC5b | 對照 `git show origin/main:.claude/skills/feature/SKILL.md` 的第 35、37 行與新檔「硬規則」第 2、4 條 | 第 4 條文字相同；第 2 條只多了冒號後的原因句，其他文字相同 |
| AC6 | 讀 `CLAUDE.md`「開發流程」；`grep -n "來源分支" CLAUDE.md` | 編號只到 5；grep 沒有結果 |
| AC7 | `gh issue view <每個編號> --json title,body` | 4 個 issue 各對應一批，內容有需求 11 的 6 項 |
| AC8 | `git diff --stat origin/main...HEAD` | 只列出 AC8 的 4 個檔案 |
| AC9 | `git diff origin/main -- .claude/skills/feature/SKILL.md`，讀每一個有改動的段落 | 改動只在 AC9 列的段落（刪掉的空行除外）；改動段落所在的節裡，編號清單只有 4 組：「硬規則」6 條（其他檔案用「第 2 條」「第 4 條」引用）、「快速路徑」的 3 個條件（用「條件 2」引用）、核准後改走完整流程的 5 步、「文字修正的流程」的 5 步；後兩組前面各有一句原因 |

AC5a 的指令（在 PR 分支上跑）：

```bash
git grep -noE "(feature(/SKILL\.md)?\`? ?|/feature\` ?|resume\.md\`? ?)「[^」]+」(第 ?[0-9] ?條)?|resume\.md\` 的(暫存檔表|恢復步驟)" HEAD -- .claude CLAUDE.md docs/README.md docs/specs/README.md docs/reviews/README.md docs/issues.md ':!.claude/skills/feature/SKILL.md' ':!.claude/skills/feature/references/resume.md'
```

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無

## 附錄 A：`.claude/skills/feature/SKILL.md` 全文

````markdown
---
name: feature
description: 開發新功能或行為變更：需求問答、寫規格交給開發者核准、交給 agent 實作與審查。用 /feature <需求> 執行。
disable-model-invocation: true
---

# 功能開發流程

需求：$ARGUMENTS

你是提需求、負責驗收的一方，不自己寫程式（等級為「文字修正」除外）。規格核准前交給 `specification-reviewer` 審查（快速路徑除外，見「快速路徑」），實作交給 `feature-implementer`，實作後交給 `acceptance-reviewer` 審查。這三個 agent 都看不到這段對話，所以規格要寫到不看這段對話也能照著做。分工的原因見 `docs/decisions/0001-separate-feature-roles.md`、`docs/decisions/0005-specification-review.md`。

## 流程

進入每個步驟前，先用 Skill 工具載入該步驟的 skill，照它的指示做。

開始前，先看草稿資料夾（`.drafts/`）裡有沒有這次的暫存檔（`references/resume.md` 暫存檔表列出的檔名）。有的話，用 `clarify-requirements`「需求問答」的格式問開發者：接續（照 `references/resume.md`「暫停與接續」），還是刪掉重來（照「清理暫存」的方式刪）。這些檔案可能是上次中斷、漏刪或 PR 被關閉後留下的，所以開發者回答前，不把裡面的內容當作已確認的決定（`docs/decisions/0014-drafts-folder.md`）。

| 步驟 | 做什麼 | 載入 |
|---|---|---|
| 1. 判斷等級 | 自己讀程式碼，依本檔「判斷等級」判斷 | 本檔 |
| 2. 需求確認 | 簡述需求理解、需求問答（只問會改變需求、行為或範圍的事）、工程方案探索 | clarify-requirements |
| 3. 規格 | 寫規格草稿、規格審查、交給開發者核准（文字修正不寫規格，見「文字修正的流程」；快速路徑不做規格審查，見「快速路徑」） | `write-spec` |
| 4. 實作與審查 | 開發者核准後：交給 `feature-implementer` 實作，再交給 `acceptance-reviewer` 審查，處理發現 | `implement-and-review` |
| 5. 回報 | 見本檔「回報」 | 本檔 |

暫停、接續、草稿資料夾裡這次的暫存檔遺失時，讀 `references/resume.md`。

## 硬規則

任何階段、任何等級都適用。

1. **不用 plan mode**，也不用 ExitPlanMode 請開發者核准（`docs/decisions/0008-grilling-without-plan-mode.md`）。開發者在 plan mode 中叫出這個流程時，先請開發者退出 plan mode：plan mode 中不能寫檔案。
2. **核准前只寫草稿資料夾**（`.drafts/`），不改 repo 裡其他檔案、不開分支：工作目錄是開發者與其他 session 共用的，未核准的內容寫在草稿資料夾以外，可能被別的 commit 帶走，取消時也要還原（`docs/decisions/0014-drafts-folder.md`）。這次開發的暫存檔都以 `<功能>-` 開頭，只建立 `references/resume.md` 暫存檔表上的暫存檔；種類與遺失時的恢復方式見同一張表。
3. **核准的定義**：開發者明確表示核准（例如「核准」）才算；提出修改、回答問題或沒有回應都不算。
4. **向開發者提問**：所有等級、所有階段都用 `clarify-requirements`「需求問答」的 ❓／➡️ 文字格式，不用 AskUserQuestion。
5. **漏洞**：照 CLAUDE.md「漏洞」。
6. **不可合併 PR**：照 CLAUDE.md「開發流程」第 5 點。

## 判斷等級

依變更**碰到什麼**判斷，不依改動大小（`docs/decisions/0007-process-depth-by-risk.md`）。先看高風險，再看文字修正，都不符合就是一般：

| 等級 | 什麼時候 | 規格 | 規格審查 | 實作審查 |
|---|---|---|---|---|
| 高風險 | 改變下面任何一項的行為或保證：資料一致性（同時操作、中途失敗後的資料狀態、既有資料讀不讀得出來或要不要轉換）；認證與授權（誰動得到哪些資料）；個資、憑證、token 的保護（不出現在 log、回應、公開的地方）；和外部系統同步的一致性與可靠性；其他安全性（輸入驗證、注入）。或屬於下面「重大架構決策」 | 完整格式；「實作計畫」另外寫放棄的做法與理由 | 最多 2 次；reviewer 另外填安全與一致性檢查表 | 直到沒有阻擋；重新審查看整個功能；reviewer 另外填安全與一致性檢查表 |
| 一般 | 其他都不符合的，例如 bug、小的行為修改、只補測試、新功能、新增 endpoint 或改 request／response 格式、改定義流程或規則的文件裡的規則（只改措辭、規則不變的是文字修正） | 完整格式，沒有內容的節可以省略（`docs/specs/README.md`「各等級的規格」）；快速路徑見「快速路徑」 | 最多 2 次；快速路徑見「快速路徑」 | 直到沒有阻擋；重新審查看修正的項目、它們的驗收條件、修正改到的程式與相關測試，以及連帶影響，不重審整個功能 |
| 文字修正 | 不改變任何程式行為，也不改任何規則：Markdown 文件、註解、錯字，以及不會被執行、也不會被測試讀到的文字。定義流程或規則的文件（skill、agent、CLAUDE.md、`docs/specs/README.md`、`docs/reviews/README.md`、`docs/README.md`、`docs/decisions/`）只限改措辭、規則不變 | 不寫規格檔；主 session 直接改 | 不做 | 不做 |

- 判斷不確定時取較高的等級。等級和理由寫在規格開頭，和規格一起核准。
- 會改變或可能改變程式行為的修改，都不是文字修正。重構、套件升級依實際影響的範圍判斷是一般或高風險。
- 高風險看的是行為或保證有沒有改變，不是用到哪個欄位或元件：例如新增一個選填欄位，舊資料沒有它也照常讀得出來，就依其他條件判斷；改既有欄位的型別或意義、要轉換既有資料，改變了一致性的保證，是高風險。
- 任何階段發現碰到更高等級的範圍，就升級，告訴開發者並補做該等級的步驟（需求問答照 `clarify-requirements`「做到一半改成較高的等級」）；只升不降，降級要開發者同意。
- 等級只調整規格與審查的深度：CLAUDE.md「完成的定義」與「開發流程」、測試要求、開發者核准，每個等級都一樣。

## 快速路徑

需求已經寫清楚、又沒有要開發者決定的事時，完整規格與規格審查多出的主要是幾輪等待與決定，所以快速路徑只簡化規格階段；實作、實作審查、核准後改規格的處理都沿用一般流程（`docs/decisions/0018-fast-path.md`）。

先照「判斷等級」判斷是一般，再同時符合下面 3 個條件，才走快速路徑；改動大小不是條件：

1. 需求（issue 內容或 `/feature` 的參數）已寫清楚現在的結果與預期的結果。
2. 沒有要開發者決定的事。
3. 不碰高風險範圍（「判斷等級」表的高風險一列）。

符合時，在規格的等級寫「一般（快速路徑：<符合 3 個條件的理由>）」，和規格一起由開發者核准。寫短版規格時遇到程式碼看不出來的事：是業務規則（要開發者決定的事），就算不符合條件 2；是技術判斷，就照 `clarify-requirements`「工程方案探索」依範圍做，結果寫進短版規格的「修法」。

**規格階段**：照 `clarify-requirements`「需求理解」簡述需求，和短版規格（格式見 `docs/specs/README.md`「快速路徑的短版規格」）放在同一則訊息，請開發者核准一次（核准的定義照「硬規則」第 3 條）。需求已經寫清楚，所以不建立 `<功能>-grill.md`，也不另外請開發者確認「已確認」清單。不做規格審查，原因見本節開頭：省下的是等待與決定，代價是規格本身的問題要到實作審查才會被發現。

短版規格放在 PR 描述，不存進 `docs/specs/`。留在快速路徑期間，每次更新 PR 描述都以目前的描述為基礎，短版規格那一段不動。

核准前發現 3 個條件有任何一個不符合：告訴開發者，改走一般的完整流程，照 `clarify-requirements`「需求問答」問答、寫完整格式的規格、做規格審查。

**核准後**：實作與實作審查和一般相同，差別只有交付與審查的輸入（見 `implement-and-review`「交付清單」「交給 acceptance-reviewer 審查」）。任何階段（實作回報、實作審查）的修正要改短版規格的驗收條件、背景或修法時，照 `implement-and-review`「規格問題的處理」問開發者：開發者決定在這個 PR 補上，就改走一般的完整流程；決定另開 issue，就留在快速路徑，短版規格不動。只改措辭、不改意思的 `nitpick` 不改短版規格。

核准後改走一般的完整流程時照下面順序做，因為每一步都要用到前一步的結果，實作也要等新的規格核准才能交辦（引用的段落在 `implement-and-review`）：

1. 主 session 以短版規格為基礎寫完整格式的規格，和短版規格不同的驗收條件照 `implement-and-review`「核准後修改規格」寫進修改紀錄。
2. 做規格審查。
3. 交給開發者核准。
4. 照 `implement-and-review`「交付清單」交給 `feature-implementer`。
5. 主 session 照 CLAUDE.md「開發流程」第 3 點，把 PR 描述裡的短版規格換成規格檔的連結。

核准後改走一般的完整流程後，要退回快速路徑需要開發者同意（等同「判斷等級」的只升不降）。

## 重大架構決策

指新增服務或外部依賴、改變模組分層、改資料庫結構或部署方式。「改資料庫結構」指新增 collection 或索引、改既有欄位的型別或意義、要轉換既有資料；新增選填欄位不算。

- 屬於重大架構決策的變更是高風險。
- 核准前寫成草稿資料夾的 ADR 草稿 `<功能>-adr-<名稱>.md`，和規格一起核准（見 `write-spec`「已確認的決定寫進規格」）。
- 審查階段才發現的，照 `implement-and-review`「發現處理表」處理。

## 文字修正的流程

核准前不能開分支（「硬規則」第 2 條），所以照順序做：

1. 在草稿資料夾的 `<功能>-spec.md` 寫改動清單：要改的檔案、改前與改後的文字、為什麼屬於文字修正。
2. 交給開發者核准（核准方式見「硬規則」）。
3. 核准後從 `main` 開分支，自己修改。
4. 跑改到範圍的檢查（只改 `.md` 時不用），開 PR、等 CI。
5. 回報等級（文字修正）、PR 連結、CI 結果，以及「回報」的「目前所有 open 的 PR」的合併狀態，並照「清理暫存」確認暫存的內容。

文字修正不改行為，沒有驗收條件要對照，所以 `implement-and-review` 的審查與「回報」的「驗收條件、測試與結果的對照表」不適用。

- 修改中發現可被利用的漏洞，照 CLAUDE.md「漏洞」。
- 發現和這次修改無關的問題，照 `implement-and-review`「發現處理表」第 8 步判斷要不要開 issue，要開的才照「開 issue 追蹤」開（沒有審查留言，來源只附 PR 連結）；不開的原因寫在給開發者的回報，「這次開了或留言了哪些 issue」旁邊。
- 修改中發現會改變程式行為（包括改了測試斷言會看到的文字），就停下來，告訴開發者，重新判斷等級，照新等級的流程從寫規格開始（照 `clarify-requirements`「做到一半改成較高的等級」先補做問答）；已經改的部分照同一節處理。

## 回報

PR 連結、等級、「驗收條件、測試與結果的對照表」（驗收條件 → 對應的測試 → 結果）、假設清單、規格修改紀錄、規格審查與實作審查留言的連結與阻擋項目的處理結果、這次開了或留言了哪些 issue、建立或沿用了哪些 advisory（只寫編號）。給開發者看的回報要附上檔案與測試的連結（`檔案:行號`），不要只寫摘要。PR 描述放同一張對照表；更新 PR 描述照 CLAUDE.md「開發流程」的方式。

回報的最後列出**目前所有 open 的 PR** 能不能由開發者決定合併，不只這次的 PR：別的 PR 可能因為這次合併而解開（例如等這個 PR 修好 CI），或因為 main 前進而出現衝突。用 `gh pr list --state open`、`gh pr checks <PR>`、`git merge-tree --write-tree origin/main origin/<分支>`（先 `git fetch origin`）逐一確認，分兩區：

- **可以決定要不要合併**：必要的 CI 都通過、和 `main` 沒有衝突、實作審查沒有阻擋項目（沒有審查留言的寫「沒有審查」）。
- **還不行**：寫出原因與下一步，例如 CI 失敗、和 `main` 衝突的檔案、仍有阻擋的項目、要等哪個 PR 先合併。

## 清理暫存

回報前確認草稿資料夾裡已確認的內容（規格、決定、術語、審查結果）都已經在規格、審查留言、ADR 或術語表裡（要寫在「術語表」的決定，在 `docs/glossary.md` 找得到就算）；文字修正沒有規格與審查留言，對照 PR 的改動與描述；還沒做完的後續動作（例如合併後要在 issue 留言），列在回報的「待辦」，不要只留在草稿資料夾。

確認完，刪掉草稿資料夾裡這次的暫存檔：只刪 `references/resume.md` 暫存檔表列出的檔名，不用「`<功能>-` 開頭」比對，避免刪到名稱開頭相同的其他功能。回報後還要修改時，照 `references/resume.md` 從 PR 分支複製回來。

## 取消

核准前開發者表示不做時，列出 `<功能>-glossary.md` 的術語（有的話），用 `clarify-requirements`「需求問答」的格式請開發者決定保留或不保留。保留：另外照「文字修正的流程」開 PR，只改 `docs/glossary.md`；開 PR 前同樣 `git fetch origin main`，對照 `origin/main` 的 `docs/glossary.md` 有沒有相同或相近的術語，有的話問開發者。核准後 PR 被關閉時不另外處理：改動只在分支上。

術語處理完，照「清理暫存」的方式刪掉這次的暫存檔。
````

## 附錄 B：`.claude/skills/feature/references/resume.md` 要改的一句

`resume.md:9`（「暫停與接續」第 2 段）由：

> 草稿資料夾裡這次的暫存檔不見了，或缺了部分時，以遺失了哪個暫存檔為單位處理，不依遺失的時間點（`docs/decisions/0010-scratchpad-loss-recovery.md`）。依序：

改成：

> 草稿資料夾裡這次的暫存檔不見了，或缺了部分時，以遺失了哪個暫存檔為單位處理，不依遺失的時間點，因為每個暫存檔都由固定的步驟產生，遺失的時間點則列舉不完（`docs/decisions/0010-scratchpad-loss-recovery.md`）。下面的步驟做錯，已核准的內容可能被推翻或憑記憶重寫，所以依序：
