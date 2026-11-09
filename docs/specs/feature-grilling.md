# `/feature` 不用 plan mode，標準、高風險先做需求問答

- 狀態：已核准
- 等級：標準（改 `/feature`、`/issue` 的流程規則，刪除一個 skill；不改程式碼。不涉及安全、資料一致性，也不是重大架構決策）
- PR：#67

## 背景

`/feature-grill`（實驗）在 `/feature` 寫規格前多一節 grilling 問答：把需求畫成決策樹，一輪問完所有前提已定的問題，決定編成 Context 項。唯一的探索性紀錄（`docs/experiments/feature-grill/records/staged-tasks-feature-grill.md`）裡，問答帶出了「階段之間強制先後順序」這類會大幅改變範圍的決定；刪除與失敗處理的決定問得很完整。紀錄的 8 項 Missing AC 中，3 項來自 plan mode 中補問、沒有回到決策樹的決定（R1#2、R1#4、R1#5），1 項是兩個決定之間的交互作用沒有追問（R1#6），1 項是 agent 自行推導的假設（R1#8），3 項沒問到或答案不完整（R1#3、R2#1、R2#2）。紀錄也記下 plan mode 只能用選單（AskUserQuestion）提問。

實驗 README 原本規定「實驗結束、開發者看過結果並決定前，不整合進正式流程」，也還沒做 `/feature` 對照的比較實驗。開發者在 2026-11-09 決定提前結束實驗，把問答併進 `/feature`，只用在標準與高風險（輕量、文字修正範圍小，問答的成本大於收益）；同時決定整個 `/feature` 不再使用 plan mode，任何時候的提問都和 grilling 一樣用文字格式，避開 plan mode 只能用選單提問的限制。這也解除了 PR #57 之後「流程凍結、不改規則」的約定（由開發者明確要求）。

## 需求

1. **不用 plan mode**：`/feature`、`/issue` 全程不進 plan mode，也不用 ExitPlanMode 請開發者核准。
   - 規格草稿寫在 scratchpad 的 `<功能>-spec.md`（文字修正寫改動清單：要改的檔案、改前與改後、為什麼是文字修正）。
   - 核准前只寫 scratchpad（規格草稿、`<功能>-grill.md`、重大架構決策的 ADR 草稿 `<功能>-adr-<名稱>.md`、審查報告原文；ADR 草稿核准後才存進 `docs/decisions/`，規格審查時把它的路徑也交給 `specification-reviewer`），不改 repo 的檔案、不開分支。
   - 交給開發者核准時，訊息附上草稿路徑與審查摘要；開發者明確表示核准（例如「核准」）才算核准，提出修改、回答問題或沉默都不算。
2. **順序**：讀程式碼、判斷等級 → 標準、高風險做需求問答，開發者確認 Context 項 → 寫規格草稿 → 規格審查 → 開發者核准。輕量、文字修正判斷完等級直接寫草稿。
3. **問答規則**從 `/feature-grill` 第 0 節搬進 `/feature`，意思不變：決策樹與「前沿」、每輪格式（❓／➡️）、「是」等於接受建議、「需要你選擇」的題目、事實自己查、決定交給開發者、需要看畫面的題目、不設題數上限與收尾、前沿空了之後先讀規格會碰到的程式碼、整理 Context 項請開發者確認、「新的決定一律回到決策樹」（含影響檢查與標上產生階段）。保留 mattpocock/skills 的出處與授權說明；拿掉「plan mode 會讓你急著產出計畫」這類以 plan mode 為前提的說明。
4. **所有等級、所有階段向開發者提問都用 ❓／➡️ 的文字格式**（包括規格審查與實作審查後的「規格問題的處理」），不用 AskUserQuestion。
5. `/feature-grill` 第 1–4 節差異表中仍適用的規則併進 `/feature`，適用於標準、高風險（包括中途升級的）：
   - 寫規格時發現漏掉的決定、規格審查與核准後的規格問題：照「新的決定一律回到決策樹」；修改紀錄的「原因」寫 C 編號（所有等級都寫，見需求 12）。
   - 規格內容：開發者決定的 Context 項寫進需求、不做或 AC；「假設」只放開發者交給你決定的 Context 項，以及寫規格時另外做的判斷。寫規格時碰到需要開發者決定的業務規則，回到決策樹，不寫成假設。`/feature` 現在「規格內容」的「只有無法合理假設、而且會影響整體方向的問題才先問」限定在輕量。
6. **中途升級**，從輕量或文字修正升級成標準或高風險時（標準升高風險不重做問答，新的決定照「新的決定一律回到決策樹」）：
   - 核准前（寫規格、規格審查）：補做問答，再改寫草稿。
   - 文字修正修改中發現會改行為：補做問答，再照新等級寫規格；已改的內容保留、不還原，問答與寫規格期間不再繼續修改，併進新規格的實作計畫。
   - 規格核准後（實作回報、實作審查）：不補做問答，之後的新決定照「新的決定一律回到決策樹」。
