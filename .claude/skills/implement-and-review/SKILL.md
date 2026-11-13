---
name: implement-and-review
description: /feature 流程核准後的階段：整理交付清單交給 feature-implementer 實作、開 PR，再交給 acceptance-reviewer 審查，依發現的分類處理（修正、問開發者、開 issue、漏洞）。只在 /feature 流程中使用，不單獨觸發。
---

# 實作與審查

> 什麼時候讀：開發者核准規格之後，到回報之前。發現可被利用的漏洞時（任何階段），直接讀「漏洞的處理」。

核准後自動進行，不再中途詢問。

## Commit 責任

依文件種類分清楚由誰 commit。

| 種類 | 檔案 | 誰寫內容 | 誰 commit、push |
|---|---|---|---|
| 產品文件 | 規格（`docs/specs/`）、ADR（`docs/decisions/`）、術語表（`docs/glossary.md`） | 主 session（核准前在 scratchpad） | `feature-implementer`，照交付清單 |
| 審查紀錄 | 規格審查紀錄（`docs/reviews/specification/`）、實作審查紀錄（`docs/reviews/implementation/`） | 主 session | 主 session，commit 後 push 到同一個 PR 分支（見下面「審查紀錄的 commit」） |
| 程式碼與測試 | 其他 | `feature-implementer` | `feature-implementer` |

文字修正沒有 `feature-implementer`，照 `feature`「文字修正的流程」自己 commit。

## 交付清單

交給 `feature-implementer` 產品文件時附上，列出每個檔案的 repo 路徑與 scratchpad 來源。術語表另外列出術語，分成「新增」、「修改既有定義（開發者已確認）」與「更新本 PR 的術語」：修改要寫術語名稱、原定義與新定義；這個 PR 先前交付、`origin/main` 還沒有的術語要改定義時，標成「更新本 PR 的術語」，寫術語名稱、這個 PR 上一版的定義與新定義。

```
交付清單：
- `docs/specs/<功能>.md` ← <scratchpad>/<功能>-spec.md
- `docs/decisions/NNNN-<名稱>.md` ← <scratchpad>/<功能>-adr-<名稱>.md（沒有寫「無」）
- `docs/glossary.md` ← <scratchpad>/<功能>-glossary.md（沒有寫「無」）
  - 新增：<名稱>、<名稱>（沒有寫「無」）
  - 修改既有定義（開發者已確認）：<名稱>；原定義：<origin/main 上的定義>；新定義：<新定義>（沒有寫「無」）
  - 更新本 PR 的術語：<名稱>；上一版定義：<PR 分支上的定義>；新定義：<新定義>（沒有寫「無」）
```

術語和 `origin/main` 的比對由 `feature-implementer` 做，比對規則寫在它自己的定義裡；有相同或相近、定義不一致時它會停下來回報，處理方式見下面「交辦實作與處理回報」。

用在兩個時間點：

- 核准後第一次交辦：交付前在 scratchpad 把規格狀態改成「已核准」，再把交付清單和分支名稱交給 `feature-implementer`。主 session 不自己把規格、ADR、術語表寫進工作目錄。
- 核准後修改規格、ADR、術語表（見下面「規格問題的處理」「核准後修改規格」、核准後的重大架構決策、核准後才確定或修改的術語）：先改 scratchpad 的來源檔，同樣整理交付清單交辦，列出這次改了哪些檔案、哪些術語。

## 交辦實作與處理回報

- 交給 `feature-implementer`，附上交付清單和分支名稱。
- 它建立 PR 後會把規格開頭的「PR」補上編號、commit、push，並回報 PR 編號。收到後，以 PR 分支上已 commit 的規格為準，同步更新 scratchpad 的 `<功能>-spec.md`，之後的交付清單才不會把 PR 編號蓋回去。
- 它回報規格有問題時：先依 `docs/reviews/README.md`「分類」判斷是哪一類；會影響範圍或驗收條件就照下面「規格問題的處理」；不影響就直接回覆它怎麼做。
- 它因為「術語重複或衝突」「工作目錄有歸屬不明的改動」停下來回報時：用 `clarify-requirements`「需求問答」的格式問開發者；術語的決定照 `clarify-requirements`「新的決定一律回到決策樹」；開發者決定修改既有定義時，在交付清單把該術語改標成「修改既有定義（開發者已確認）」，寫上原定義與新定義；要改的是這個 PR 先前交付、`origin/main` 還沒有的術語時，改標成「更新本 PR 的術語」，寫上上一版定義與新定義，再交辦。
- 它回報的「發現但沒處理的問題」，照下面「不阻擋的發現開 issue」處理；是「漏洞」的照「漏洞的處理」。

## 審查紀錄的 commit

只限目前 feature 的 PR 分支與這次的 `docs/reviews/` 紀錄檔（規格審查、實作審查）。

1. commit 前確認目前分支是這次的 PR 分支，並看 `git status`。
2. 只用 `git add <這次的紀錄檔路徑>`，不帶其他未提交的修改，不用 `git add -A`、`git add .`。
3. commit 後 push 到同一個 PR 分支，再 `gh pr checks <PR> --watch` 等 CI。
4. 分支或檔案的歸屬無法確認時停止，用「需求問答」的格式問開發者。

