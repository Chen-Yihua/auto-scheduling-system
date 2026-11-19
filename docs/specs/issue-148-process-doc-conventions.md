# 流程文件對照常見寫法、每條規則只寫一處、草稿改放 `.drafts/`

- 狀態：已核准
- 等級：一般（只改流程文件、`.gitignore` 與 ADR 的狀態；不改程式碼，不涉及資料一致性、認證授權、憑證保護，也不是重大架構決策。草稿位置的改變推翻 ADR 0008、0009、0010 的一部分，另寫 ADR 0014）
- issue：#148、#147
- PR：#150

## 簡短說明

流程文件改成一般常見的寫法；每條流程規則只寫在一個檔案，其他地方連過去；核准前的草稿從 scratchpad 改放 repo 內被 git 排除的 `.drafts/`。

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/148 、https://github.com/Chen-Yihua/auto-scheduling-system/issues/147

**問題**：開發者讀流程文件時，有三種情況要多花時間：

1. 寫法和公認寫得好的文件不同，要另外理解（#148）。
2. 同一條規則寫在好幾個檔案，改一處就和另一處衝突（#147）。
3. 要看核准前的草稿時，要自己到 `/tmp` 底下依 session id 找資料夾。

**案例**：

- `/issue 140` 的需求問答中，主 session 提的規則草稿寫出原本就沒有的東西、規定固定句型，開發者要求參考著名的 skill 才改成常見寫法。
- #140 改了 `docs/specs/README.md` 的驗收條件寫法，`write-spec` 寫了同一個句型，要另外改；`docs/issues.md` 漏改，到現在還寫著舊的句型「在 X 情況下，系統要 Y」。
- `/issue 148` 的需求問答中，開發者每次看草稿都要自己開 `/tmp/claude-0/-home-auto-scheduling-system/<session id>/scratchpad/`。

### 對照的來源

| 文件 | 來源（版本） |
|---|---|
| 全部 | Google developer documentation style guide〈Highlights〉（2026-11-20 讀取） |
| skill | Anthropic〈Skill authoring best practices〉（2026-11-20）；`anthropics/skills` 的 `skill-creator/SKILL.md`（`e4bb5d9`）；`mattpocock/skills` 的 `grilling`（`abeeaf9`）；`obra/superpowers` 的 `writing-skills`、`brainstorming`（`22f0b46`） |
| agent | Claude Code〈Subagents〉（2026-11-20） |
| `CLAUDE.md` | Claude Code〈Memory〉（2026-11-20）；〈Best practices〉的 CLAUDE.md 部分 |
| `docs/specs/README.md` | `github/spec-kit` 的 `templates/spec-template.md`（`61d3abb`）；Liz Keogh〈Acceptance Criteria vs. Scenarios〉 |
| `docs/reviews/README.md` | Google eng-practices〈Writing code review comments〉 |
| `docs/issues.md` | Mozilla〈Bug writing guidelines〉 |
| `docs/decisions/README.md` | Michael Nygard〈Documenting Architecture Decisions〉 |

### 對照結果

| # | 段落 | 和常見寫法不同的地方 | 來源 | 處理 |
|---|---|---|---|---|
| F1 | 6 個 skill 的 `description` | 寫整段流程摘要；3 個階段 skill 的「什麼時候用」寫在本文 | Anthropic「Writing effective descriptions」：寫做什麼與什麼時候用；skill-creator：「All "when to use" info goes here, not in the body」 | 需求 1 |
| F2 | `clarify-requirements:8`、`write-spec:8`、`implement-and-review:8` 的「> 什麼時候讀」 | 同 F1 | 同 F1 | 需求 2 |
| F3 | `implement-and-review` 整份 | 步驟分散在多節，沒有總覽 | Anthropic「Use workflows for complex tasks」 | 需求 3 |
| F4 | skill 之間的引用 | A 叫讀者看 B，B 又叫讀者看 C | Anthropic「Avoid deeply nested references」 | 需求 34 |
| F5 | `clarify-requirements:108` | grilling 一律派 sub-agent 查事實，這裡只在範圍大時派，沒寫原因 | mattpocock `grilling` | 需求 4 |
| F6 | `implement-and-review:50`、`:79`、`:80`、`:85`、`:134`；`write-spec:15`、`:32` | 一句話塞了多個條件與做法 | Google「Put conditions before instructions」「Use numbered lists」；`CLAUDE.md`「寫作規則」第 1、5 條 | 需求 5 |
| F7 | `clarify-requirements:72`、`:122`、`:140` | 讀者有時叫「你」、有時叫「Agent」；「使用者提出的做法」其實是開發者；「開發等級」其他地方都叫「等級」 | Anthropic「Use consistent terminology」；Google「Use second person」 | 需求 6 |
| F8 | `feature` 的「## 4. 回報」 | 流程表寫第 5 步 | 同 F7 | 需求 7 |
| F9 | `write-spec:52` | 「以及 已確認」多一個空格；檔尾沒有換行 | — | 需求 7 |
| F10 | `issue-triage:42` | 一句說明插在編號清單第 3、4 步中間 | Google「Use numbered lists」 | 需求 7 |
| G1 | 3 個 agent 開頭的「你會收到」 | 收到的東西、舊等級對照、指令寫在同一段 | Google「Use bulleted lists」 | 需求 8 |
| G2 | `feature-implementer` 步驟 3 | 一步裡有檢查、commit、push、開 PR、補編號、等 CI | Google「Use numbered lists」 | 需求 9 |
| G3 | `docs/issues.md`「格式」 | bug 沒有重現步驟 | Mozilla：重現步驟是 bug report 最重要的部分，並註明每次都發生還是偶爾 | 需求 10 |
| G4 | `docs/specs/README.md`「格式」的「需求」 | 沒要求編號（「假設」有） | spec-kit：需求編號 FR-001 | 需求 11 |
| G5 | `docs/decisions/README.md` | 沒寫為什麼沒有「提議中」 | Nygard：proposed → accepted | 需求 12 |
| G6 | `docs/README.md:23` | 一格寫了整段交付流程 | Claude Code〈Memory〉「Structure」 | 需求 26 |

符合、不改：沒有否定原本不存在的東西；SKILL.md 都在 500 行內，`references/resume.md` 不到 100 行，不用目錄；沒有時效性資訊；`CLAUDE.md` 93 行（〈Memory〉建議 200 行內）；agent 的 `description` 寫了什麼時候派；`docs/reviews/README.md` 的阻擋／不阻擋對應 Google 的 Nit／Optional／FYI 標示，發現都附原因與建議；ADR 格式有背景、決定、影響；issue 第一句寫問題而不是修法，看到的現象（情境）和推測的原因（技術背景）分開。

### 重複的規則

