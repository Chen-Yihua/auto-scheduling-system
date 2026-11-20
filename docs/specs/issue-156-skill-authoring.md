# 審查的特殊情況判斷改成原則加原因，CLAUDE.md 加 skill 寫作原則

- 狀態：已核准（2026-11-20）
- 等級：一般（改流程文件裡的規則：`CLAUDE.md`「寫作規則」新增一條、`docs/reviews/README.md` 兩段判斷順序改成原則。不改程式碼，不涉及資料一致性、認證授權、憑證保護，也不是重大架構決策）
- issue：#156
- PR：#166

## 簡短說明

`CLAUDE.md`「寫作規則」加一條：改 skill、agent 時照 Anthropic〈Skill authoring best practices〉，而且不另外建立情境驗證。`docs/reviews/README.md` 裡「暫存檔遺失時」與規格「不做」的判斷順序，改成一兩句原則加原因，小節改名「特殊情況的判斷」。逐檔重寫 skill、agent 另外開 issue。

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/156

**問題**：開發者讀或修改 `/feature`、`/issue` 用到的規則時，規則寫得像法條；每遇到一個新情況就加一條，審查又容易找到「規則沒寫到」的地方，規則越寫越長。

**實際案例**：`docs/reviews/README.md:54-67`「暫存檔遺失與規格「不做」的判斷」：

- 暫存檔遺失時有 2 步判斷順序，外加「這條只限暫存檔遺失，不擴大到其他流程」（`docs/reviews/README.md:56-60`）。
- 規格「不做」有 6 步判斷順序（`docs/reviews/README.md:61-67`）：
  1. 是漏洞：照「漏洞」。
  2. 實作做了「不做」排除的改動：列成發現。
  3. 查到「不做」依據的事實不成立（包括和規格審查的查證紀錄不同）：列成發現。
  4. 規格審查時認為不該列在「不做」，沒有新查到的事實：列成發現。
  5. 「不做」寫明不處理的：寫在「已接受的風險」，比 main 退步也一樣。
  6. 都不符合：照一般的分類判斷。

**和這次相關的現況**：

- 第 1 步的處理方式和上面的「漏洞」小節（`docs/reviews/README.md:47-52`）重複，但「漏洞優先於『不做』」這個先後只寫在第 1 步，「漏洞」小節沒有寫；#155（PR #164，已合併）已規定漏洞的阻擋照「阻擋」判斷，不一律阻擋。
- 小節標題混用三個名稱：小節叫「暫存檔遺失與規格「不做」的判斷」，項目叫「暫存檔遺失時」，結果寫進報告欄位「已接受的風險」。「已接受的風險」也是 `docs/README.md` 術語表的詞（`docs/README.md:83-84`）。
- 引用這一節的地方：`docs/reviews/README.md:123`、`.claude/agents/acceptance-reviewer.md:26`、`:39`、`.claude/agents/specification-reviewer.md:34`、`:49`。
- #155 的規格 `docs/specs/issue-155-review-labels.md` AC8（`:137`）要求判斷順序保留；這次取代這一條。
- #157（還開著）會改 `feature`「判斷等級」並新增 ADR，和這次改的檔案不重疊。
- `CLAUDE.md:78-86`「寫作規則」目前有 5 條；第 5 條規定有先後順序的條件寫成編號清單，不寫成「原則＋例外＋例外的例外」。
- 一般做法（2026-11-20 讀過原文）：
  - Anthropic〈[Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)〉：「Default assumption: Claude is already very smart」「Only add context Claude doesn't already have」；「Match the level of specificity to the task's fragility and variability」，操作容易出錯、一致性很重要、必須照特定順序時才寫具體步驟；「Create evaluations BEFORE writing extensive documentation」。這份文件沒有「每條規則寫原因」的一般建議，只要求說明腳本裡的設定值。
  - `anthropics/skills` 的 [`skill-creator`](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)：「Try hard to explain the **why** behind everything you're asking the model to do」；看到自己寫全大寫的 ALWAYS、NEVER 或很死板的結構時，改成說明原因。