7. `/issue`：標準、高風險的 issue 也做問答。issue 裡的現象與程式狀態可以當作查到的事實（仍要讀程式碼確認）；「建議的驗收條件」「修法參考」要在問答裡當成題目（附建議答案）問開發者，不直接編成已決定的 Context 項。
8. **Context 與 Frontier**（取代「已決定事項」與 D 編號，概念取自 grilling）：在 `/feature` 定義一次，「D 項」「已決定事項」這些舊名稱不再使用，第一次出現就寫清楚定義：
   - **Context**：開發者確認過的資訊，也就是開發者回答的決定，以及開發者明確交給你決定的事。每項編號 C1、C2…，欄位：內容、決定者（開發者決定／開發者交給你決定）、來源（哪一題，Qn）、前提（依賴哪些 C 項，沒有寫「無」）、產生階段（問答、寫規格、規格審查、實作回報、實作審查；文字修正是「改動清單」或「修改中」）、寫進哪裡（規格的哪一節或哪條 AC；文字修正寫「改動清單」）。從程式碼、文件查到的事實不放進 Context，寫進規格的「背景」。
   - **Frontier**：從目前的 Context 推出、前提都已確認、現在就能問的問題，加上還沒問到的分支。題目編號 Q1、Q2…，整個功能連續編號，不每輪重來。
   - 兩者寫在同一份 scratchpad 檔 `<功能>-grill.md`（「Context」「Frontier」兩節），每輪問完更新；取代 `<功能>-decisions.md`。
   - 所有等級都用（輕量、文字修正沒有多輪問答，但問開發者的題目與回答一樣記進這份檔案）。
9. **清理暫存**：沒有 plan 檔可刪。第 4 節回報前確認 scratchpad 裡已確認的內容（規格、決定、審查結果）都已在規格、審查紀錄或 ADR；還沒做完的後續動作列在回報的「待辦」。`docs/README.md`「生命週期」的暫存列與 `docs/specs/README.md`「各等級的規格」的「草稿是 plan mode 的 plan 檔」同步改。
10. 刪除 `.claude/skills/feature-grill/`。`docs/experiments/feature-grill/README.md`：開頭改成指向結論；「探索性實驗（目前階段）」「比較實驗」「紀錄的提交」標成已結束、保留原文；新增「結論」：結束日期、開發者決定提前結束、證據的限制（只有一筆探索性紀錄、沒有比較實驗）、整合後的規則位置（`/feature` 第 1 節、ADR 0008），以及 `/feature-grill` 最後一版在 commit `23c56c9` 的 `.claude/skills/feature-grill/SKILL.md`（TEMPLATE 與 records 對它的引用從這裡找）。
11. 新增 ADR 0008（問答與不用 plan mode），ADR 清單加一列；ADR 0007 狀態行標出「文字修正在 plan mode 列改動」被 0008 取代，內文不變。ADR 0008 也寫明 Context／Frontier 取代 D 項的理由。
12. 規格核准後的修改紀錄，所有等級都在「原因」寫 C 編號。
13. `/issue` 第 1 節（讀 `/feature` 之前）向開發者提問，例如參數沒有 issue 編號、issue 已關閉，也用 `/feature` 的 ❓／➡️ 文字格式。
14. 第 4 節「清理暫存」：文字修正沒有規格與審查紀錄，改成對照 PR 的改動與描述。

## 不做

- 不搬實驗紀錄的填寫規則（起始 commit、時間、token 計算、實驗紀錄檔）與「背景加一行問答輪數」進 `/feature`。
- 不改 `docs/experiments/feature-grill/` 的 TEMPLATE 與 records（`docs/README.md`「生命週期」：實驗紀錄不為新規則修改）。
- 不改既有規格、審查紀錄、ADR 的內文（例如 `docs/specs/workflow-levels.md` 的「不改 `/feature-grill`」、ADR 0002 提到的 plan 檔是當時的紀錄）。
- 不改等級的定義與各等級的審查深度、輪數。
- 不改程式碼、不新增其他 skill 或 agent；不改 Claude Code 的設定（plan mode 本身仍可由開發者自行使用，只是流程不依賴它）。

## 假設

1. 判斷等級需要先讀程式碼，所以在問答前進行；問答第一輪開頭寫出暫定等級與理由，等級仍和規格一起核准。
2. 輕量、文字修正也用 Context 檔與 C 編號（欄位值見需求 8）：審查紀錄與修改紀錄能用同一種方式引用，不需要兩套定義。
3. 草稿放 scratchpad、不放 `~/.claude/plans/`：不用 plan mode 後，plan 檔沒有作用；scratchpad 不 commit，和 `<功能>-grill.md`、審查報告原文放在一起。
4. 開發者在 plan mode 中叫出 `/feature` 時，agent 只能讀、不能寫 scratchpad，流程請開發者先退出 plan mode。