| # | 規則 | 現在的位置 |
|---|---|---|
| D1 | 問開發者不用 AskUserQuestion | `feature:35`、`issue:22` |
| D2 | `gh` 要加 `--json`、不用 `gh issue edit` | `CLAUDE.md:27-28`、`issue-triage:18`、`:42` |
| D3 | 漏洞的定義、細節不能寫在哪裡、不能 push 修正 | `feature:36`、`implement-and-review:105`、`:108`、`feature-implementer:20`、`docs/reviews/README.md:61-62` |
| D4 | 暫存檔遺失時審查怎麼判斷 | `resume.md:5-11`、`acceptance-reviewer:16`、`specification-reviewer:27`、`docs/reviews/README.md:37` |
| D5 | 寫法問題不另設類型 | `acceptance-reviewer:14`、`specification-reviewer:19`（同一段話） |
| D6 | 「寫法：」的發現怎麼標、怎麼處理 | `implement-and-review:79`、`feature-implementer:22`、`acceptance-reviewer:37` |
| D7 | 一般等級第 2 輪以後的審查範圍 | `feature:46`、`implement-and-review:134`、`acceptance-reviewer:31` |
| D8 | 驗收條件要想過的情境（**內容不一致**） | `docs/specs/README.md:60`、`write-spec:16`、`acceptance-reviewer:11` 是 6 類；`specification-reviewer:17` 多了資料一致性、同時操作、和既有規則交會的地方 |
| D9 | 「修改紀錄」的「原因」怎麼寫 | `implement-and-review:93`、`docs/specs/README.md:105` |
| D10 | 合併由開發者決定 | `CLAUDE.md:30`、`feature:37` |
| D11 | 驗收條件範本（**內容不一致**） | `docs/specs/README.md:57-58`、`docs/issues.md:27` |
| D12 | 規格審查最多 2 次 | `feature:45-46`、`write-spec:41`、`docs/reviews/README.md:12` |
| D13 | 漏洞一律阻擋 | `docs/reviews/README.md:61`、`acceptance-reviewer:33` |
| D14 | 暫存檔核准後怎麼轉成正式文件 | `docs/README.md:23`、`implement-and-review:15-22`、`feature`「清理暫存」 |
| D15 | 只用 `git add <路徑>`，不用 `git add -A`、`git add .` | `implement-and-review:58`、`feature-implementer:17` |
| D16 | 「需要你選擇」：開發者要選定一個選項，只回「是」不算 | `clarify-requirements:107`、`implement-and-review:85`、`docs/reviews/README.md:72` |
| D17 | 等級判斷偏低時列成「規格內容互相矛盾或沒有依據」 | `specification-reviewer:9`、`acceptance-reviewer:31`、`docs/reviews/README.md:28` |
| D18 | 會讓驗收條件在某個條件下不成立的發現，不是「沒有錯，但可以更好」 | `acceptance-reviewer:22`、`docs/reviews/README.md:34` |
| D19 | 規格問題的「影響」「建議」與證據怎麼寫 | `acceptance-reviewer:39`、`specification-reviewer:35`、`docs/reviews/README.md:116-118`（一部分） |
| D20 | 核准前只寫 scratchpad、不改 repo | `feature:33`、`clarify-requirements:55` |
| D21 | 正式文件不引用 `<功能>-grill.md` | `clarify-requirements:49`、`docs/reviews/README.md:162` |

`feature:35` 這種寫法指 `.claude/skills/feature/SKILL.md` 第 35 行；agent 指 `.claude/agents/<名稱>.md`；`resume.md` 指 `.claude/skills/feature/references/resume.md`。

### 和草稿位置有關的事實

- 範圍內的流程文件有 50 處寫到 scratchpad（`grep -c scratchpad`）。
- agent（Explore、Plan 除外）啟動時會讀 `CLAUDE.md`，不會讀 skill，除非 frontmatter 用 `skills` 預先載入（Claude Code〈Subagents〉）。所以主 session 和 agent 都要遵守的規則放在 `CLAUDE.md`，雙方都讀得到。
- ADR 0010「放棄的做法」放棄過「把 scratchpad 改到 repo 內的資料夾」，理由是會被別的 commit 帶走、取消時要還原；ADR 0014 草稿說明現在怎麼處理這兩點。

## 需求

範圍內的檔案：`CLAUDE.md`、`.gitignore`、`.claude/skills/` 底下全部、`.claude/agents/` 底下全部、`docs/README.md`、`docs/specs/README.md`、`docs/reviews/README.md`、`docs/issues.md`、`docs/decisions/README.md`，以及 ADR 0008、0009、0010 的「狀態」那一行。下面的行號是 `origin/main`（`b1e52c3`）上的行號。

### A. 寫法（#148）

1. 6 個 skill 的 `description` 改成下面的文字：
   - `clarify-requirements`：「需求確認：簡述對需求的理解、向開發者做需求問答（決策樹）、探索工程方案、確認術語。在 /feature 判斷完等級後載入；之後任何階段出現新的決定或要升級等級時也載入。只在 /feature 流程中使用，不單獨觸發。」
   - `write-spec`：「寫規格草稿（和重大架構決策的 ADR 草稿）、交給 specification-reviewer 審查並處理發現、交給開發者核准。在 /feature 需求確認完成後載入，用到開發者核准規格為止。只在 /feature 流程中使用，不單獨觸發。」
   - `implement-and-review`：「整理交付清單交給 feature-implementer 實作與開 PR、交給 acceptance-reviewer 審查、依發現的分類處理。在 /feature 開發者核准規格後載入，用到回報為止。只在 /feature 流程中使用，不單獨觸發。」
   - `feature`：「開發新功能或行為變更：需求問答、寫規格交給開發者核准、交給 agent 實作與審查。用 /feature <需求> 執行。」
   - `issue`：「針對指定的 GitHub Issue 執行和 /feature 相同的開發流程。用 /issue <issue 編號> 執行。」
   - `issue-triage`：「整理所有開著的 GitHub Issues：分類、建議優先度、相依性與處理順序，開發者確認後加 priority 標籤。用 /issue-triage 執行；只整理，不開始開發。」
2. 3 個階段 skill 開頭的「> 什麼時候讀」改成只留導覽：
   - `clarify-requirements:8` 改成：「> 所有等級都做；深度依「需求問答」的提問原則（小改動自然只有一兩題）。之後任何階段出現新的決定、或要升級等級時，讀「新的決定一律回到決策樹」與「做到一半改成較高的等級」。」
   - `write-spec:8` 改成：「> 文字修正不寫規格，見 `feature`「文字修正的流程」。」
   - `implement-and-review:8` 改成：「> 發現可被利用的漏洞時（任何階段），直接讀「漏洞的處理」。」
3. `implement-and-review` 的「核准後自動進行，不再中途詢問。」後面加一節「## 步驟」：
   ```
   照順序做，每一步的細節見括號裡的節：

   1. 整理交付清單，交給 `feature-implementer` 實作、開 PR（「交付清單」「交辦實作與處理回報」）。
   2. PR 建立後，commit 規格審查紀錄（「審查紀錄的 commit」）。
   3. 交給 `acceptance-reviewer` 審查（「交給 acceptance-reviewer 審查」）。
   4. 依每項發現處理（「發現處理表」）。
   5. 更新實作審查紀錄並 commit（「每一輪都更新紀錄檔」）。
   6. 還有阻擋的項目就回到第 3 步（「輪數依根本原因計算」）。
   7. 沒有阻擋後，照 `feature`「回報」回報。
   ```