## 需求

1. `CLAUDE.md`「寫作規則」新增第 6 條，開頭那句改成「寫文件時照下面 6 條」。第 6 條全文：

   > 6. 改 skill、agent 時，照 Anthropic〈[Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)〉：只寫 Claude 不知道的事，只有容易出錯、出錯難挽回的操作寫固定步驟；照 `anthropics/skills` 的〈[skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)〉：說明重要指示背後的原因。這個 repo 不另外建立改 skill 時的情境驗證（Anthropic 建議的「Build evaluations first」）：改完的 skill、agent 直接在之後的實際開發中使用，發現規則遺漏、誤判或流程退化時，依具體案例修正。

2. `docs/reviews/README.md` 的小節「暫存檔遺失與規格「不做」的判斷」改名「特殊情況的判斷」。
3. 「特殊情況的判斷」底下有兩項，開頭分別是「**暫存檔遺失時**」和「**規格「不做」**」。
4. 「暫存檔遺失時」換成：

   > - **暫存檔遺失時**：`.claude/skills/feature/references/resume.md` 的恢復步驟處理不了，而且會讓已核准的決定被推翻、正式文件被憑記憶重寫，或開發者沒被告知決定或成果遺失時，列成發現。其他遺失的情況寫在報告的「已接受的風險」，不要求替每種情況加規則，因為遺失的時間點列舉不完，每補一個情況，審查就會找到下一個（ADR 0010）。

5. 規格「不做」換成：

   > - **規格「不做」**：「不做」是開發者依當時已知的事實做的決定，所以只有三種情況列成發現：實作做了「不做」排除的改動、查到「不做」依據的事實不成立（包括實際後果和「不做」寫的不同，或和規格審查的查證紀錄不同，例如實作新增了會產生這個情況的依賴），或規格審查時認為某個情況不該列在「不做」。前兩種是決定的前提變了，第三種是規格還沒核准、決定還能改。其他「不做」寫明不處理的情況，寫在報告的「已接受的風險」。

6. 兩項都不提漏洞與阻擋：漏洞照同一份文件的「漏洞」，阻擋照「阻擋」。
7. 「漏洞」小節（`docs/reviews/README.md:47-52`）加一句，保留舊第 1 步的先後：

   > - 漏洞不論「特殊情況的判斷」怎麼寫，都照這一節處理。
8. 「已接受的風險」只當作審查報告的欄位名稱，不用來命名判斷規則。
9. 引用舊名稱的地方統一寫成「特殊情況的判斷」：
   - `docs/reviews/README.md:123`、`.claude/agents/acceptance-reviewer.md:39`、`.claude/agents/specification-reviewer.md:49`：前半句「「分類」的「暫存檔遺失時」」改成「「特殊情況的判斷」的「暫存檔遺失時」」；後半句「另見「分類」的「暫存檔遺失與規格「不做」的判斷」」改成「另見「特殊情況的判斷」」；兩個 agent 檔的原文在「另見」後面有路徑（「另見 `docs/reviews/README.md`「分類」的…」），保留路徑，改成「另見 `docs/reviews/README.md`「特殊情況的判斷」」。
   - `.claude/agents/acceptance-reviewer.md:26`、`.claude/agents/specification-reviewer.md:34`：「照 `docs/reviews/README.md`「分類」的「暫存檔遺失時」判斷」改成「照 `docs/reviews/README.md`「特殊情況的判斷」的「暫存檔遺失時」判斷」。
