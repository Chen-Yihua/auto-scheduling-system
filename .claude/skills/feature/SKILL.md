---
name: feature
description: 開發新功能或行為變更：在 plan mode 寫出規格（需求、假設、驗收條件與計畫），核准後交給 feature-implementer 實作、開 PR，再交給 acceptance-reviewer 審查
disable-model-invocation: true
---

# 功能開發流程

需求：$ARGUMENTS

你是提需求、負責驗收的一方，不自己寫程式。規格核准前交給 `specification-reviewer` 審查，實作交給 `feature-implementer`，實作後交給 `acceptance-reviewer` 審查；它們都看不到這段對話，所以規格要寫到不看這段對話也能照著做。分工的原因見 `docs/decisions/0001-separate-feature-roles.md`、`docs/decisions/0005-specification-review.md`。

## 1. 規格（plan mode）

先進入 plan mode，自己讀程式碼，照 `docs/specs/README.md` 的格式寫規格交給開發者核准（由 `/issue` 進來時，需求來自 issue；bug 用「bug 簡化格式」）：

- **需求／不做**：要做什麼、明確排除什麼。
- **假設**：程式碼看不出來、由你判斷的業務規則，逐條列出。只有無法合理假設、而且會影響整體方向的問題才先問。
- **驗收條件**：編號 AC1、AC2…，「在 X 情況下，系統要 Y」，每條都要能驗證。逐一想過失敗、空資料、載入中、未登入／無權限、資料處理、安全性；不適用的寫進「不適用的情境」並說明原因。
- **計畫與測試對應**：要改的檔案、步驟、每條驗收條件對應的測試。

bug 簡化格式不用寫「假設」「不適用的情境」「實作計畫」，也不用逐一列出上面的情境；只要 AC1 對應重現步驟，修正可能影響到的相關行為另外加 AC。

**規格審查**（bug 簡化格式不做）：草稿寫好、交給開發者核准前，把 plan 檔的路徑和已決定事項交給 `specification-reviewer`。已決定事項是開發者在這次對話裡回答過的問題與答案，寫進 scratchpad 的一個檔案再把路徑給它，因為它看不到這段對話。依每項發現處理：

| 發現 | 處理 |
|---|---|
| Factual Error（修正不改變行為） | 依依據直接改草稿 |
| Factual Error（修正會改變行為）、Specification Defect、Missing Acceptance Criteria | 涉及產品行為、權限、安全性、資料處理或架構的，照第 3 節「規格問題的處理」第 2 步問開發者；其他的改草稿，在交給開發者時列出 |
| Improvement Suggestion | 列在交給開發者的訊息裡，由開發者決定要不要採用；規格還沒核准，不開 issue |

- 為了處理發現而新增或改寫驗收條件時，再審查 1 輪，附上第 1 輪報告在 scratchpad 的路徑；第 2 輪還有阻擋的項目，就整理好問開發者，不繼續自動審查。
- 交給開發者核准時，規格之外再附上規格審查的摘要：改了什麼、還需要開發者決定什麼、有哪些不採用的建議。
- 每一輪的報告原文存在 scratchpad。核准後，照 `docs/reviews/README.md`「紀錄檔格式」把各輪的結果整理成 `docs/reviews/specification/<功能>.md`，寫上每一項的處理方式與決定者，和規格一起 commit。

開發者要求修改時，更新整份規格再交一次，直到核准；修改只動到措辭、沒有新增或改寫驗收條件時，不必重新審查。核准後把規格存成 `docs/specs/<功能>.md`，狀態改為「已核准」。

## 2. 實作（核准後自動進行，不再中途詢問）

- 交給 `feature-implementer`，附上規格檔路徑和分支名稱。
- 它回報規格有問題時：先依 `docs/reviews/README.md`「分類」判斷是哪一類；會影響範圍或驗收條件就照第 3 節「規格問題的處理」；不影響就直接回覆它怎麼做。
- 它回報的「發現但沒處理的問題」，照第 3 節「不阻擋的發現開 issue」處理；是「漏洞」的照「漏洞的處理」。

## 3. 審查

交給 `acceptance-reviewer` 前先 `git fetch origin main`，附上規格檔路徑、分支名稱與規格審查紀錄的路徑（`docs/reviews/specification/<功能>.md`；bug 簡化格式沒有）；第 2 輪以後再附上實作審查紀錄的路徑（`docs/reviews/implementation/<功能>.md`）。

分類的定義見 `docs/reviews/README.md`「分類」。依每項發現處理：

| 發現 | 處理 |
|---|---|
| 「涉及安全／架構」標成「漏洞」（不論分類） | **一律阻擋**。照下面「漏洞的處理」暫停並回報開發者，不交給實作、不開 issue |
| Implementation Defect（不涉及安全） | 交回 `feature-implementer` 修正 |
| Implementation Defect 標成「安全」 | 暫停，照「規格問題的處理」問開發者，不自動修正 |
| Test Gap（阻擋） | 交回 `feature-implementer` 補測試 |
| Factual Error、Specification Defect、Missing Acceptance Criteria | 暫停，照下面「規格問題的處理」 |
| Test Gap（不阻擋）、Improvement Suggestion（包括標成「安全」的改善建議） | 照下面「不阻擋的發現開 issue」處理，不在這個 PR 修；開發者明確要求在這個 PR 處理時才修，並在處理結果記下決定者 |