4. `clarify-requirements:108` 的「範圍很大時才派 `Explore` agent。」改成：「範圍很大時才派 `Explore` agent。grilling 一律派 sub-agent 查事實，這裡不用：派出去的 agent 要重新讀過上下文，查一兩個檔案時自己讀比較快。」
5. 下面幾段拆成清單，條件寫在前面，規則的意思不變：
   1. `implement-and-review:50` 改成：
      ```
      - 它因為「術語重複或衝突」或「工作目錄有歸屬不明的改動」停下來回報時，照順序做：
        1. 用 `clarify-requirements`「需求問答」的格式問開發者；術語的決定照 `clarify-requirements`「新的決定一律回到決策樹」。
        2. 開發者決定修改 `origin/main` 上既有的定義時，交付清單把該術語標成「修改既有定義（開發者已確認）」，寫上原定義與新定義，再做第 4 步。
        3. 要改的是這個 PR 先前交付、`origin/main` 還沒有的術語時，標成「更新本 PR 的術語」，寫上上一版定義與新定義，再做第 4 步。
        4. 再交辦。
      ```
   2. `implement-and-review:79`「處理」欄改成：「不阻擋，不開 issue，在同一個 PR 改：`feature-implementer` 寫的檔案請它修正，主 session 寫的檔案由主 session 改。已核准的規格、ADR 與術語表裡的寫法問題除外，照「核准後修改規格」。」
   3. `implement-and-review:80`「處理」欄改成：「照「不阻擋的發現開 issue」，不在這個 PR 修。開發者明確要求在這個 PR 處理時：先照「規格問題的處理」第 3 步寫成驗收條件，再交給 `feature-implementer`，並在處理結果記下決定者。」「發現」欄維持原文（包括「；上一列的寫法問題除外」），讓第 79、80 列不會同時符合。
   4. `implement-and-review:85`（「規格問題的處理」第 2 步）改成：
      ```
      2. 用 `clarify-requirements`「需求問答」的格式問開發者，並請開發者決定要在這個 PR 補上，還是另開 issue。規格已經核准，每一項修改都要開發者確認。照順序判斷，符合一條就停：
         1. 涉及產品行為、權限、安全性、資料處理或架構：照 `docs/reviews/README.md`「開發者決策」表「需要選擇」那一列出題，標明「需要你選擇」。
         2. 其他（包括依查證依據修正、不改變行為的「規格對現有系統的描述和程式不符」）：可以附上建議的驗收條件，讓開發者一次確認。

         開發者的決定照 `clarify-requirements`「新的決定一律回到決策樹」處理。
      ```
   5. `implement-and-review:134`（「輪數依根本原因計算」）改成：
      ```
      修正後重新審查，直到沒有阻擋的項目為止：

      1. 每一項阻擋的發現，在紀錄檔的「根本原因」欄標上一個簡短的名稱。
      2. 之後的發現出自同一個根本原因時，沿用同一個名稱並累計輪數；改了不同的驗收條件或規格版本也不重新計算。
      3. 同一個根本原因連續 3 輪都還有阻擋時，停止自動修改，整理具體原因問開發者。不得自行重置輪數。
      4. 第 2 輪以後的審查範圍照 `feature`「判斷等級」表的「實作審查」欄，寫進給 `acceptance-reviewer` 的指示。
      ```
   6. `write-spec:15`（「假設」）改成：
      ```
      - **假設**：逐條列出程式碼看不出來、由你判斷的事，以及開發者明確交給你決定的事。
        - 開發者決定的事寫進需求、不做或驗收條件，不寫成假設。
        - 只有無法合理假設、而且會影響整體方向的問題，才先問開發者。
        - 碰到需要開發者決定的業務規則，照 `clarify-requirements`「新的決定一律回到決策樹」問開發者，不寫成假設。
      ```
   7. `write-spec:32` 改成：「- 涉及產品行為、權限、安全性、資料處理或架構的發現：照 `implement-and-review`「規格問題的處理」第 2 步問開發者。包括會改變行為的「規格對現有系統的描述和程式不符」、「規格內容互相矛盾或沒有依據」、「規格沒寫某個情境該怎麼做」。」
6. `clarify-requirements` 的用詞：
   - `:72` 的「由 Agent 依照」改成「由你依照」。
   - `:140` 的「一般技術實作方式由 Agent 決定」改成「一般技術實作方式由你決定」。
   - `:122` 的「使用者提出的做法」改成「開發者提出的做法」，「依開發等級」改成「依等級」。
7. 修標題、錯字與被打斷的清單：
   - `feature` 的「## 4. 回報」改成「## 回報」。
   - `write-spec:52` 的「以及 已確認決定」改成「以及已確認決定」，檔尾補換行。
   - `issue-triage:42` 那一行刪掉，`:36` 的「確認後：」改成「確認後照下面的步驟做。改標籤用 `gh api`，照 CLAUDE.md「開發流程」第 3 點：」。
8. 3 個 agent 開頭的「你會收到」拆成清單：
   - `acceptance-reviewer:7` 改成：
     ```
     你會收到：

     - 規格檔：`docs/specs/<功能>.md` 或 `docs/specs/issue-<N>-<名稱>.md`。
     - 等級：一般或高風險。ADR 0007 以前的規格沒有等級；更早的規格寫「輕量」或「標準」的，都當成「一般」。
     - 分支名稱。
     - 規格審查紀錄：`docs/reviews/specification/<功能>.md`。ADR 0006 以前用 bug 簡化格式的規格沒有。
     - PR 描述全文。

     規格在核准前已經由 `specification-reviewer` 審查過：它的查證紀錄當作已確認的事實，「已接受的風險」不要再列成新發現。

     用 `git diff origin/main...HEAD` 看改動。主 session 交給你前已經 fetch；不要用本機 `main`，它可能落後。檢查：
     ```
   - `specification-reviewer:7` 改成：
     ```
     你會收到：

     - 規格草稿的路徑。
     - 等級：一般或高風險，定義見 `.claude/skills/feature/SKILL.md`「判斷等級」。
     - 草稿資料夾的 `<功能>-grill.md`：「已確認」是開發者確認過的決定，「待問」是還沒問到的問題，定義見 `.claude/skills/clarify-requirements/SKILL.md`「記錄決定」。
     - 有的話：重大架構決策的 ADR 草稿路徑；草稿資料夾的 `<功能>-glossary.md`（這次確定的術語，格式見 `docs/README.md`「術語表」）。

     這時還沒有實作，你審查的是規格本身，讓問題在寫程式之前被發現。
     ```
   - `feature-implementer:6` 改成：
     ```
     你會收到交付清單和分支名稱。交付清單列出這次要放進 repo 的產品文件，每個檔案寫出 repo 路徑與草稿資料夾裡的來源：

     - 規格：`docs/specs/<功能>.md`。
     - ADR：`docs/decisions/`（有的話）。
     - 術語表：`docs/glossary.md`（格式見 `docs/README.md`「術語表」）。術語另外分成「新增」、「修改既有定義（開發者已確認）」與「更新本 PR 的術語」。

     規格是你唯一的需求來源：需求、假設、驗收條件都以它為準。不要自己補需求，也不要因為覺得「應該要有」就擴大範圍。
     ```
9. `feature-implementer:17`（步驟 3）改成：
   ```
   3. commit 與開 PR，照順序做：
      1. 跑 CLAUDE.md「完成的定義」的檢查，全部通過才繼續。
      2. 看 `git status`、`git diff`。工作目錄有交付清單以外、也不是這次實作造成的改動，或無法確認歸屬時，停下來回報，不 commit。
      3. 照 CLAUDE.md「開發流程」第 2 點 commit，只加入交付清單上的檔案與這次實作改的檔案。`docs/reviews/` 的審查紀錄由主 session commit，不要加入。
      4. push，用 `gh pr create` 開 PR。描述放「驗收條件、測試與結果的對照表」：驗收條件 → 對應的測試 → 結果。
      5. 把規格開頭的「PR」補上編號，commit、push。
      6. 用 `gh pr checks --watch` 等 CI。

      之後更新 PR 描述照 CLAUDE.md「開發流程」第 3 點。
   ```