10. `docs/specs/issue-155-review-labels.md` 的「狀態」改成「部分被 [審查的特殊情況判斷改成原則加原因，CLAUDE.md 加 skill 寫作原則](issue-156-skill-authoring.md) 取代（AC8）」，其他內容不改。
11. 開一個新 issue（照 `docs/issues.md`）：照 `CLAUDE.md`「寫作規則」第 6 條逐檔重寫 skill、agent、`references/`，一次改一兩個檔。issue 列出要寫固定步驟的操作：
    1. 漏洞：照 `CLAUDE.md`「漏洞」與 `docs/reviews/README.md`「漏洞」（#155 的規則：阻擋照「阻擋」判斷，不一律阻擋）。
    2. `git add` 只加這次要 commit 的檔案。
    3. 合併由開發者決定。
    4. 不讀、不複製、不改 `.env`。
    5. 刪除（檔案、分支、`docs/` 永久保存的文件；範圍列在 issue 的「待決定」）。
    6. 開發者明確表示核准才算核准。
    7. 核准前只寫草稿資料夾。

    issue 的「待決定」另外列出：
    1. 「刪除」的具體範圍。
    2. 有先後順序、但不算容易出錯的判斷（例如 `implement-and-review`「發現處理表」），照寫作規則第 5 條寫成編號清單，還是照第 6 條改成原則。
    3. agent 會讀的規則文件（例如 `docs/reviews/README.md`、`docs/specs/README.md`）算不算第 6 條的範圍。

## 不做

- 不重寫其他 skill、agent、`references/`：留給需求 11 的 issue，避免和 #157 同時大改 `feature` skill。
- `CLAUDE.md` 不新增「容易出錯操作」的分類、清單或判斷流程：第 6 條只寫原則，固定步驟的清單只放在需求 11 的後續 issue。
- 不改 #155 已經定好的審查制度（標籤、阻擋、漏洞、報告格式、處理）。需求 7 只把舊第 1 步的先後搬到「漏洞」小節，漏洞的定義、標法與處理都不變。
- 不改 ADR 0010：「審查豁免」的判斷結果沒變，只是寫法從編號步驟改成一句話。
- 不改 `docs/README.md` 術語表的「已接受的風險」：定義本來就是報告欄位的意思。
- 不改其他規格、審查紀錄等歷史文件裡的舊小節名稱（`docs/README.md`「生命週期」：永久保存的文件不改寫）。
- 發現上面決定以外的問題，先回報開發者，不在這個 PR 修。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 開發者讀 `CLAUDE.md`「寫作規則」，第 6 條指向 Anthropic〈Skill authoring best practices〉與 `anthropics/skills` 的〈skill-creator〉，寫明只寫 Claude 不知道的事、只有容易出錯且難挽回的操作寫固定步驟、說明重要指示背後的原因 |
| AC2 | 同一條寫明這個 repo 不另外建立情境驗證，以及改用實際開發中發現的案例修正 |
| AC3 | 開發者讀 `docs/reviews/README.md`「特殊情況的判斷」，「暫存檔遺失時」與規格「不做」各是一兩句原則加原因，沒有編號的判斷順序 |
| AC4 | 舊判斷順序裡每一種情況，在新寫法下要不要列成發現、寫在哪裡都和改前相同；舊第 1 步（漏洞優先）改由「漏洞」小節的一句寫明；拿掉的句子只有下列 4 處，拿掉後結果不變：「比 main 退步也一樣」（「寫明不處理」已包含）、「這條只限暫存檔遺失，不擴大到其他流程」（項目標題已限定範圍）、恢復依據裡的「暫存檔表與部分改動的完成狀態」（`resume.md` 本身包含）、舊第 4 步的「沒有新查到的事實」（有新事實時屬於第二種，本來也列成發現） |
| AC5 | 「特殊情況的判斷」的兩項都沒有定義漏洞或阻擋 |
| AC6 | `.claude/`、`CLAUDE.md`、`docs/reviews/README.md`、`docs/README.md` 裡找不到舊小節名稱「暫存檔遺失與規格「不做」的判斷」；需求 9 的 5 處引用都寫成「特殊情況的判斷」 |
| AC7 | `docs/reviews/README.md` 裡「已接受的風險」只出現在報告欄位的意思，不當作小節或規則的名稱 |
| AC8 | `docs/specs/issue-155-review-labels.md` 的狀態是部分被這份規格取代（AC8），其他行和改前相同 |
| AC9 | 有一個新 issue 追蹤逐檔重寫 skill、agent，列出需求 11 的 7 項固定步驟，漏洞那一項寫的是 #155 的規則 |
| AC10 | 這個 PR 改到的檔案只有：`CLAUDE.md`、`docs/reviews/README.md`、兩個 reviewer agent、`docs/specs/issue-155-review-labels.md`、新規格 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限、資料處理與一致性、同時操作、安全性 | 只改流程文件，不改程式行為與資料 |
| 和既有規則交會 | 漏洞與阻擋由 AC5 涵蓋（照既有「漏洞」「阻擋」）；暫存檔恢復步驟（`resume.md`）不改；判斷結果不變由 AC4 涵蓋 |