時機：規格審查紀錄在 `feature-implementer` 回報 PR 已建立之後、交給 `acceptance-reviewer` 之前 commit（從 `<功能>-spec-review.md` 存成 `docs/reviews/specification/<功能>.md`，「PR」補上編號）；實作審查紀錄見下面「每一輪都更新紀錄檔」。

## 交給 acceptance-reviewer 審查

交給 `acceptance-reviewer` 前先 `git fetch origin main`，確認規格審查紀錄已照上面「審查紀錄的 commit」commit、push，附上規格檔路徑、等級、分支名稱、規格審查紀錄的路徑（`docs/reviews/specification/<功能>.md`）與 PR 描述全文（`gh api repos/{owner}/{repo}/pulls/<PR> --jq .body`）；第 2 輪以後再附上實作審查紀錄的路徑（`docs/reviews/implementation/<功能>.md`）。

規格審查紀錄草稿遺失、開發者決定不補時（見 `feature/references/resume.md`），改附上「沒有規格審查紀錄」與原因，跳過確認規格審查紀錄已 commit、push；`acceptance-reviewer` 照它的定義補做「完整格式的規格卻沒有規格審查紀錄」的情境檢查。

## 發現處理表

分類的定義見 `docs/reviews/README.md`「分類」。依每項發現處理，處理方式只有五種：

| 發現 | 處理 |
|---|---|
| 「涉及安全／架構」標成「漏洞」（不論分類） | **一律阻擋**。照「漏洞的處理」暫停並回報開發者，不交給實作、不開 issue |
| 阻擋，問題在程式或測試：「程式沒照規格做」、「測試抓不到錯的程式」（不涉及安全） | 請 `feature-implementer` 修正或補測試 |
| 阻擋，其餘：「規格對現有系統的描述和程式不符」、「規格內容互相矛盾或沒有依據」、「規格沒寫某個情境該怎麼做」，以及標成「安全」或涉及重大架構決策（定義見 `feature`「重大架構決策」）的任何項目 | 暫停，照「規格問題的處理」問開發者；涉及重大架構決策的，決定後寫成 scratchpad 的 ADR 草稿，照「交付清單」交給 `feature-implementer` 存進 `docs/decisions/` |
| 只換說法、意思不變的寫法問題（標題開頭是「寫法：」） | 不阻擋，由寫那份文件的人在同一個 PR 改，不開 issue：`feature-implementer` 寫的檔案請 `feature-implementer` 修正，主 session 寫的檔案由主 session 改。已核准的規格、ADR 與術語表裡的寫法問題不適用這一列，照「核准後修改規格」處理 |
| 不阻擋：「測試抓不到錯的程式」（不阻擋）、「沒有錯，但可以更好」（包括標成「安全」的改善建議；上一列的寫法問題除外） | 照「不阻擋的發現開 issue」處理，不在這個 PR 修；開發者明確要求在這個 PR 處理時才修：先照「規格問題的處理」第 3 步寫成驗收條件，再交給 `feature-implementer`，並在處理結果記下決定者 |

## 規格問題的處理

1. 整理每一項：分類、問題的情境、影響範圍（哪些檔案、哪些既有驗收條件）、建議的驗收條件與理由。
2. 用 `clarify-requirements`「需求問答」的格式問開發者，並請開發者決定要在這個 PR 補上，還是另開 issue；決定照 `clarify-requirements`「新的決定一律回到決策樹」處理。涉及產品行為、權限、安全性、資料處理或架構時，先列出選項與各自的影響，最後附上建議與理由，標明「需要你選擇」：開發者要選定其中一個選項（或另外說明），只回「是」不算；其他的（包括依查證依據修正、不改變行為的「規格對現有系統的描述和程式不符」）可以附上建議的驗收條件，讓開發者一次確認：規格已經核准，修改都要開發者確認。
3. 這個 PR 補：先做下面「核准後修改規格」的影響檢查，把確認後的驗收條件寫進 scratchpad 的規格，照「交付清單」交給 `feature-implementer` 更新規格、實作並補測試。
4. 另開 issue：用 `gh issue create` 記下缺漏與建議的驗收條件，在規格的「修改紀錄」（照「交付清單」交給 `feature-implementer`）與 PR 描述附上連結，這項就解除阻擋。

**停下來問開發者時，一起整理不阻擋的發現**：這一輪已經因為上面任何一項暫停時，同一則訊息分成「需要你決定」與「不阻擋（預設開 issue，可以改成在這個 PR 修；只換說法的寫法問題例外，不開 issue，在這個 PR 改）」兩區，開發者回答後才照「不阻擋的發現開 issue」開 issue。這一輪沒有暫停時，不阻擋的發現直接開 issue。

### 核准後修改規格

寫進「修改紀錄」之前，先列出這次修改會影響到的其他驗收條件、假設、實作計畫與測試對應，一起更新或確認不用改。「修改紀錄」的「原因」寫：決定的內容（一句話）＋寫在哪裡（規格的節或 AC 編號、ADR 編號，或「術語表」）＋檢查過哪些，例如「開發者決定一般等級也要問答 → AC3；檢查過 AC1、AC4 不用改」。