10. `docs/issues.md`「格式」的「情境」在「實際」前面加一欄「- **重現步驟**：」；範本後面的說明加一條：「「重現步驟」只有產品的 bug、部署與 CI 的錯誤要寫：用編號寫出每一步操作，最後寫每次都會發生還是偶爾發生。還不知道怎麼重現時，寫進「待調查／待決定」。」
11. `docs/specs/README.md`「格式」的「需求」說明改成：「要做什麼，逐條編號。每條需求只講一件事：出現「而且」「以及」就考慮拆開。」
12. `docs/decisions/README.md` 開頭第二段後面加一段：「核准前只維護草稿資料夾（`.drafts/`）裡的一份工作草稿（ADR 0008、ADR 0014），核准後才轉成正式文件 commit。」
13. 修錯字與連錯的節：
    - `docs/reviews/README.md:12` 的括號補齊（內容照需求 23）。
    - `docs/reviews/README.md:14` 的「照 `/feature` 的「漏洞的處理」」改成「照 `implement-and-review`「審查紀錄與重新審查」」。
    - `docs/reviews/README.md:68` 的「照 `/feature` 的處理表」改成「照 `implement-and-review`「發現處理表」」。
    - `docs/issues.md:42` 的反引號補齊（內容照需求 17）。

### B. 每條規則只寫一處（#147）

每條規則依下面的順序決定放哪裡，符合一條就停：

1. 主 session 和 agent 都要遵守的 → `CLAUDE.md`。
2. 審查的分類與判斷 → `docs/reviews/README.md`。
3. 規格的寫法 → `docs/specs/README.md`。
4. 只有主 session 會做的 → 對應的 skill。
5. 只有某個 agent 會做的 → 那個 agent 的定義。

14. D1：`issue:22` 改成「這一節向開發者提問（沒有 issue 編號、issue 已關閉）也照 `feature`「硬規則」第 4 條。」原文留在 `feature:35`。
15. D2：`issue-triage:18` 的「`gh issue view` 一定要加 `--json`，原因見 CLAUDE.md「開發流程」。」改成「`gh` 指令照 CLAUDE.md「開發流程」第 3 點。」`:42` 照需求 7 刪掉。原文留在 `CLAUDE.md:27-28`。
16. D3：`CLAUDE.md` 在「跨前後端的連動」前面加一節：
    ```
    ## 漏洞

    這個 repo 是公開的。「漏洞」與「安全」怎麼區分，見 `docs/reviews/README.md`「涉及安全／架構」。

    主 session 或 agent 在任何階段發現漏洞時：

    1. 停止這一項。agent 不修正、不 push，在回報裡標明「漏洞」交給主 session；主 session 照 `.claude/skills/implement-and-review/SKILL.md`「漏洞的處理」。
    2. 開發者決定處理方式前，漏洞的位置與利用方式只寫在給主 session 或開發者的回報裡，不能出現在 issue、PR 描述、commit 訊息、程式註解、規格檔、測試名稱與 docstring、`docs/reviews/`。
    3. 不把修正推送到公開的 repo，包括這個 PR 的分支。
    ```
17. D3 的其他位置改成連到 `CLAUDE.md`「漏洞」：
    - `feature:36` 改成「5. **漏洞**：照 CLAUDE.md「漏洞」。」
    - `feature:67` 的「照 `implement-and-review`「漏洞的處理」」改成「照 CLAUDE.md「漏洞」」。
    - `issue:41` 的「（可被利用的漏洞照 `implement-and-review`「漏洞的處理」，不開 issue）」改成「（可被利用的漏洞照 CLAUDE.md「漏洞」，不開 issue）」。
    - `implement-and-review:105` 改成「漏洞的定義見 `docs/reviews/README.md`「涉及安全／架構」；細節不能出現的地方見 CLAUDE.md「漏洞」。這裡只寫主 session 怎麼處理，不定義漏洞的修復與發布流程。」
    - `implement-and-review:107` 改成「1. 暫停目前的開發流程，不再交給 `feature-implementer` 任何修正。」`:108` 刪掉，後面的步驟重新編號（第 3 步變第 2 步，第 4 步變第 3 步）。
    - `feature-implementer:20` 改成「發現可被利用的漏洞時（不用等指示），照 CLAUDE.md「漏洞」。之後照開發者決定的方式處理。」
    - `docs/issues.md:42` 改成「- 可被利用的漏洞不開 issue，照 CLAUDE.md「漏洞」。」
    - `docs/reviews/README.md:61-62` 不變，是「漏洞」「安全」定義的原文。
18. D4：`docs/reviews/README.md:37` 改成：
    ```
    - **暫存檔遺失時**：草稿資料夾裡這次的暫存檔遺失時，照順序判斷，符合一條就停：
      1. `.claude/skills/feature/references/resume.md` 的恢復步驟、暫存檔表與部分改動的完成狀態處理不了，而且會造成下列風險之一：已核准的決定被推翻、正式文件被憑記憶重寫、開發者沒被告知決定或成果遺失 → 列成發現並阻擋。
      2. 其他情況不算問題：不列成發現，也不要求逐一增加特定案例，寫在報告的「已接受的風險」。「規格內容互相矛盾或沒有依據」、「規格沒寫某個情境該怎麼做」一律阻擋的規則不適用於這些情況。

      這條只限暫存檔遺失，不擴大到其他流程。
    ```
    `resume.md:5-11`（「scratchpad 遺失時的審查規則」整節）刪掉，`:3` 刪掉「`specification-reviewer` 與 `acceptance-reviewer` 只讀「scratchpad 遺失時的審查規則」。」。其他位置照下面改：
    - `acceptance-reviewer:16`、`specification-reviewer:27` 改成「草稿資料夾裡的暫存檔遺失時，照 `docs/reviews/README.md`「分類」的「暫存檔遺失時」判斷。」
    - `acceptance-reviewer:29`、`specification-reviewer:44` 的「上面「scratchpad 遺失時的審查規則」判定不算問題的情況」改成「`docs/reviews/README.md`「分類」的「暫存檔遺失時」判定不算問題的情況」。
    - `docs/reviews/README.md:145` 的「列 `feature/references/resume.md`「scratchpad 遺失時的審查規則」判定不算問題的情況」改成「列「分類」的「暫存檔遺失時」判定不算問題的情況」。
    - `docs/reviews/README.md:214` 的「實作審查紀錄有 scratchpad 遺失時不算問題的情況（`feature/references/resume.md`「scratchpad 遺失時的審查規則」）、決定不補（同一個檔案「暫停與接續」第 6 步）的項目」改成「實作審查紀錄有「分類」的「暫存檔遺失時」判定不算問題的情況、決定不補（`.claude/skills/feature/references/resume.md`「暫停與接續」第 6 步）的項目」。
19. D5、D6：`docs/reviews/README.md`「分類」的清單最後加一條：
    ```
    - **寫法問題**（`CLAUDE.md`「寫作規則」）不另設類型：看改寫後會影響什麼，歸進現有的類型。改寫會改到驗收條件的意思，就是規格的問題；只換說法、意思不變，就是「沒有錯，但可以更好」，不阻擋，標題開頭寫「寫法：」，讓主 session 分得出來。
    ```
    `acceptance-reviewer:14`、`specification-reviewer:19` 的「寫法問題不另設類型：…就是「沒有錯，但可以更好」。」改成「分類照 `docs/reviews/README.md`「分類」的「寫法問題」。」`acceptance-reviewer:37` 改成「不阻擋的發現（標題開頭是「寫法：」的除外）會被拿去開 GitHub issue，「問題說明」要寫到不看這次 PR 也看得懂。」`feature-implementer:22` 的最後一句改成「另一個例外：主 session 請你修標題開頭是「寫法：」的發現時照做，只改你寫的檔案。」處理方式的原文留在 `implement-and-review:79`。