## 實作計畫

1. 從 `main` 開分支 `issue-156-skill-authoring`。
2. `CLAUDE.md`：照需求 1 改「寫作規則」。
3. `docs/reviews/README.md`：照需求 2–5 換掉 `:54-67` 整節；照需求 7 在「漏洞」小節加一句；照需求 9 改 `:123`。
4. 兩個 reviewer agent：照需求 9 改 4 行引用，其他行不動。
5. `docs/specs/issue-155-review-labels.md`：照需求 10 只改狀態行。
6. 規格存成 `docs/specs/issue-156-skill-authoring.md`，狀態改「已核准」，填 PR 編號。
7. 照需求 11 開 issue，把編號寫進 PR 描述。
8. 只改 `.md`，不用跑後端、前端的檢查；PR 描述加 `Closes #156`。

為什麼新寫法不是「原則＋例外」（`CLAUDE.md`「寫作規則」第 5 條）：舊第 1 步的先後（漏洞優先）移到「漏洞」小節寫一次（需求 7），剩下的條件彼此不重疊，沒有先後順序，所以寫成「只有這三種情況列成發現，其他寫在已接受的風險」，不用編號清單。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | 讀 `CLAUDE.md`「寫作規則」 | 開頭寫「6 條」；第 6 條和需求 1 的全文相同，兩個連結分別是 `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices`、`https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md`；沒有「每條規則寫原因」 |
| AC2 | 同上 | 第 6 條有「不另外建立改 skill 時的情境驗證」與「依具體案例修正」 |
| AC3 | 讀 `docs/reviews/README.md`「特殊情況的判斷」 | 兩項的內容分別和需求 4、5 相同；沒有 `1.` 開頭的編號行 |
| AC4 | 逐項對照背景列出的舊步驟 | 暫存檔：處理不了且有三種風險 → 發現；其他 → 已接受的風險；舊 2 → 發現（第一種）；舊 3 → 發現（第二種，括號寫明實際後果不同、查證紀錄不同）；舊 4 → 發現（第三種）；舊 5 → 已接受的風險；舊 6 → 不屬於這一節，照一般分類；舊 1 → 「漏洞」小節有需求 7 那一句 |
| AC5 | 讀「特殊情況的判斷」兩項的文字 | 沒有「漏洞」「阻擋」兩個詞 |
| AC6 | `grep -rn "暫存檔遺失與規格" .claude CLAUDE.md docs/reviews/README.md docs/README.md` | 沒有結果；`grep -rn "特殊情況的判斷" .claude docs/reviews/README.md` 找到需求 9 的 5 行（3 行各兩處）與小節標題；`grep -rn "「分類」的「暫存檔遺失時」" .claude docs/reviews/README.md` 沒有結果 |
| AC7 | `grep -n "已接受的風險" docs/reviews/README.md` | 每一處都是「寫在報告的『已接受的風險』」或報告格式裡的欄位，沒有 `#` 開頭的標題 |
| AC8 | `git diff origin/main -- docs/specs/issue-155-review-labels.md` | 只有狀態那一行改變 |
| AC9 | `gh issue view <新編號> --json body` | 內容有需求 11 的 7 項；漏洞那項寫阻擋照「阻擋」判斷 |
| AC10 | `git diff --stat origin/main...HEAD` | 只列出 AC10 的 6 個檔案 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