## 驗收條件

| # | 條件 | 類型 |
|---|---|---|
| AC1 | 照 `/feature` 或 `/issue` 開發時，流程不要求進 plan mode 或用 ExitPlanMode；規格草稿（文字修正是改動清單）寫在 scratchpad 的 `<功能>-spec.md`，重大架構決策的 ADR 草稿寫在 scratchpad、核准後才存進 `docs/decisions/`；開發者明確表示核准前，只寫 scratchpad，不改 repo 的檔案、不開分支 | 使用者行為（用 agent 的開發者） |
| AC2 | 標準、高風險的順序是：判斷等級 → 需求問答 → 開發者確認 Context 項 → 寫規格草稿 → 規格審查 → 核准；確認 Context 項前不寫規格草稿 | 使用者行為 |
| AC3 | 輕量、文字修正不做需求問答；除了 AC1 的草稿位置與核准方式、AC4 的提問格式、已決定事項用 C 編號與同一組欄位，流程和現在一樣 | 不變條件 |
| AC4 | 所有等級、所有階段（包括 `/issue` 第 1 節讀 `/feature` 之前的提問）向開發者提問都用 ❓／➡️ 的文字格式；`/feature`、`/issue` 不再要求用 AskUserQuestion | 不變條件 |
| AC5 | `/feature-grill` 第 0 節的每一條問答規則（需求 3）與 mattpocock/skills 的出處、授權說明都在 `/feature` 找得到，意思不變；實驗專用的規則（起始 commit 與時間、token、實驗紀錄、背景的問答輪數行）不在 `/feature` 裡 | 不變條件 |
| AC6 | 標準、高風險（包括中途升級的）在寫規格、規格審查、實作回報、實作審查任何階段出現需要開發者決定的事時，流程要求編成新 Context 項並標上產生階段、做影響檢查、既有 Context 項被改變時重新問開發者；核准後的修改紀錄寫 C 編號 | 不變條件 |
| AC7 | 做過問答的變更：開發者決定的 Context 項寫在需求、不做或 AC；「假設」只有開發者交給你決定的 Context 項與寫規格時另外做的判斷；寫規格時碰到需要開發者決定的業務規則，流程要求回到決策樹 | 不變條件 |
| AC8 | 從輕量或文字修正升級成標準或高風險時，照需求 6 的三種情況處理；標準升高風險不重做問答 | 使用者行為 |
| AC9 | `/issue` 依同一個等級規則決定要不要問答；標準、高風險的 issue 裡「建議的驗收條件」「修法參考」在問答中當成附建議答案的題目問開發者，不直接編成已決定的 Context 項 | 不變條件 |
| AC10 | Context 檔的欄位只定義在 `/feature`（需求 8），`/feature`、`/issue`、`specification-reviewer` 對它的描述彼此一致 | 不變條件 |
| AC11 | `.claude/`、CLAUDE.md、`docs/README.md`、`docs/specs/README.md`、`docs/reviews/README.md` 沒有把 plan mode、plan 檔、ExitPlanMode 當成流程的一部分（歷史文件除外，見 AC14） | 不變條件 |
| AC12 | repo 裡沒有 `.claude/skills/feature-grill/`；實驗 README 的「結論」寫出結束日期、開發者決定提前結束、證據的限制、整合後規則的位置，以及 `/feature-grill` 最後一版所在的 commit | 使用者行為（之後讀實驗的開發者） |
| AC13 | ADR 0008 寫出背景（含證據的限制與 plan mode 的提問限制）、決定、放棄的做法（所有等級都問、繼續實驗到比較完成、保留兩個入口、保留 plan mode 只在問答時退出）；ADR 清單有這一列；ADR 0007 只改狀態行 | 不變條件 |
| AC14 | 所有 skill、agent、文件引用的路徑與節名稱都存在；歷史文件（`docs/specs/`、`docs/reviews/`、既有 ADR、實驗的 TEMPLATE 與 records，以及實驗 README 標成已結束的節）對 `/feature-grill`、plan 檔的引用除外 | 不變條件 |
| AC15 | `/feature` 定義 Context 與 Frontier（需求 8），第一次出現就寫清楚；Context 只有開發者確認過的資訊，查到的事實寫在規格背景；Q 編號整個功能連續；`.claude/`、`docs/README.md`、`docs/specs/README.md`、`docs/reviews/README.md` 不再把「D 項」「已決定事項」「`<功能>-decisions.md`」當成現行規則 | 不變條件 |
| AC16 | 所有等級的規格修改紀錄都寫 C 編號；文字修正的「清理暫存」對照 PR 的改動與描述 | 不變條件 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中、空資料、未登入／無權限 | 只改流程文件，沒有畫面與 API |
| 失敗 | 流程中途的升級由 AC8 涵蓋；其他失敗沿用既有規則 |
| 資料處理、併發 | 不碰資料 |
| 安全性 | 不改「漏洞的處理」與公開資訊邊界；核准前不改 repo 的保證改由流程規則維持（AC1），不再依賴 plan mode 的工具限制 |