20. D7：`acceptance-reviewer:31` 的「一般等級的第 2 輪以後，主 session 會指定要覆核的項目，…不重審整個功能；看到範圍外的新問題仍然回報。」改成「第 2 輪以後，照主 session 在指示裡寫的範圍審查；看到範圍外的新問題仍然回報。」`implement-and-review:134` 照需求 5 第 5 點。原文留在 `feature:46`（「判斷等級」表）。
21. D8：`docs/specs/README.md`「驗收條件怎麼寫」在「每條都要能驗證」前面加一條：「- 逐一想過下面每一類情境：失敗、空資料、載入中、未登入／無權限、資料處理與一致性、同時操作、安全性，以及新功能和既有規則（例如既有的排程規則、刪除行為）交會的地方。驗收條件沒有涵蓋的，寫進「不適用的情境」並說明原因。」其他位置改成連過去：
    - `docs/specs/README.md:60` 改成「照 `docs/specs/README.md`「驗收條件怎麼寫」。」（這一行在規格範本裡，範本被複製到別的檔案後，「上面」會指錯地方）
    - `docs/specs/README.md:101` 的「「格式」裡「驗收條件」下方列出的每一類情境」改成「「驗收條件怎麼寫」列出的每一類情境」。
    - `write-spec:16` 改成「- **驗收條件**：編號 AC1、AC2…，照 `docs/specs/README.md`「驗收條件怎麼寫」。」
    - `specification-reviewer:17` 改成「4. **缺漏**：在規格宣告的需求範圍內，`docs/specs/README.md`「驗收條件怎麼寫」列出的每一類情境，有沒有被驗收條件涵蓋，或在「不適用的情境」說明原因。」
    - `acceptance-reviewer:11` 的「另外檢查失敗、空資料、載入中、未登入／無權限、資料處理、安全性這些情境有沒有被驗收條件涵蓋」改成「另外照 `docs/specs/README.md`「驗收條件怎麼寫」列出的每一類情境，檢查有沒有被驗收條件涵蓋」。
22. D9：`implement-and-review:93` 的「「修改紀錄」的「原因」寫：…不用改」」改成「「修改紀錄」照 `docs/specs/README.md`「核准後」寫。」原文留在 `docs/specs/README.md:105`。
23. D10、D12：`feature:37` 改成「6. **不可合併 PR**：照 CLAUDE.md「開發流程」第 5 點。」`write-spec:41` 的「**最多 2 次**：」改成「**次數**：上限見 `feature`「判斷等級」的表。」`docs/reviews/README.md:12` 改成「- 等級是「文字修正」的變更不審查，沒有紀錄檔。規格審查的次數上限見 `/feature`「判斷等級」的表；第 2 次審查的範圍見 `write-spec`「審查次數與審查後的修改」。」
24. D11：`docs/issues.md:27-28` 的兩列改成「| AC1 | <必須達成的結果> | 使用者行為 |」「| AC2 | 在 X 情況下，做 Y，結果是 Z | 不變條件 |」。
25. D13：`acceptance-reviewer:33` 的「不論類型，「阻擋合併」一律填「是」，不能以不阻擋的項目通過驗收；另外」改成「「阻擋合併」照 `docs/reviews/README.md`「涉及安全／架構」填；另外」。
26. D14：`docs/README.md:23` 的「規則」欄改成：「只放當下的開發需要的內容，不會進 git。核准後由誰把哪個暫存檔存成正式文件見 `implement-and-review`「Commit 責任」，審查紀錄的 commit 步驟見同一個檔案「審查紀錄的 commit」；回報前的確認與刪除見 `/feature`「清理暫存」」。`feature:82`（「清理暫存」）開頭的「見 `docs/README.md`「生命週期」。」刪掉，避免兩邊互相指向。
27. D15：`CLAUDE.md:26` 改成「2. 跑完上面「完成的定義」的檢查才 commit。commit 時只用 `git add <路徑>` 加入這次要 commit 的檔案，不用 `git add -A`、`git add .`。」`implement-and-review:58` 改成「2. 照 CLAUDE.md「開發流程」第 2 點，只加入這次的紀錄檔，不帶其他未提交的修改。」`feature-implementer:17` 照需求 9。
28. D16：`docs/reviews/README.md:72`「需要選擇」那一列的「什麼時候」欄改成：「涉及未定義的產品行為、權限、安全性、資料處理或架構。列出選項與各自的影響，附上建議與理由；開發者要選定一個選項或另外說明，只回「是」不算」。`clarify-requirements:107` 改成「- 涉及未定義的產品行為、權限、安全性、資料處理或架構的題目，照 `docs/reviews/README.md`「開發者決策」表「需要選擇」那一列出題：`➡️` 那一行寫建議與理由，並標明「需要你選擇」。」`implement-and-review:85` 照需求 5 第 4 點。
29. D17：`specification-reviewer:9` 的「照規格的內容判斷等級偏低時（例如標成一般，卻改變了既有資料的讀取或權限），列成「規格內容互相矛盾或沒有依據」，寫出應該是哪個等級與理由。」改成「照規格的內容判斷等級偏低時，照 `docs/reviews/README.md`「問題類型」分類，寫出應該是哪個等級與理由。」`acceptance-reviewer:31` 的「改動實際的影響比規格的等級高時（例如「一般」卻改變了既有資料的讀取或權限），列成「規格內容互相矛盾或沒有依據」。」改成「改動實際的影響比規格的等級高時，照 `docs/reviews/README.md`「問題類型」分類。」原文留在 `docs/reviews/README.md:28`。
30. D18：`acceptance-reviewer:22` 最後一句「會讓某條驗收條件在某個條件下不成立的發現（例如同時操作、中途失敗時），不能列成「沒有錯，但可以更好」。」刪掉；同一段已經寫了照 `docs/reviews/README.md`「分類」判斷，原文留在 `docs/reviews/README.md:34`。
31. D19：`docs/reviews/README.md`「問題說明」的清單改成：第 3 點最後加「規格的問題，寫出影響哪些檔案、哪些驗收條件與假設。」；第 4 點最後加「「規格對現有系統的描述和程式不符」附上現有行為的依據（`檔案:行號`）；「規格內容互相矛盾或沒有依據」寫出互相衝突的是哪幾條。」；第 5 點的「規格的問題寫出建議的驗收條件。」改成「規格的問題寫出建議的驗收條件與理由。」`specification-reviewer:35`、`acceptance-reviewer:39` 整段刪掉。
32. D20：`clarify-requirements:55` 的「寫在哪裡填「術語表」。核准前仍然只寫 scratchpad，不改 repo。」改成「寫在哪裡填「術語表」（核准前只寫草稿資料夾，照 `feature`「硬規則」第 2 條）。」原文留在 `feature:33`（需求 37 改過的硬規則 2）。
33. D21：`docs/reviews/README.md:162` 的「不引用 scratchpad 的 <功能>-grill.md，直接寫決定的內容與寫在哪裡（見 clarify-requirements「記錄決定」）。」改成「決定怎麼寫照 `.claude/skills/clarify-requirements/SKILL.md`「記錄決定」。」原文留在 `clarify-requirements:49`。
34. 這次改動中新寫的引用，都直接連到規則原文所在的那一節；被連到的那一節寫的是規則本身，不是另一個連結。

### C. 草稿資料夾（ADR 0014）

35. `.gitignore` 加上：
    ```
    # /feature、/issue 核准前的草稿（docs/decisions/0014-drafts-folder.md）
    /.drafts/
    ```
