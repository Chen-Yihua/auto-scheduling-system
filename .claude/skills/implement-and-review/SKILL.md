---
name: implement-and-review
description: 整理交付清單交給 feature-implementer 實作與開 PR、交給 acceptance-reviewer 審查、依發現的分類處理。在 /feature 開發者核准規格後載入，用到回報為止。只在 /feature 流程中使用，不單獨觸發。
---

# 實作與審查

> 任何階段發現漏洞，直接讀「漏洞的處理」。「發現處理」也給規格審查用。

核准後照步驟一路做下去，只有下面寫明要問開發者時才停。

## 步驟

照順序做，因為每一步都用到前一步的結果（PR 建好才能貼留言，留言貼出才能附給 reviewer）：

1. 整理交付清單，交給 `feature-implementer` 實作、開 PR。
2. PR 建好後，貼規格審查每一輪的留言（有的話）。
3. 交給 `acceptance-reviewer` 審查。
4. 處理每項發現，要修的交給 `feature-implementer`。
5. 這一輪的修正都 commit 後，貼這一輪的留言。
6. 還有阻擋就回到第 3 步。
7. 沒有阻擋後，照 `feature`「回報」回報。

## 交付清單

規格、ADR、術語表由你在草稿資料夾寫，由 `feature-implementer` 放進 repo 並 commit；你不自己寫進工作目錄。交付清單列出每個檔案的 repo 路徑與草稿資料夾的來源：

```
交付清單：
- `docs/specs/<功能>.md` ← .drafts/<功能>-spec.md（快速路徑寫「PR 描述 ← .drafts/<功能>-spec.md（快速路徑）」）
- `docs/decisions/NNNN-<名稱>.md` ← .drafts/<功能>-adr-<名稱>.md（沒有寫「無」）
- `docs/glossary.md` ← .drafts/<功能>-glossary.md（沒有寫「無」）
  - 新增：<名稱>、<名稱>（沒有寫「無」）
  - 修改既有定義（開發者已確認）：<名稱>；原定義：<origin/main 上的定義>；新定義：<新定義>（沒有寫「無」）
```

- 第一次交辦：先在草稿把規格狀態改成「已核准」，再把交付清單和分支名稱交給 `feature-implementer`。`/issue` 另外要求 PR 描述加上 `Closes #<N>`。
- 核准後要改規格、ADR、術語表：先改草稿資料夾的來源，再交一份新的交付清單，列出這次改了什麼。

文字修正沒有 `feature-implementer`，照 `feature`「文字修正的流程」自己 commit。

## 處理 feature-implementer 的回報

- **PR 建好**：它會把 PR 編號補進規格開頭並 push。以 PR 分支上的規格為準，同步更新草稿的 `<功能>-spec.md`，之後的交付清單才不會把編號蓋掉。
- **規格有問題**：要改規格就照「規格問題的處理」；不用改就直接回覆它怎麼做。
- **術語重複或衝突、工作目錄有歸屬不明的改動**：問開發者，依決定更新交付清單後再交辦。
- **發現但沒處理的問題**：照「發現處理」。

## 交給 acceptance-reviewer

先 `git fetch origin main`，附上：

- 規格檔路徑（快速路徑沒有，等級寫「一般（快速路徑）」）、等級、分支名稱、PR 編號。
- PR 描述全文（`gh api repos/{owner}/{repo}/pulls/<PR> --jq .body`）。
- 規格審查每一輪留言的連結；沒有規格審查時寫「沒有規格審查」與原因，reviewer 會補做規格的檢查。
- 第 2 輪起：前幾輪實作審查留言的連結，以及這一輪的範圍（`feature`「判斷等級」表的「實作審查」欄）。

## 發現處理

規格審查與實作審查共用；標籤見 `docs/reviews/README.md`。一項發現可能同時符合好幾條，所以照順序判斷，符合就停：漏洞先擋住細節外流，要開發者決定的先問，才不會改了又退回。

| # | 情況 | 核准前（規格審查） | 核准後（實作審查） |
|---|---|---|---|
| 1 | 標題開頭是「漏洞：」 | 照「漏洞的處理」 | 照「漏洞的處理」，不交給實作、不開 issue |
| 2 | 要開發者決定：`question`；修正會改變或新增規格沒寫的行為；核准後要改已核准的規格、ADR 或術語表；涉及沒核准過的重大架構決策 | 先查程式碼與文件能不能回答；不能就照「規格問題的處理」問 | 同左。阻擋的在開發者回答前不往下做 |
| 3 | 阻擋，不用開發者決定 | 你照依據改草稿 | 交給 `feature-implementer` 修正或補測試 |
| 4 | `nitpick` | 你直接改草稿，核准時列出改了什麼 | 你決定改不改，不開 issue |
| 5 | 不阻擋，屬於這次 PR | 列在核准的訊息裡，附你的建議，由開發者決定 | 你決定改不改；要改的交給 `feature-implementer`，不改的寫原因 |
| 6 | 不阻擋，和這次 PR 無關 | 列在核准的訊息裡，不開 issue | 之後還要有人處理的照「開 issue 追蹤」開；不需要的寫原因 |

- reviewer 沒寫清楚要不要改規格、屬不屬於這次 PR 時，你查證後自己判斷，「決定者」寫主 session。
- 實作審查第 4、5 條的修正：同一輪沒有阻擋時，不另加一輪審查，你看過 diff，把 commit 寫進這一輪的「處理」；同一輪還有阻擋時，併進下一輪審查。
- 停下來問開發者時，同一則訊息分成「需要你決定」與「不阻擋的發現」兩區；後者寫你對每一項的決定（改、不改、開 issue），開發者可以改。
- 開發者回答後照 `clarify-requirements`「新的決定」。