## 實作計畫

和這份規格同一個 PR（分支 `feature-grilling`）：

- `.claude/skills/feature/SKILL.md`
  - frontmatter description、開頭、第 1 節標題「1. 規格（plan mode）」與第一段：需求 1、2。
  - 第 1 節新增「### 需求問答（標準、高風險）」，放在「判斷等級」之後、「規格內容」之前：需求 3、6，以及提問格式（需求 4）。
  - 「文字修正的流程」：改動清單寫在 scratchpad、文字核准；需求 6 第 2 點。
  - 「規格內容」的「假設」：需求 5 第 2 點。「已決定事項」：需求 8。
  - 「規格審查」：傳草稿路徑；第 3 節「規格問題的處理」：提問用文字格式、回到決策樹；「核准後修改規格」：C 編號。
  - 第 4 節「清理暫存」：需求 9。
- `.claude/skills/issue/SKILL.md`：差異表「在 plan mode 交給開發者核准」改成文字核准；需求 7。
- `.claude/agents/specification-reviewer.md`：已決定事項描述對齊需求 8。
- 刪除 `.claude/skills/feature-grill/`。
- `docs/README.md` 暫存列、`docs/specs/README.md`「各等級的規格」：需求 9。
- `docs/experiments/feature-grill/README.md`：需求 10。
- `docs/decisions/0008-grilling-without-plan-mode.md`（新增）、`docs/decisions/README.md` 清單、ADR 0007 狀態行。
- `docs/specs/feature-grilling.md`（這份規格，已核准）、`docs/reviews/specification/feature-grilling.md`、`docs/reviews/implementation/feature-grilling.md`。

## 測試對應

| AC | 驗證方式 |
|---|---|
| AC1–AC4、AC6–AC9 | 讀 `/feature`、`/issue`，各走一次流程並確認步驟、順序與提問格式：標準功能、高風險 issue（含建議的驗收條件）、輕量 bug、文字修正、輕量在規格審查後升級、文字修正中途升級、實作審查時升級；AC6 至少走過實作回報與實作審查兩個階段 |
| AC5 | `git show 23c56c9:.claude/skills/feature-grill/SKILL.md` 第 0 節逐條對照 `/feature` |
| AC10 | 比對三個檔案中已決定事項的描述 |
| AC11、AC14 | `git grep -n "plan mode\|plan 檔\|ExitPlanMode\|AskUserQuestion\|feature-grill"`、`grep` 節名稱與路徑 |
| AC12、AC13 | 讀對應文件 |
| AC15 | 讀 `/feature` 的定義與第一次出現的位置；`git grep -n "D 項\|D 編號\|已決定事項\|decisions.md"` 只剩歷史文件 |
| AC16 | 讀 `/feature`「核准後修改規格」與「清理暫存」 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-09 | 核准前：新增「整個 `/feature` 不用 plan mode、提問一律文字格式」（需求 1、4、9、11；AC1、AC3、AC4、AC11、AC13、AC14），拿掉 plan mode 中用 AskUserQuestion 的規則 | D9（第 2 輪規格審查後，開發者決定）；這幾條未經規格審查，由實作審查補查 | 開發者（2026-11-09 核准） |
| 2026-11-09 | 實作審查第 1 輪後：ADR 草稿核准前寫在 scratchpad（需求 1、AC1）；`/issue` 第 1 節的提問也用文字格式（需求 13、AC4）；文字修正的清理暫存對照 PR（需求 14、AC16）；「D 項／已決定事項」改成 Context（C 編號）與 Frontier（Q 編號連續），查到的事實不進 Context，所有等級共用（需求 8、AC15）；修改紀錄所有等級寫 C 編號（需求 12、AC16）。影響檢查：需求 1–3、5、7、9、11，假設 2、3，AC1–AC4、AC6、AC7、AC10、AC11、AC14 改用新名稱或已一併更新；AC5、AC8、AC9、AC12、AC13 不用改。這份規格自己的 D1–D12 是當時的紀錄，保留原名 | 實作審查第 1 輪 #1（D11）、#2、#3；開發者要求改用 grill-me 的 Context／Frontier（D12） | 開發者（2026-11-09） |