36. `docs/README.md`「流程用語」的「**scratchpad**」那一條改成：
    ```
    **草稿資料夾**：
    repo 根目錄的 `.drafts/`，放核准前的草稿與開發中的暫存檔，不會進 git。
    _避免_：scratchpad
    ```
37. 範圍內的檔案裡，「scratchpad」都改成「草稿資料夾」（每個檔案第一次出現時寫「草稿資料夾（`.drafts/`）」）。保留原文的只有三種：需求 36 的「_避免_」；`docs/decisions/README.md` 清單裡照抄 ADR 標題與狀態的文字；檔名與路徑（例如 `0010-scratchpad-loss-recovery.md`）。講到遺失的地方寫「草稿資料夾裡這次的暫存檔遺失」，不寫「草稿資料夾遺失」（例如 `feature:25`、`docs/README.md:29`）。下面幾處除了換詞，另外照這裡改：
    - `feature:32`（硬規則 1）的「plan mode 中不能寫 scratchpad」改成「plan mode 中不能寫檔案」。
    - `feature:33`（硬規則 2）改成「2. **核准前只寫草稿資料夾**（`.drafts/`），不改 repo 裡其他檔案、不開分支。這次開發的暫存檔都以 `<功能>-` 開頭，只建立 `references/resume.md` 暫存檔表上的暫存檔；種類與遺失時的恢復方式見同一張表。」
    - `write-spec:41` 的「以及第 1 次報告在 scratchpad 的路徑」改成「以及第 1 次報告與上一版規格（`<功能>-spec-v<N>.md`）在草稿資料夾的路徑」。
    - `write-spec:48` 的「每一輪的報告原文存在 scratchpad。」改成「每一輪的報告原文存成草稿資料夾的 `<功能>-spec-review-r<N>.md`。」`implement-and-review:130` 的「審查完把報告原文存在 scratchpad」改成「審查完把報告原文存成草稿資料夾的 `<功能>-impl-review-r<N>.md`」。
    - `CLAUDE.md:28` 的「`-F body=@<檔案>`」改成「`-F body=@.drafts/<功能>-pr-body.md`」（`feature-implementer` 更新 PR 描述時也用這個檔）。
    - `implement-and-review` 的「漏洞的處理」查重複那一步的「`gh api -X PATCH repos/{owner}/{repo}/security-advisories/<GHSA> --input <檔案>`」改成「先把要更新的內容寫進草稿資料夾的 `<功能>-advisory.json`，再 `gh api -X PATCH repos/{owner}/{repo}/security-advisories/<GHSA> --input .drafts/<功能>-advisory.json`」；建立 advisory 那一步的 `--input` 也寫 `.drafts/<功能>-advisory.json`。
    - `implement-and-review` 的「漏洞的處理」建立 advisory 那一步：「把下面的 JSON 寫進暫存檔（放 scratchpad，不放 repo）」改成「把下面的 JSON 寫進草稿資料夾的 `<功能>-advisory.json`」。
38. `feature`「清理暫存」最後加上：「確認完，刪掉草稿資料夾裡這次的暫存檔：只刪 `references/resume.md` 暫存檔表列出的檔名，不用「`<功能>-` 開頭」比對，避免刪到名稱開頭相同的其他功能。回報後還要修改時，照 `references/resume.md` 從 PR 分支複製回來。」
39. `feature`「取消」最後加上：「術語處理完，照「清理暫存」的方式刪掉這次的暫存檔。」
40. `resume.md` 的改法：
    - 標題改成「# 暫停、接續與暫存檔遺失」；`:3` 改成「> 什麼時候讀：暫停或接續一次開發、草稿資料夾裡這次的暫存檔遺失時。」
    - `:15` 改成「暫停與接續時，直接用草稿資料夾裡這次的暫存檔（暫存檔表列出的檔名），不用複製。」
    - `:17` 的「舊 scratchpad 不存在，或缺了部分檔案時」改成「草稿資料夾裡這次的暫存檔不見了，或缺了部分時」。
    - 暫存檔表加一列：「| advisory 的內容 | `<功能>-advisory.json` | 「漏洞的處理」建立 advisory | 以 GitHub 上的 advisory 為準（用 GHSA 編號讀回），不重建 |」。
    - 暫存檔表加一列：「| 上一版規格 | `<功能>-spec-v<N>.md` | 第 2 次規格審查送審前，把第 1 次審查時的規格存成這個檔 | 只用來比對改了什麼，不恢復；遺失時第 2 次審查只附修改內容與原因 |」。
    - 暫存檔表加一列：「| PR 描述 | `<功能>-pr-body.md` | 回報、更新 PR 描述 | 以 GitHub 上的 PR 描述為準（`gh api … --jq .body` 讀回），不重建 |」。
    - 暫存檔表「審查報告原文」那一列的檔名從「各輪報告」改成「`<功能>-spec-review-r<N>.md`、`<功能>-impl-review-r<N>.md`（N 是第幾輪）」。
    - 表前的說明「這張表是暫存檔唯一的清單。」後面加：「每一列都寫出確切的檔名；清理、取消、開始前的檢查都用這些檔名比對。」
41. ADR 0014 照 `issue-148-adr-drafts-folder.md` 存成 `docs/decisions/0014-drafts-folder.md`；`docs/decisions/README.md` 的清單加一列「| [0014](0014-drafts-folder.md) | 核准前的草稿放在 repo 內被 git 排除的 `.drafts/` | 已採用 |」。
42. 在 3 份 ADR「狀態」那一行補上被 0014 取代的部分：
    - ADR 0008：整行最後加上「；核准前只寫 scratchpad 已被 [0014](0014-drafts-folder.md) 取代」（這一行的括號在中間就關了，所以接在整行最後）。
    - ADR 0009：括號裡最後加上「；接續時把暫存檔複製到新的 scratchpad 已被 [0014](0014-drafts-folder.md) 取代」。
    - ADR 0010：括號裡最後加上「；遺失的對象（scratchpad）已被 [0014](0014-drafts-folder.md) 取代」。

    `docs/decisions/README.md` 清單裡 0008、0009、0010 的狀態欄照同樣的文字補上。3 份 ADR 的其他內容不改。

43. `feature`「流程」的「進入每個步驟前，…照它的指示做。」後面加一段：「開始前，先看草稿資料夾裡有沒有這次的暫存檔（`references/resume.md` 暫存檔表列出的檔名）。有的話，用 `clarify-requirements`「需求問答」的格式問開發者：接續（照 `references/resume.md`「暫停與接續」），還是刪掉重來（照「清理暫存」的方式刪）。開發者回答前，不讀這些檔案的內容當作已確認的決定。」

### 其他

44. PR 描述寫 `Closes #147` 與 `Closes #148`。

## 不做