## 規格問題的處理

1. 整理每一項：問題的情境、影響範圍（哪些檔案、哪些 AC）、建議的驗收條件與理由。
2. 用 `clarify-requirements`「需求問答」的格式問開發者。核准後的問題，另外請開發者選：在這個 PR 補，還是另開 issue。
3. 依開發者的決定：
   - **這個 PR 補**：先列出會受影響的其他 AC、假設、實作計畫與測試對應，一起更新或確認不用改；把確認後的驗收條件寫進草稿，記在規格的「修改紀錄」（`docs/specs/README.md`「核准後」），再照「交付清單」交給 `feature-implementer`。快速路徑照 `feature`「快速路徑」。
   - **另開 issue**：用 `gh issue create` 記下缺漏與建議的驗收條件，在規格的「修改紀錄」（快速路徑是那一輪的「處理」）與 PR 描述附上連結。這項就不再阻擋。

## 審查留言

每一輪審查（規格或實作）各貼一則公開的 PR 留言：報告原文加上這一輪的「處理」，讀者在一個地方就看得到發現了什麼、怎麼處理。照順序做：

1. 報告原文存成 `<功能>-spec-review-r<N>.md` 或 `<功能>-impl-review-r<N>.md`。
2. 處理完每項發現：決定處理方式、開好 issue、修正都 commit。
3. 在同一份檔案加上：
   - 第一行：`## <功能>：規格審查第 N 輪` 或 `## <功能>：實作審查第 N 輪（commit <sha>）`。
   - 「技術證據」包進 `<details><summary>技術證據</summary>` … `</details>`。
   - 最後一節「處理」（格式見 `docs/reviews/README.md`「處理」）。
4. 有「漏洞：」的發現時，報告原文要留給重新審查用，所以另外複製成 `<…>-comment.md`，在副本照「漏洞的處理」第 4 步改寫，貼副本。
5. `gh pr comment <PR> --body-file <檔案>` 貼出，印出的網址就是留言連結。

留言貼出後不修改。最後一輪之後才有的修正（例如開發者後來要求的），你看過 diff，在 commit 訊息寫清楚原因；改到驗收條件的，記進修改紀錄並再審一輪。

## 開 issue 追蹤

1. 先查重複：`gh issue list --state all --search "<關鍵字>"`。已有相同問題時，在既有 issue 留言補充，不另開。
2. 一項發現一個 issue；同一個檔案、同一個原因的合併成一個。
3. 內容照 `docs/issues.md`，最後附「來源：PR #NN 第 N 輪規格審查／實作審查 #M」。
4. 程式行為不正確（包括原本就有的問題）標 `bug`，其他（測試補強、可讀性、文件）標 `enhancement`。不加優先度，交給 `/issue-triage`。
5. 在這一輪「處理」的「結果」寫上 issue 連結。

## 漏洞的處理

漏洞的定義見 `docs/reviews/README.md`「漏洞」，細節不能出現的地方見 CLAUDE.md「漏洞」。照順序做：先暫停，修正才不會被推到公開的 repo；先查重複，同一個漏洞才不會有兩份 advisory。

1. 暫停開發，不再交給 `feature-implementer` 任何修正。
2. 提出建立 private security advisory 的方案（附上要填的內容），開發者確認後才建立：
   1. 查重複：`gh api --paginate repos/{owner}/{repo}/security-advisories --jq '.[] | {ghsa_id, summary, state}'`。已有相同問題時沿用它的 GHSA 編號；要補充時把內容寫進 `.drafts/<功能>-advisory.json`，用 `gh api -X PATCH repos/{owner}/{repo}/security-advisories/<GHSA> --input .drafts/<功能>-advisory.json` 更新。
   2. 建立草稿 advisory（只有 repo 管理者看得到）：把下面的 JSON 寫進 `.drafts/<功能>-advisory.json`，再 `gh api -X POST repos/{owner}/{repo}/security-advisories --input .drafts/<功能>-advisory.json`。
      ```json
      {
        "summary": "<一句話>",
        "description": "現象、影響範圍、依據（檔案:行號）、建議的修法、來源 PR",
        "severity": "low | medium | high | critical",
        "vulnerabilities": [{"package": {"ecosystem": "other", "name": "auto-scheduling-system"}}]
      }
      ```
   3. 建立失敗時，不改開公開 issue，停下來問開發者。
3. 之後照開發者決定的方式處理；開發者決定前，不管 reviewer 標的阻擋，PR 都不能結束。
4. 貼留言前，在副本檢查整份報告（摘要、問題說明、技術證據的每一張表），把提到漏洞位置或利用方式的地方，改寫成一般性的描述或 advisory 編號。原文不動、不 commit。重新審查時 reviewer 只看得到改寫過的留言，所以把原始內容直接寫進給 reviewer 的指示。

## 重新審查

修正後重新審查，直到沒有阻擋。連續好幾輪都還有阻擋，通常是規格或做法本身有問題，再交回實作也修不好，所以：

1. 實作審查連續 3 輪都還有阻擋時（不論是不是同一個原因），第 3 輪的「結果」寫「等開發者決定」，貼出後不再交給 `feature-implementer` 修正，照「發現處理」整理後問開發者。
2. 開發者決定繼續後，從下一輪重新算。

規格審查的次數見 `write-spec`。

## 限制

- agent 推測的行為不是已確認的需求；開發者確認前，不寫進驗收條件。
- 發現缺漏也不擴大範圍：只做開發者確認要在這個 PR 補的部分。