## 不阻擋的發現開 issue

1. 先查重複：`gh issue list --state all --search "<關鍵字>"`。已有相同問題時，在既有 issue 留言補充（`gh issue comment`），不另開。
2. 一項發現一個 issue；同一個檔案、同一個原因的多項發現合併成一個。
3. 內容照 `docs/issues.md`：先寫受影響的人遇到的情境，再寫技術背景、依據（`檔案:行號`）、審查的建議，最後附來源 PR 的連結與審查紀錄的檔案路徑（`docs/reviews/implementation/<名稱>.md`；不要用分支上的檔案連結，分支刪除後會失效）。
4. 標籤：程式行為不正確（包括原本就有的問題）用 `bug`，其餘（測試補強、可讀性、文件）用 `enhancement`。不加優先度，交給 `/issue-triage`。
5. 在審查紀錄「發現與處理」的「結果」欄寫上 issue 連結。

## 漏洞的處理

這個 repo 是公開的。「漏洞」是可被利用的程式漏洞；「安全」是安全相關的改善或規格、流程缺漏，不是漏洞，照「發現處理表」處理、內容可以公開。這裡只定義安全邊界，不定義漏洞的修復與發布流程。

1. 暫停目前的開發流程，不再交給 `feature-implementer` 任何修正，把漏洞的細節只寫在給開發者的回報裡。
2. 開發者決定處理方式前，漏洞的位置與利用方式不能出現在任何公開的地方：issue、PR 描述、commit 訊息、程式註解、規格檔、測試名稱與 docstring、`docs/reviews/`；也不能把修正推送到公開的 repo（包括這個 PR 的分支）。
3. 可以提出建立 private security advisory 的方案（附上要填的內容），開發者確認後才建立：
   1. 先查重複：`gh api --paginate repos/{owner}/{repo}/security-advisories --jq '.[] | {ghsa_id, summary, state}'`。已有相同問題時沿用它的 GHSA 編號，需要補充時 `gh api -X PATCH repos/{owner}/{repo}/security-advisories/<GHSA> --input <檔案>` 更新 description，不另建。
   2. 建立草稿 advisory（只有 repo 管理者看得到）：把下面的 JSON 寫進暫存檔（放 scratchpad，不放 repo），再 `gh api -X POST repos/{owner}/{repo}/security-advisories --input <檔案>`。
      ```json
      {
        "summary": "<一句話>",
        "description": "現象、影響範圍、依據（檔案:行號）、建議的修法、來源 PR",
        "severity": "low | medium | high | critical",
        "vulnerabilities": [{"package": {"ecosystem": "other", "name": "auto-scheduling-system"}}]
      }
      ```
   3. 建立失敗時，不要改開公開 issue，停下來問開發者。
4. 之後照開發者決定的方式處理；開發者決定前，這一項維持阻擋，不能讓 PR 以「沒有阻擋」結束。

## 審查紀錄與重新審查

- 寫進紀錄檔前檢查**整份報告**（「摘要」「問題說明」「技術證據」的每一張表），所有提到「漏洞」位置或利用方式的地方，都改寫成一般性的描述（或開發者確認建立後的 advisory 編號）。scratchpad 裡的報告原文不 commit。
- 重新審查時，reviewer 只看得到改寫過的紀錄：主 session 把原始內容直接寫進給 reviewer 的指示，不存檔。

### 每一輪都更新紀錄檔

審查完把報告原文存在 scratchpad，再照 `docs/reviews/README.md`「紀錄檔格式」更新 `docs/reviews/implementation/<功能>.md`（「漏洞」的內容照上面改寫）；每一項處理完，在「發現與處理」寫下處理方式、決定者、根本原因與 commit / issue / advisory 編號。每一輪整理完就照「審查紀錄的 commit」commit 並 push 到 PR 分支，最後一輪沒有修正時也一樣；請 `feature-implementer` 修正前必須已經 commit、push，否則它會把紀錄檔當成歸屬不明的改動。

### 輪數依根本原因計算

修正後重新審查，直到沒有阻擋的項目為止。每一項阻擋的發現在紀錄檔的「根本原因」欄標上根本原因（一個簡短的名稱）；之後的發現出自同一個根本原因時沿用同一個名稱並累計，不因為改了不同的驗收條件或規格版本而重新計算。同一個根本原因連續 3 輪都還有阻擋時，停止自動修改，整理具體原因問開發者；不得自行重置輪數。重新審查（第 2 輪以後）：一般等級只覆核主 session 指定的項目（修正的項目、它們的驗收條件、修正改到的程式與相關測試，以及修正可能的連帶影響）；高風險重審整個功能。看到範圍外的新問題，reviewer 仍然回報。

## 限制

- 不可把 agent 推測的行為當成已確認的需求；開發者確認前，不寫進規格的驗收條件。
- 不可因為發現缺漏就擴大範圍：只做開發者確認過要在這個 PR 補上的部分。
- 不可只改程式而不改規格：每項修正都要對應到規格裡的驗收條件。