- 不改程式碼、測試、`docs/api.md`、`docs/architecture.md`。
- 不改歷史規格、審查紀錄、實驗紀錄與 ADR 的內文（ADR 只改需求 42 的狀態）。
- 不把舊 scratchpad 的草稿搬進 `.drafts/`。
- 不把一組暫存檔合併成一份檔案。
- 不改除了上面列出的規則之外的任何規則；只改措辭與結構的地方，意思和原文相同。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 6 個 skill 的 `description` 和需求 1 的文字相同 |
| AC2 | 3 個階段 skill 開頭的導覽和需求 2 的文字相同，不再寫觸發時機 |
| AC3 | `implement-and-review` 有「## 步驟」一節，內容和需求 3 相同，括號裡的節名稱都存在 |
| AC4 | `clarify-requirements` 寫出只在範圍大時派 `Explore` 的原因，和需求 4 的文字相同 |
| AC5 | 需求 5 列的 7 段改成需求寫的清單，規則的意思和原文相同 |
| AC6 | `clarify-requirements` 沒有「由 Agent」「使用者提出的做法」「開發等級」 |
| AC7 | 需求 7 與需求 13 的標題、錯字、清單與連錯的節都已修正 |
| AC8 | 3 個 agent 開頭與 `feature-implementer` 步驟 3 照需求 8、9 改成清單，規則的意思和原文相同 |
| AC9 | `docs/issues.md` 有「重現步驟」欄與需求 10 的說明 |
| AC10 | `docs/specs/README.md` 的「需求」說明要求逐條編號 |
| AC11 | `docs/decisions/README.md` 有需求 12 的那一段，沒有提到「提議中」 |
| AC12 | D1–D21 每一組規則的原文只出現在需求 14–33 指定的那一處，其他位置連到那一處 |
| AC13 | `CLAUDE.md` 有「漏洞」一節，內容和需求 16 相同；需求 17 列的每個位置都是需求 17 的文字；`implement-and-review` 內部連到「漏洞的處理」的地方不變 |
| AC14 | 驗收條件要想過的情境只列在 `docs/specs/README.md`「驗收條件怎麼寫」，內容是需求 21 的完整清單 |
| AC15 | `docs/issues.md` 的驗收條件範本和 `docs/specs/README.md`「格式」的兩列例子相同 |
| AC16 | 這次新寫的每一個「照 X「某節」」，被連到的那一節寫的是規則本身，不是另一個連結 |
| AC17 | `.drafts/` 被 git 排除，`.drafts/` 裡的檔案不會出現在 `git status`，也加不進 commit（不加 `-f` 時） |
| AC18 | 範圍內的檔案裡，「scratchpad」只出現在需求 37 保留的三種地方 |
| AC19 | `feature` 的「清理暫存」「取消」寫明何時刪掉這次的暫存檔；`resume.md` 寫明接續時直接用 `.drafts/` 的檔案、不用複製 |
| AC20 | `docs/decisions/0014-drafts-folder.md` 存在，內容和 ADR 草稿相同；ADR 0008、0009、0010 與 `docs/decisions/README.md` 的狀態照需求 41、42 更新，3 份 ADR 的其他內容沒有改 |
| AC21 | 改動只包括需求 1–44 列出的內容 |
| AC22 | 新增或修改的文字裡引用的檔案路徑、節名稱都存在 |
| AC23 | PR 描述有 `Closes #147` 與 `Closes #148` |
| AC24 | `resume.md` 暫存檔表每一列都寫出確切檔名（包括審查報告原文、上一版規格與 advisory 的 JSON）；`feature` 硬規則 2 寫明只建立表上的暫存檔；`feature`「清理暫存」「取消」只刪這些檔名 |
| AC25 | `feature`「流程」寫明：開始前草稿資料夾已有這次的暫存檔時，先問開發者接續或刪掉重來 |
| AC27 | 流程裡要先寫成檔案再交給 `gh` 的內容（PR 描述、advisory 的建立與更新），在 `resume.md` 暫存檔表上都有確切檔名 |
| AC26 | 合併前開發者跑 `/doctor prompt-audit`，結果裡沒有範圍內的檔案互相矛盾、或引用不存在的檔案的發現；有的話，主 session 逐項處理 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 空資料、載入中、未登入／無權限 | 沒有改到程式、畫面與登入流程 |
| 同時操作 | 多個 session 共用 `.drafts/`：清理只刪確切檔名（AC24），開始前遇到同名舊檔先問開發者（AC25） |
| 失敗、資料處理與一致性 | 只改文件；`.drafts/` 不進 git，不影響 repo 的資料 |
| 安全性 | 漏洞的處理規則只換位置，不能公開的地方和原文相同（AC13 檢查）；審查報告原文與 advisory 的 JSON 改放被 git 排除的 `.drafts/`，push 不出去（AC17 檢查） |
| 和既有規則交會的地方 | 改到的規則都列在需求裡；其他規則不改（AC21 檢查） |

## 實作計畫

1. 從 `main` 開分支 `issue-148-process-doc-conventions`。
2. 照需求 1–13 改寫法（A）。
3. 照需求 14–34 合併重複的規則（B）。B 和 A 改到同一段時，照 B 的文字。
4. 照需求 35–43 改草稿資料夾（C），最後全文把 scratchpad 換成草稿資料夾。
5. 跑下面「測試對應」的 `grep` 檢查；只改 `.md` 與 `.gitignore`，不用跑 CLAUDE.md「完成的定義」的檢查。

改動的順序是 A → B → C：C 的換詞會改到 A、B 改過的段落，最後做才不會漏。

## 測試對應

指令寫在表格下面的程式碼區塊，依 AC 編號找；表格裡的 `|` 會被當成表格的分隔，不要從表格複製指令。`$F` 是範圍內的檔案。

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | 讀 6 個 `SKILL.md` 的 frontmatter | `description` 和需求 1 逐字相同 |
| AC2 | 讀 3 個階段 skill 開頭的導覽 | 和需求 2 逐字相同 |
| AC3 | 讀「## 步驟」；跑 AC3 的指令 | 內容和需求 3 相同；括號裡的每個節名稱都在指令結果裡，或是 `feature/SKILL.md` 的節 |
| AC4 | 跑 AC4 的指令 | 那一行和需求 4 相同 |
| AC5 | 逐段對照 `git diff origin/main...HEAD` 裡需求 5 的 7 段與原文 | 改後的文字和需求 5 相同；原文的每個條件、做法與「可以」「只有…才」這類限定都還在 |
| AC6 | 跑 AC6 的指令 | 沒有輸出 |
| AC7 | 跑 AC7 的指令；讀 `issue-triage`「3.」、`docs/reviews/README.md` 第 12、14、68 行附近與 `docs/issues.md` 的漏洞那一行 | 前兩個 grep 沒有輸出；`tail` 印出 `0a`；清單 1–4 沒有被打斷；括號、反引號成對，節名稱是需求 13 寫的 |
| AC8 | 對照 `git diff` 裡 3 個 agent 開頭與 `feature-implementer` 步驟 3 | 和需求 8、9 相同；原文的每一項輸入與動作都還在 |
| AC9 | 跑 AC9 的指令 | 「情境」有這一欄，說明和需求 10 相同 |
| AC10 | 跑 AC10 的指令 | 「需求」與「假設」各一行 |
| AC11 | 讀 `docs/decisions/README.md` 開頭；跑 AC11 的指令 | 有需求 12 的那一段；指令沒有輸出 |
| AC12 | 跑 AC12 的指令，每一組各一次 | 每一組只出現在下面程式碼區塊註解寫的檔案；寫「無」的沒有輸出 |
| AC13 | 讀 `CLAUDE.md`「漏洞」；跑 AC13 的指令 | 內容和需求 16 相同；需求 17 列的位置是需求 17 的文字；其他結果只在 `implement-and-review/SKILL.md`、`docs/reviews/README.md`、`docs/README.md`（advisory）、`acceptance-reviewer.md` 的回報格式 |
| AC14 | 跑 AC14 的指令 | 只在 `docs/specs/README.md` 兩處：「驗收條件怎麼寫」的完整清單（和需求 21 相同），以及「各等級的規格」表裡合成一列的例子 |
| AC15 | 對照 `docs/issues.md` 與 `docs/specs/README.md` 的驗收條件範本 | 「條件」欄文字相同 |
| AC16 | 列出 `git diff origin/main...HEAD` 新增行裡的每個「照 …「…」」「見 …「…」」，逐一打開被連到的節 | 每一節寫的是規則本身，不是另一個連結 |
| AC17 | 跑 AC17 的指令（不建立檔案） | 印出 `.gitignore` 裡 `/.drafts/` 那一行與 `.drafts/x-spec.md` |
| AC18 | 跑 AC18 的指令 | 只有：需求 36 的「_避免_」；`docs/decisions/README.md` 清單的 0008、0009、0010 三列；`resume.md` 裡 `0010-scratchpad-loss-recovery.md` 的檔名 |
| AC19 | 讀 `feature`「清理暫存」「取消」與 `resume.md`「暫停與接續」 | 和需求 38–40 相同 |
| AC20 | 跑 AC20 的指令 | `diff` 沒有輸出；3 份 ADR 只有「狀態」那一行改了，文字和需求 42 相同 |
| AC21 | `git diff --stat origin/main...HEAD`，再逐段對照需求 | 只改了需求列出的檔案與段落（加上規格、審查紀錄） |
| AC22 | 列出新增文字裡的每個路徑與「…」節名稱；路徑用 `ls`，節名稱跑 AC22 的指令 | 路徑都存在；每個節名稱是那個檔案的標題、粗體標籤，或寫明是哪張表的哪一列 |
| AC23 | 跑 AC23 的指令 | 兩行 |
| AC24 | 讀 `resume.md` 暫存檔表、`feature` 硬規則 2 與「清理暫存」「取消」 | 每一列的檔名欄沒有「各輪報告」這種沒有檔名的寫法，有「上一版規格」那一列；硬規則 2 和需求 37 相同；清理、取消照需求 38、39 |
| AC25 | 讀 `feature`「流程」 | 有需求 43 那一段 |
| AC27 | 跑 AC27 的指令；讀 `resume.md` 暫存檔表 | 每個 `body=@`、`--input` 後面都是 `.drafts/` 開頭的路徑，檔名是暫存檔表上的檔名（`<功能>-pr-body.md`、`<功能>-advisory.json`） |
| AC26 | 開發者在 Claude Code 跑 `/doctor prompt-audit`，把結果貼給主 session | 沒有範圍內檔案的矛盾或失效引用；有的話主 session 照 `implement-and-review`「規格問題的處理」處理 |

