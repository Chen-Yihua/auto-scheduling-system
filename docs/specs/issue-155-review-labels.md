# 審查發現改成一個標籤加阻擋／不阻擋

- 狀態：已核准
- 等級：一般（改流程文件裡的規則：審查發現怎麼分類、怎麼處理、何時停下來問開發者。不改程式碼，不涉及資料一致性、認證授權、憑證保護，也不是重大架構決策。推翻 ADR 0003、0005、0010、0012 的一部分，另寫 ADR 0017）
- issue：#155
- PR：#NN

## 簡短說明

審查報告的每項發現標一個標籤（`issue`、`suggestion`、`nitpick`、`question`），另外依實際影響判斷阻擋或不阻擋；主 session 依這兩件事決定怎麼處理，連續 3 輪都還有阻擋就停下來問開發者。

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/155

**問題**：開發者和主 session 讀 `specification-reviewer`、`acceptance-reviewer` 的審查報告時，每項發現要對照很多定義才能決定怎麼處理；規則越細，審查越容易找到「規則沒寫到」的地方。

**現在的規則**：

- `docs/reviews/README.md`「分類」：每項發現分開判斷 6 種類型（依根本原因）、4 種嚴重程度、阻擋合併、涉及安全／架構（漏洞／安全／架構／否）、開發者決策（需要選擇／需要確認／否）、確定程度（已驗證／推論／待確認）。阻擋依類型決定；「寫法問題」一條規定改寫的發現歸進哪個類型。
- `docs/reviews/README.md`「報告格式」：「摘要」依嚴重程度計數，表格有上面的每一欄；「技術證據」範本有「已驗證」「待確認」兩行；「處理」表有「根本原因」欄，用來累計輪數。
- `implement-and-review`「發現處理表」：依類型分成 5 種處理；「停下來問開發者時，一起整理不阻擋的發現」：沒有暫停時，不阻擋的發現直接開 issue；「不阻擋的發現開 issue」：開 issue 的步驟，`issue`、`feature` 兩個 skill 也指向這一節；「輪數依根本原因計算」：同一個根本原因連續 3 輪都還有阻擋才停止自動修改、問開發者（來自 ADR 0003）。
- `implement-and-review`「限制」最後一條與 `.claude/agents/feature-implementer.md` 第 37 行：每項修正都要對應規格裡的某條驗收條件；不對應的（例如「沒有錯，但可以更好」）`feature-implementer` 不做。
- `write-spec`「處理發現」依類型處理規格審查的發現。
- 引用舊名稱的其他地方：CLAUDE.md 第 49 行（「漏洞」與「安全」的區分指向「涉及安全／架構」）、`clarify-requirements` 第 111 行（「需要你選擇」指向「開發者決策」表）、`docs/README.md`「問題類型與嚴重程度的舊名稱」對照表、兩個 reviewer agent 的「寫法」檢查（指向「寫法問題」）。
- 一般做法：
  - [Conventional Comments](https://conventionalcomments.org/)：每則留言標一個標籤，blocking 是「解決前不應該接受」，non-blocking 是「不應該因此不接受」；nitpick「本質上不阻擋」。
  - Google〈[The Standard of Code Review](https://google.github.io/eng-practices/review/reviewer/standard.html)〉：改動確定讓整體程式碼健康度變好時就應該核准，即使不完美；技術事實與資料優先於意見和個人偏好；風格指南沒寫的純風格是個人偏好。〈[How to write code review comments](https://google.github.io/eng-practices/review/reviewer/comments.html)〉用 Nit／Optional／FYI 標出不是必改的。
  - [GitLab Code Review Guidelines](https://docs.gitlab.com/development/code_review/)：用 Conventional Comments，非必要的建議標 non-blocking；只剩 non-blocking 的建議時就往下一步，不等它們處理完；可以在後續 issue 處理的意見，和維護者討論做法。

## 需求

### 分類（`docs/reviews/README.md`「分類」）

1. 每項發現標一個標籤。標籤只描述發現的性質，用英文原名，各附一句中文定義：
   - `issue`：要修的問題，包括會影響需求或驗收條件正確性的寫法。
   - `suggestion`：可以更好的改法，包括安全改善、讓文字更清楚的改寫。
   - `nitpick`：只換說法、意思不變的小地方。
   - `question`：要開發者決定或回答的事，例如未定義的產品行為、權限、資料處理。
2. 每項發現另外標阻擋或不阻擋（沿用 `docs/README.md` 術語表的「阻擋／不阻擋」），和標籤分開判斷：
   - 問題的實際影響嚴重到照現在的規格或程式，這次 PR 不應該被接受（規格審查時是規格不應該被核准），標阻擋；否則標不阻擋。
   - 評估實際影響時，考量正確性、安全性、可靠性、是否符合需求與驗收條件，以及程式碼健康度（之後讀、改這份程式或文件的難易）。安全、架構、影響大小是評估時的考量，不是另外的分類。
   - 不要求完美才能合併：個人偏好、純風格差異、非必要的改善不阻擋。
   - `nitpick` 一律不阻擋；`issue`、`suggestion`、`question` 不由標籤決定阻擋，各自依實際影響判斷。
3. 漏洞（實際可被利用的程式漏洞）的標題開頭寫「漏洞：」，主 session 照 `implement-and-review`「漏洞的處理」處理。阻擋與否照需求 2 判斷。「漏洞的處理」第 3 步「開發者決定前，這一項維持阻擋，不能讓 PR 以『沒有阻擋』結束」改成「開發者決定前，PR 不能結束，不看 reviewer 標的阻擋」；其他步驟不變。
4. 實作審查中的 `issue`、`suggestion`，reviewer 在「建議」寫一句修正要不要改規格；涉及重大架構決策（定義見 `feature`「重大架構決策」）時也寫明。
5. 實作審查中不阻擋的 `issue`、`suggestion`，reviewer 在「建議」另外寫一句屬於哪一種：
   - 屬於這次 PR：問題出在 `git diff origin/main...HEAD` 改到的程式、測試或文件，或和某條驗收條件有關。
   - 和這次 PR 無關：其他。
6. 拿掉 6 種類型、4 種嚴重程度、「涉及安全／架構」、「開發者決策」、「確定程度」與「寫法問題」那一條；不另外訂固定的阻擋清單。
7. reviewer 沒有實際驗證的推論，在「技術原因」寫明是推論與推斷的步驟；保留「不要把推論寫成確定的事實」。
8. 「分類」裡「暫存檔遺失時」與「不做」的判斷順序保留，每一步要不要列成發現、寫在哪裡不變；列成發現的，標籤與阻擋照需求 1、2 判斷，拿掉步驟裡寫死的類型與阻擋（例如「列成發現並阻擋」、「列成『沒有錯，但可以更好』，不阻擋」都改成「列成發現」），以及「一律阻擋的規則不適用於這些情況」那一句。

### 報告格式與「處理」（`docs/reviews/README.md`）

9. 「摘要」改成依標籤與阻擋計數；摘要的表只有 #、標題、標籤、阻擋四欄。
10. 「問題說明」拿掉「開發者決策」一點，以及第 2 輪以後寫明「與第 N 輪 #M 同一根本原因」的規定；「技術原因」一點裡的類型名稱改成依內容描述（描述現有系統的，附上現有行為的依據；互相矛盾的，寫出是哪幾條）；`question` 在「建議」列出選項、各自的影響、建議與理由；開頭「嚴重程度是『不影響功能，只供參考』的項目也一樣」改成「`nitpick` 也一樣」；「技術證據」範本的「已驗證：」「待確認：」兩行改成一行「推論：」。
11. 「處理」表拿掉「根本原因」欄。「決定者」的主 session 範圍改成照 `implement-and-review`「發現處理表」與 `write-spec`「處理發現」由主 session 決定的項目；「結果」加三種：「不改：<原因>」、「不開 issue：<原因>」、「等開發者決定」。其他欄位不變。

### 實作審查的處理（`implement-and-review`）

12. 「發現處理表」改成照下面順序判斷，符合一條就停。reviewer 在「建議」沒寫需求 4、5 那一句，或寫了也分不出來時，主 session 查證後自己判斷，在「處理」的「決定者」寫主 session。
    1. 標題開頭是「漏洞：」：照「漏洞的處理」暫停並回報開發者，不交給實作、不開 issue。
    2. `question`：主 session 先查程式碼、文件能不能回答；是要開發者決定的事，用 `clarify-requirements`「需求問答」的格式問開發者。阻擋的 `question` 回答前不往下做；回答後要改規格的，照第 4 步。
    3. 涉及重大架構決策，而且沒有已核准的決定可以依循（不分阻擋與否）：照「規格問題的處理」問開發者；需要時，決定後寫 ADR 草稿，照「交付清單」交給 `feature-implementer`。
    4. 阻擋的發現，修正要改規格：照「規格問題的處理」問開發者。
    5. 阻擋的發現，不用改規格：請 `feature-implementer` 修正或補測試。
    6. `nitpick`：主 session 決定改不改，不開 issue。`feature-implementer` 寫的檔案請它改，主 session 寫的檔案自己改；已核准的規格、ADR、術語表照「核准後修改規格」。
    7. 不阻擋，屬於這次 PR：主 session 決定改不改。要改的請 `feature-implementer` 修正；修正會改變規格寫到的行為，或新增規格沒寫的行為時，改照第 4 步。不改的在「處理」寫原因。
    8. 不阻擋，和這次 PR 無關：主 session 判斷之後還需要有人處理的，照「開 issue 追蹤」開 issue；不需要的，在「處理」寫原因。開發者明確要求在這個 PR 處理時，照第 4 步寫成驗收條件再交給 `feature-implementer`。
13. 第 12 條第 6、7 步的修正，同一輪沒有阻擋的項目時，不另加一輪審查：主 session 看過修正的 diff，把修正的 commit 寫進「實作審查補充」留言。同一輪還有阻擋的項目時，修正併進下一輪審查。
14. 「輪數依根本原因計算」的第 1～3 步換成下面的規則，開頭「修正後重新審查，直到沒有阻擋的項目為止」與第 4 步（第 2 輪以後的審查範圍）保留：實作審查連續 3 輪都還有阻擋的項目時，第 3 輪的審查留言貼出後，不再交給 `feature-implementer` 任何修正（包括第 12 條第 5、7 步），「處理」的「結果」寫「等開發者決定」；主 session 照需求 18 整理後問開發者。不看是不是同一個原因。開發者決定繼續後，從下一輪重新算。規格審查最多 2 次，不適用這條。
15. 「限制」最後一條改成：修正符合下面任一項才做——對應規格的某條驗收條件；或屬於這次 PR 的品質修正（例如修註解、補測試、改寫法），不改變規格寫到的行為，也不新增規格沒寫的行為。`.claude/agents/feature-implementer.md` 第 37 行同步改成同一條規則，並寫明：修正會改變或新增行為時，`feature-implementer` 不做，回報主 session，由主 session 問開發者。
16. 「交辦實作與處理回報」裡依「分類」判斷 `feature-implementer` 回報的規格問題，改成判斷要不要改規格：要改照「規格問題的處理」，不用改直接回覆它怎麼做。
17. 「規格問題的處理」第 1 步拿掉「分類」；第 2 步第 1 點不再引用「開發者決策」表，改成和 `clarify-requirements` 同一條「需要你選擇」的規則（需求 22）。
18. 「停下來問開發者時，一起整理不阻擋的發現」改成：這一輪因為第 12 條第 1～4 步暫停（第 2 步只算阻擋的 `question`），或照需求 14 停下來時，同一則訊息分成「需要你決定」與「不阻擋的發現」兩區，後者寫主 session 對每一項的決定（改、不改、開 issue），開發者可以改；沒有暫停時，照第 12 條第 7、8 步。
19. 「不阻擋的發現開 issue」改名「開 issue 追蹤」，只寫開 issue 的步驟；第 12 條第 8 步判斷要開的才照這一節開。審查以外發現的無關問題（`issue` skill 第 40 行的開發中、`feature` skill 第 70 行的文字修正、`implement-and-review`「交辦實作與處理回報」裡 `feature-implementer` 回報的「發現但沒處理的問題」）只照第 12 條第 8 步判斷要不要開 issue，要開的才照這一節開；不開的原因，有審查留言的那一輪寫在「處理」，沒有的寫在給開發者的回報（`feature`「回報」的「這次開了或留言了哪些 issue」旁邊）；這幾處指向這一節的地方同步改名。

### 規格審查的處理（`write-spec`「處理發現」）

20. 「處理發現」改成照下面順序判斷，符合一條就停：
    1. 標題開頭是「漏洞：」：照 `implement-and-review`「漏洞的處理」。
    2. 涉及重大架構取捨，而且沒有已核准的決定可以依循：整理選項、各自的影響與建議，問開發者；需要時，決定後寫 ADR 草稿。不涉及重大決策的架構改善，照下面的步驟。
    3. `question`，或修正會改變規格寫到的行為，或新增規格沒寫的行為：照 `implement-and-review`「規格問題的處理」第 2 步問開發者。
    4. 阻擋的 `issue`、`suggestion`，修正不改變行為：主 session 依依據直接改草稿。
    5. `nitpick`：主 session 直接改草稿，不開 issue；交給開發者時列出改了哪些。
    6. 不阻擋的 `issue`、`suggestion`：列在交給開發者的訊息裡，由開發者決定採不採用；規格還沒核准，不開 issue。

    `question` 經開發者回答後，照回答改草稿；回答帶出新的重大架構取捨時，照第 2 步。

### 其他引用舊名稱的地方

21. 兩個 reviewer agent 的定義：
    - 照新的「分類」標標籤與阻擋；拿掉「只會用到四種類型」、依根本原因判斷前幾輪的說明。
    - 「寫法」檢查改成照需求 1 的標籤標（只換說法標 `nitpick`、影響需求或驗收條件正確性標 `issue`、讓文字更清楚標 `suggestion`），不再指向「寫法問題」。
    - 等級判斷偏低、改動實際的影響比等級高時，標 `issue`，寫出應該是哪個等級與理由；阻擋照需求 2。
    - 「涉及安全／架構」填「漏洞」那一段，改成標題開頭是「漏洞：」時。
    - `specification-reviewer` 的「事實」檢查「對不上的就是『規格對現有系統的描述和程式不符』」改成「對不上的標 `issue`」；「範圍外的想法最多列成『沒有錯，但可以更好』」改成「範圍外的想法最多標 `suggestion`」，阻擋照需求 2。
    - `acceptance-reviewer`「不阻擋的發現（標題開頭是「寫法：」的除外）會被拿去開 issue」改成「和這次 PR 無關的不阻擋發現可能被拿去開 issue」。
22. `clarify-requirements` 第 111 行的「需要你選擇」改成寫在本檔：列出選項與各自的影響，附上建議與理由；開發者要選定一個選項或另外說明，只回「是」不算。
23. CLAUDE.md 第 49 行改成「『漏洞』與一般安全改善怎麼區分」，指向 `docs/reviews/README.md` 裡定義漏洞的位置。
24. `docs/README.md`「問題類型與嚴重程度的舊名稱」對照表保留，表頭「舊名稱｜新名稱」改成「英文舊名稱｜中文名稱（ADR 0017 以前）」，表後那一行改成：這些類型與嚴重程度已由 ADR 0017 改成標籤加阻擋，讀舊紀錄時用這張表對照。

### ADR 與舊規格

25. 新增 ADR 0017「審查發現改用 Conventional Comments 標籤」，檔名 `docs/decisions/0017-review-findings-conventional-labels.md`。
26. 下面四份 ADR 只改狀態行，寫明被 0017 取代的部分；`docs/decisions/README.md` 清單加 0017，0003、0005、0010、0012 的狀態欄同步：
    - ADR 0003：「不阻擋的審查發現自動開 issue」、「只定義安全邊界」裡「實際漏洞一律阻擋」與「安全改善建議分開分類」兩句、「審查輪數依根本原因計算」、「暫停的條件」裡「實際漏洞（一律阻擋）」與標成「安全」的那兩項。
    - ADR 0005：「審查分類依根本原因」、「不阻擋的發現在同一則訊息裡一起問，回答後才開 issue」。
    - ADR 0010：「審查豁免」裡「才列為發現並阻擋」的「並阻擋」，以及「影響」裡「保留三種實際風險仍然阻擋」。
    - ADR 0012：決定 3「審查發現的去處只有四種」與「只有涉及產品行為、權限、安全性、資料處理或架構的才問開發者」。
27. 舊規格只改狀態行，標成部分被這份規格取代：
    - `issue-154-review-comments.md`：AC6 的「根本原因」欄。
    - `writing-rules.md`：AC23、AC24。
    - `issue-139-protection-scope.md`：AC5、AC7、AC8。
    - `issue-148-process-doc-conventions.md`：AC12 裡的 D5（寫法問題不另設類型）、D6（「寫法：」的標法）、D13（漏洞一律阻擋）、D16（「需要你選擇」的位置）、D17（等級偏低的分類）、D18（會讓驗收條件不成立的發現的分類），以及輪數依根本原因計算的規則。

## 不做

- 不改 `docs/reviews/specification/`、`docs/reviews/implementation/`、`docs/reviews/*-round<N>.md` 的既有紀錄。
- 不改 `docs/experiments/feature-grill/` 的實驗紀錄（實驗已結束，有自己的嚴重程度定義）。
- 不改「漏洞的處理」的流程（需求 3 那一句除外）與 CLAUDE.md「漏洞」的規則，只改漏洞怎麼標、指向哪裡。
- 不加 Conventional Comments 的其他標籤（`praise`、`todo`、`thought`、`chore` 等）與裝飾詞（decoration）。
- 不改 `clarify-requirements` 第 139 行、`docs/specs/README.md` 第 88 行的「確認根本原因」：講的是修 bug 前找原因，不是審查分類。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 開發者讀 `docs/reviews/README.md`「分類」，看得到 4 個標籤，各一句定義 |
| AC2 | 開發者讀 `docs/reviews/README.md`「分類」，看得到阻擋依實際影響判斷：寫著需求 2 的判斷方式、要考量的五項，以及不要求完美、偏好與純風格不阻擋；沒有固定的阻擋清單 |
| AC3 | 開發者讀 `docs/reviews/README.md`「分類」，看得到 `nitpick` 一律不阻擋，其他標籤不由標籤決定阻擋 |
| AC4 | 開發者讀 `docs/reviews/README.md`「分類」，沒有類型、嚴重程度、涉及安全／架構、開發者決策、確定程度、寫法問題的小節或條目 |
| AC5 | 開發者讀 `docs/reviews/README.md`「分類」，看得到漏洞的標法：標題開頭寫「漏洞：」，處理照「漏洞的處理」；`implement-and-review`「漏洞的處理」第 3 步是需求 3 的新寫法 |
| AC6 | 開發者讀 `docs/reviews/README.md`「分類」，看得到實作審查的 `issue`、`suggestion` 要在「建議」寫要不要改規格，涉及重大架構決策時寫明 |
| AC7 | 開發者讀 `docs/reviews/README.md`「分類」，看得到實作審查不阻擋的 `issue`、`suggestion` 要寫屬於這次 PR 或和這次 PR 無關，以及兩者的定義 |
| AC8 | 開發者讀 `docs/reviews/README.md`「分類」的「暫存檔遺失時」與「不做」的判斷順序，每一步要不要列成發現、寫在哪裡和改前一樣，步驟裡沒有寫死的類型或阻擋 |
| AC9 | 開發者讀 `docs/reviews/README.md`「報告格式」，摘要依標籤與阻擋計數，表只有 #、標題、標籤、阻擋 |
| AC10 | 開發者讀 `docs/reviews/README.md`「報告格式」，「問題說明」沒有「開發者決策」、「同一根本原因」與類型名稱，寫著 `question` 的選項與建議放在「建議」；「技術證據」範本沒有「已驗證」「待確認」 |
| AC11 | 開發者讀 `docs/reviews/README.md`「處理」，表沒有「根本原因」欄；「決定者」與「結果」照需求 11 |
| AC12 | 開發者讀 `implement-and-review`「發現處理表」，看得到需求 12 的 8 步與步驟前那一句，照順序判斷、符合一條就停 |
| AC13 | 開發者讀 `implement-and-review`，看得到第 6、7 步的修正在同一輪沒有其他阻擋時不另加一輪審查，寫進「實作審查補充」留言 |
| AC14 | 開發者讀 `implement-and-review`，看得到實作審查連續 3 輪都還有阻擋時，第 3 輪留言貼出後不再交辦任何修正、問開發者，開發者決定繼續後從下一輪重新算；沒有根本原因的計算；第 2 輪以後審查範圍那一步還在 |
| AC15 | 開發者讀 `implement-and-review`「限制」與 `.claude/agents/feature-implementer.md`，兩處都寫著需求 15 的同一條規則；`feature-implementer.md` 寫著修正會改變或新增行為時不做、回報主 session |
| AC16 | 開發者讀 `implement-and-review`「交辦實作與處理回報」，`feature-implementer` 回報的規格問題依要不要改規格處理，不引用「分類」 |
| AC17 | 開發者讀 `implement-and-review`「規格問題的處理」，第 1 步沒有「分類」，第 2 步第 1 點不引用「開發者決策」表 |
| AC18 | 開發者讀 `implement-and-review`，停下來問開發者時的兩區寫法照需求 18，沒有「不阻擋的發現直接開 issue」 |
| AC19 | 開發者讀 `implement-and-review`，有「開 issue 追蹤」一節，只寫開 issue 的步驟；第 12 條第 8 步與需求 19 列的三處都先照第 8 步判斷，要開的才用這一節；三處指向這一節的名稱相同 |
| AC20 | 開發者讀 `write-spec`「處理發現」，看得到需求 20 的 6 步與 `question` 回答後的那一句 |
| AC21 | 開發者讀兩個 reviewer agent 的定義，看得到需求 21 的每一點 |
| AC22 | 開發者讀 `clarify-requirements`，「需要你選擇」的規則寫在本檔，不引用「開發者決策」表 |
| AC23 | 在 `CLAUDE.md`、`.claude/`、`docs/reviews/README.md`、`docs/specs/README.md`、`docs/README.md`、`docs/issues.md` 跑 `grep -rn "嚴重程度\|根本原因\|問題類型\|涉及安全／架構\|開發者決策\|確定程度\|沒有錯，但可以更好\|程式沒照規格做\|測試抓不到錯的程式\|規格沒寫某個情境\|規格內容互相矛盾\|規格對現有系統\|寫法：\|寫法問題\|已驗證\|待確認\|需要確認\|「安全」\|不阻擋的發現開 issue"`，每一行都不是在用舊規則：只剩 `docs/README.md` 的舊名稱對照表與它的標題、說明，「不做」列出的兩處，以及意思不同的「待確認」（`docs/issues.md` 第 51 行、`resume.md` 第 38 行）與「寫法：」（`docs/README.md` 第 11 行「GitHub issue 的寫法：」） |
| AC24 | 開發者讀 CLAUDE.md「漏洞」前的說明，寫的是「漏洞」與一般安全改善的區分，指向 `docs/reviews/README.md` 裡定義漏洞的位置，那個位置存在 |
| AC25 | 開發者讀 `docs/README.md` 的舊名稱對照表，表頭與表後那一行照需求 24 |
| AC26 | `docs/decisions/0017-review-findings-conventional-labels.md` 存在；`docs/decisions/README.md` 清單有 0017 那一列，連到這個檔名 |
| AC27 | ADR 0003、0005、0010、0012 只改狀態行，寫明需求 26 列的被取代部分；`docs/decisions/README.md` 裡四者的狀態欄同步 |
| AC28 | 需求 27 的 4 份舊規格只改狀態行，寫明被取代的部分 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限、資料處理與一致性、同時操作 | 只改流程文件，不改程式、畫面、API 與資料 |
| 安全性 | 漏洞的處理流程（第 3 步那一句除外）與 CLAUDE.md「漏洞」的規則不變（需求 3、不做），只改漏洞的標法與指向的位置（AC5、AC24） |
| 和既有規則交會 | 「不做」判斷順序與暫存檔遺失由 AC8 涵蓋；改寫的發現由需求 1、21 涵蓋；重大架構決策由需求 12 第 3 步、需求 20 第 2 步涵蓋；規格核准後的修改由需求 12 第 4 步涵蓋 |

## 實作計畫

用 AC23 的 `grep` 找到的每一處逐一改寫（「不做」列出的檔案不改），再對照需求 18、19 改 grep 找不到的段落。主要的改動：

1. **`docs/reviews/README.md`**
   - 「分類」整節改寫：開頭一段說明標籤描述性質、阻擋另外依實際影響判斷，參考 Conventional Comments、Google、GitLab；小節「標籤」（需求 1）、「阻擋」（需求 2、4、5）、「漏洞」（需求 3）；保留「暫存檔遺失時」與「不做」判斷順序（需求 8）、推論的寫法（需求 7）；刪掉「問題類型」「嚴重程度」「涉及安全／架構」「開發者決策」「確定程度」各小節與「寫法問題」那一條。
   - 「報告格式」照需求 9、10；「處理」照需求 11；高風險的「安全與一致性檢查」表最後一行「『沒有涵蓋』的項目依根本原因列成發現」改成「列成 `issue`，阻擋照『阻擋』判斷」。
   - 「處理」的「決定者」例子改成「阻擋的發現，不用改規格」。
2. **`implement-and-review`**：步驟 6 改指向新的停止規則；「交辦實作與處理回報」照需求 16 與需求 19 的改名；「審查留言」第 2、6 步的「不阻擋的發現開 issue」「寫法：」改成新名稱與 `nitpick`；「發現處理表」照需求 12；新增需求 13 的規則（放在「審查留言」第 6 步或「發現處理表」下）；「規格問題的處理」照需求 17、18；「不阻擋的發現開 issue」照需求 19；「輪數依根本原因計算」改名「重新審查與連續 3 輪都還有阻擋」，內容照需求 14；「限制」照需求 15；「漏洞的處理」開頭指向的漏洞定義改成新位置。
3. **`write-spec`「處理發現」**：照需求 20。
4. **兩個 reviewer agent**：照需求 21。
5. **`feature-implementer`**：第 37 行照需求 15；「寫法：」改成 `nitpick`。
6. **`clarify-requirements`**：第 111 行照需求 22。
7. **`issue`、`feature` skill**：照需求 19 改指向的節名。
8. **CLAUDE.md** 第 49 行照需求 23。
9. **`docs/README.md`** 照需求 24。
10. **ADR**：新增 `docs/decisions/0017-review-findings-conventional-labels.md`（交付清單）；0003、0005、0010、0012 的狀態行與 `docs/decisions/README.md` 照需求 26。
11. **舊規格**：照需求 27，只改狀態行，例如「部分被 [issue-155-review-labels.md](issue-155-review-labels.md) 取代（AC6 的「根本原因」欄）」。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | 讀 `docs/reviews/README.md`「分類」 | 4 個標籤，各一句定義，和需求 1 相同 |
| AC2 | 同上 | 需求 2 的判斷方式與五項考量；不要求完美、偏好與純風格不阻擋；沒有編號的阻擋條件清單 |
| AC3 | 同上 | `nitpick` 一律不阻擋；`issue`、`suggestion`、`question` 依實際影響判斷 |
| AC4 | 同上 | 沒有那 6 種小節或條目 |
| AC5 | 同上；讀 `implement-and-review`「漏洞的處理」第 3 步 | 「漏洞：」開頭；處理照「漏洞的處理」；第 3 步寫「開發者決定前，PR 不能結束，不看 reviewer 標的阻擋」 |
| AC6 | 同上 | 實作審查的 `issue`、`suggestion` 寫要不要改規格與是否涉及重大架構決策 |
| AC7 | 同上 | 不阻擋的寫屬於這次 PR 或無關，兩者有定義（`git diff origin/main...HEAD` 或和某條 AC 有關） |
| AC8 | `git diff origin/main -- docs/reviews/README.md`，逐步對照「暫存檔遺失時」2 步與「不做」6 步 | 每一步「列成發現」「不列成發現」「寫在已接受的風險」和改前相同；步驟裡沒有類型名稱或「阻擋」「不阻擋」 |
| AC9 | 讀「報告格式」 | 摘要依標籤與阻擋計數；表 4 欄 |
| AC10 | 同上 | 「問題說明」沒有「開發者決策」「同一根本原因」與類型名稱；`question` 的選項與建議寫在「建議」；「技術證據」範本有「推論：」，沒有「已驗證：」「待確認：」 |
| AC11 | 讀「處理」 | 表沒有「根本原因」；「決定者」的主 session 範圍指向兩張處理表；「結果」有「不改：<原因>」「不開 issue：<原因>」「等開發者決定」 |
| AC12 | 讀 `implement-and-review`「發現處理表」 | 步驟前那一句、8 步，順序與內容同需求 12，前面寫明符合一條就停 |
| AC13 | 讀 `implement-and-review` | 寫著需求 13 |
| AC14 | 讀 `implement-and-review` 原「輪數依根本原因計算」的位置與「步驟」第 6 步 | 連續 3 輪、第 3 輪留言貼出後不再交辦任何修正、問開發者、繼續後重新算；沒有「根本原因」；開頭一句與第 2 輪以後審查範圍那一步還在 |
| AC15 | 讀 `implement-and-review`「限制」與 `.claude/agents/feature-implementer.md` | 兩處都是需求 15 的兩種情況；`feature-implementer.md` 寫著會改變或新增行為時不做、回報主 session |
| AC16 | 讀「交辦實作與處理回報」 | 依要不要改規格分流，沒有「分類」 |
| AC17 | 讀「規格問題的處理」 | 第 1 步沒有「分類」；第 2 步第 1 點是「需要你選擇」的規則，沒有「開發者決策」 |
| AC18 | 讀原「停下來問開發者時，一起整理不阻擋的發現」的位置 | 兩區照需求 18；沒有「不阻擋的發現直接開 issue」 |
| AC19 | 讀 `implement-and-review`「開 issue 追蹤」；`grep -n "開 issue 追蹤" .claude/skills/issue/SKILL.md .claude/skills/feature/SKILL.md .claude/skills/implement-and-review/SKILL.md` | 這一節只寫開 issue 的步驟；第 12 條第 8 步與需求 19 的三處都先照第 8 步判斷，要開的才用這一節；三個 skill 都用這個名稱 |
| AC20 | 讀 `write-spec`「處理發現」 | 需求 20 的 6 步與最後一句 |
| AC21 | 讀 `.claude/agents/specification-reviewer.md`、`.claude/agents/acceptance-reviewer.md` | 需求 21 的 6 點都有（第 5 點只看 `specification-reviewer`，第 6 點只看 `acceptance-reviewer`） |
| AC22 | 讀 `clarify-requirements`「需求問答」 | 「需要你選擇」的規則寫在本檔，沒有「開發者決策」 |
| AC23 | 跑 AC23 的 `grep`，逐行看 | 每一行都是 AC23 列出可以保留的地方 |
| AC24 | 讀 CLAUDE.md 第 49 行，打開它指向的節 | 寫「漏洞」與一般安全改善的區分；那一節定義漏洞 |
| AC25 | 讀 `docs/README.md` 舊名稱對照表 | 表頭「英文舊名稱｜中文名稱（ADR 0017 以前）」；表後那一行指向 ADR 0017 |
| AC26 | `ls docs/decisions/0017-review-findings-conventional-labels.md`；讀 `docs/decisions/README.md` 清單 | 檔案存在；清單有 0017 那一列，連結是這個檔名 |
| AC27 | `git diff origin/main -- docs/decisions/0003-* docs/decisions/0005-* docs/decisions/0010-* docs/decisions/0012-* docs/decisions/README.md` | 四份 ADR 只改狀態行，列出需求 26 的部分；清單的狀態欄一致 |
| AC28 | `git diff origin/main -- docs/specs/issue-154-review-comments.md docs/specs/writing-rules.md docs/specs/issue-139-protection-scope.md docs/specs/issue-148-process-doc-conventions.md` | 每個檔案只改狀態行，寫明需求 27 列的部分 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