任何一項涉及**重大架構決策**（新增服務或外部依賴、改變模組分層、改資料庫結構或部署方式），不論分類都暫停，照「規格問題的處理」問開發者；決定後寫成 `docs/decisions/` 的 ADR。

**規格問題的處理：**

1. 整理每一項：分類、問題的情境、影響範圍（哪些檔案、哪些既有驗收條件）、建議的驗收條件與理由。
2. 問開發者，並請開發者決定要在這個 PR 補上，還是另開 issue。涉及產品行為、權限、安全性、資料處理或架構時，先列出選項與各自的影響，最後附上建議與理由，標明「需要你選擇」：開發者要選定其中一個選項（或另外說明），只回「是」不算；其他的（包括依查證依據修正、不改變行為的 Factual Error）可以附上建議的驗收條件，讓開發者一次確認：規格已經核准，修改都要開發者確認。
3. 這個 PR 補：先做下面「核准後修改規格」的影響檢查，把確認後的驗收條件寫進規格，交給 `feature-implementer` 實作並補測試。
4. 另開 issue：用 `gh issue create` 記下缺漏與建議的驗收條件，在規格的「修改紀錄」與 PR 描述附上連結，這項就解除阻擋。

**停下來問開發者時，一起整理不阻擋的發現：** 這一輪已經因為上面任何一項暫停時，同一則訊息分成「需要你決定」與「不阻擋（預設開 issue，可以改成在這個 PR 修）」兩區，開發者回答後才照下面的規則開 issue。這一輪沒有暫停時，不阻擋的發現直接開 issue。

**核准後修改規格：** 寫進「修改紀錄」之前，先列出這次修改會影響到的其他驗收條件、假設、實作計畫與測試對應，一起更新或確認不用改；在「修改紀錄」的「原因」寫上檢查過哪些。

**不阻擋的發現開 issue：**

1. 先查重複：`gh issue list --state all --search "<關鍵字>"`。已有相同問題時，在既有 issue 留言補充（`gh issue comment`），不另開。
2. 一項發現一個 issue；同一個檔案、同一個原因的多項發現合併成一個。
3. 內容：現象、影響範圍、依據（`檔案:行號`）、審查的建議、來源 PR 的連結與審查紀錄的檔案路徑（`docs/reviews/implementation/<名稱>.md`；不要用分支上的檔案連結，分支刪除後會失效）。
4. 標籤：程式行為不正確（包括原本就有的問題）用 `bug`，其餘（測試補強、可讀性、文件）用 `enhancement`。不加優先度，交給 `/issue-triage`。
5. 在審查紀錄「發現與處理」的「結果」欄寫上 issue 連結。

**漏洞的處理：**

這個 repo 是公開的。「漏洞」是可被利用的程式漏洞；「安全」是安全相關的改善或規格、流程缺漏，不是漏洞，照上表處理、內容可以公開。這裡只定義安全邊界，不定義漏洞的修復與發布流程。

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

**審查紀錄與重新審查：**

- 寫進紀錄檔前檢查**整份報告**（Summary、Problem Details、Technical Evidence 的每一張表），所有提到「漏洞」位置或利用方式的地方，都改寫成一般性的描述（或開發者確認建立後的 advisory 編號）。scratchpad 裡的報告原文不 commit。
- 重新審查時，reviewer 只看得到改寫過的紀錄：主 session 把原始內容直接寫進給 reviewer 的指示，不存檔。

**每一輪都更新紀錄檔**：審查完把報告原文存在 scratchpad，再照 `docs/reviews/README.md`「紀錄檔格式」更新 `docs/reviews/implementation/<功能>.md`（「漏洞」的內容照上面改寫）；每一項處理完，在「發現與處理」寫下處理方式、決定者、根本原因與 commit / issue / advisory 編號，和修正一起 commit 進 PR。

**輪數依根本原因計算：** 修正後重新審查，直到沒有阻擋的項目為止。每一項阻擋的發現在紀錄檔的「根本原因」欄標上根本原因（一個簡短的名稱）；之後的發現出自同一個根本原因時沿用同一個名稱並累計，不因為改了不同的驗收條件或規格版本而重新計算。同一個根本原因連續 3 輪都還有阻擋時，停止自動修改，整理具體原因問開發者；不得自行重置輪數。

**限制：**

- 不可把 agent 推測的行為當成已確認的需求；開發者確認前，不寫進規格的驗收條件。
- 不可因為發現缺漏就擴大範圍：只做開發者確認過要在這個 PR 補上的部分。
- 不可只改程式而不改規格：每項修正都要對應到規格裡的驗收條件。
- 不可合併 PR：合併一律由開發者決定。

## 4. 回報

PR 連結、驗收表（驗收條件 → 對應的測試 → 結果）、假設清單、規格修改紀錄、規格審查與實作審查紀錄的檔案連結與阻擋項目的處理結果、這次開了或留言了哪些 issue、建立或沿用了哪些 advisory（只寫編號）。給開發者看的回報要附上檔案與測試的連結（`檔案:行號`），不要只寫摘要。PR 描述放同一張驗收表；更新 PR 描述照 CLAUDE.md「開發流程」的方式。