```bash
F="CLAUDE.md .claude/skills/*/SKILL.md .claude/skills/feature/references/resume.md .claude/agents/*.md docs/README.md docs/specs/README.md docs/reviews/README.md docs/issues.md docs/decisions/README.md"

# AC3
grep -n -e '^## ' -e '^### ' .claude/skills/implement-and-review/SKILL.md
# AC4
grep -n 'Explore' .claude/skills/clarify-requirements/SKILL.md
# AC6
grep -n -e '由 Agent' -e '使用者提出的做法' -e '開發等級' .claude/skills/clarify-requirements/SKILL.md
# AC7
grep -n '## 4\. 回報' .claude/skills/feature/SKILL.md
grep -n '以及 已確認' .claude/skills/write-spec/SKILL.md
tail -c1 .claude/skills/write-spec/SKILL.md | od -An -tx1
# AC9
grep -n '重現步驟' docs/issues.md
# AC10
grep -n '逐條編號' docs/specs/README.md
# AC11
grep -n '提議中' docs/decisions/README.md
# AC12（每一組一行；行尾註解是預期出現的檔案）
grep -n 'AskUserQuestion' $F                      # D1：只有 feature/SKILL.md
grep -n -e 'gh issue edit' -e '一定要加' $F        # D2：只有 CLAUDE.md
grep -n -e '測試名稱與 docstring' $F               # D3：只有 CLAUDE.md
grep -n -e '實際可被利用的程式漏洞' $F             # D3：只有 docs/reviews/README.md
grep -n '已核准的決定被推翻' $F                    # D4：只有 docs/reviews/README.md
grep -n '不另設類型' $F                            # D5：只有 docs/reviews/README.md
grep -n '標題開頭寫「寫法：」' $F                  # D6：只有 docs/reviews/README.md
grep -n '修正改到的程式與相關測試' $F              # D7：只有 feature/SKILL.md
grep -n '空資料' $F                                # D8：只有 docs/specs/README.md
grep -n '檢查過 AC1、AC4' $F                       # D9：只有 docs/specs/README.md
grep -n -e 'gh pr merge' -e '合併一律由開發者決定' $F  # D10：只有 CLAUDE.md
grep -n '系統要 Y' $F                              # D11：無
grep -n '最多 2 次' $F                             # D12：只有 feature/SKILL.md
grep -n -e '一律是「是」' -e '一律填「是」' $F      # D13：只有 docs/reviews/README.md
grep -n '規格審查紀錄草稿由主 session 存進' $F     # D14：無
grep -n 'git add -A' $F                            # D15：只有 CLAUDE.md
grep -n '只回「是」不算' $F                        # D16：只有 docs/reviews/README.md
grep -n '既有資料的讀取或權限' $F                  # D17：只有 docs/reviews/README.md
grep -n '不能列成「沒有錯' $F                      # D18：無
grep -n '互相衝突的是哪幾條' $F                    # D19：只有 docs/reviews/README.md
grep -n '不改 repo' $F                             # D20：只有 feature/SKILL.md
grep -n '不引用' $F                                # D21：只有 clarify-requirements/SKILL.md 與 docs/decisions/README.md 的 0009 那一列
# AC13
grep -n '漏洞' $F
# AC14
grep -n '載入中' $F
# AC17
git check-ignore -v --no-index .drafts/x-spec.md
# AC18
grep -n -i 'scratchpad' $F
# AC20
diff <ADR 草稿的路徑> docs/decisions/0014-drafts-folder.md
git diff origin/main...HEAD -- docs/decisions/0008-*.md docs/decisions/0009-*.md docs/decisions/0010-*.md
# AC22（<名稱> 換成要找的節名稱）
grep -n -e '^#.*<名稱>' -e '\*\*<名稱>\*\*' <檔案>
# AC27
grep -n -e 'body=@' -e '--input' $F
# AC23
gh api repos/{owner}/{repo}/pulls/<PR> --jq .body | grep -n 'Closes #14[78]'
```

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-20 | 需求 40 的暫存檔表加「PR 描述」`<功能>-pr-body.md`；需求 37 寫明 `CLAUDE.md:28` 的 PR 描述檔與更新 advisory 也用暫存檔表的檔名；新增 AC27 | 開發者決定要先寫成檔案再交給 `gh` 的內容都放進暫存檔表 → 需求 37、40、AC27（實作審查 #1）；檢查過 AC24、AC19 不用改，Q38「只建立表上的暫存檔」不變 | 開發者 |
| 2026-11-20 | 需求 37：advisory 的 PATCH 與 POST 的 `--input` 改寫 `.drafts/<功能>-advisory.json`；AC27 的預期結果要求 `.drafts/` 開頭的路徑 | 開發者決定 #151 在這個 PR 修、不另外審查 → 需求 37、AC27；檢查過 AC24、AC12 不用改 | 開發者 |
| 2026-11-20 | 需求 17 的 `implement-and-review:105` 改成直接連到 `docs/reviews/README.md`「涉及安全／架構」 | 開發者決定漏洞的定義直接連到原文 → 需求 17、AC16（實作審查 #2）；檢查過需求 16、AC13 不用改 | 開發者 |

## 請你決定

無
