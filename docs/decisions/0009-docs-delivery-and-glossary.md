# 0009. 修改紀錄寫決定與落點、引進術語表、產品文件照交付清單由 implementer commit

- 狀態：已採用（C、Q 編號規則已被 [0012](0012-simplify-process-levels.md) 取代；不引用 scratchpad 的原則沿用）
- 日期：2026-11-09

## 背景

[0008](0008-grilling-without-plan-mode.md) 讓 `/feature` 用 Context（開發者確認過的資訊，編號 C1、C2…）與 Frontier（還要問的問題，編號 Q1、Q2…）追蹤問答，兩者寫在 scratchpad、不 commit；但同一份 ADR 要求規格的修改紀錄在「原因」寫 C 編號。PR 合併、session 結束後，讀規格的人看到 C 編號，在 repo 裡查不到它是什麼決定（issue #69）。

開發者決定參考 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `grill-with-docs`（commit `4ae2317`，MIT 授權）：決定一確定就落在持久的位置，專案自己的用詞一確定就寫進術語表，用詞不一致或模糊時馬上問清楚。它沒有處理規格、分支、commit、多人同時寫入與取消，所以只整合問答、用詞規則與術語表；檔案由誰、在什麼時候 commit，由這個 repo 的流程定義。

另外，文字修正以外的等級由 `feature-implementer` 開分支，它的規則只寫「規格檔要一起 commit」，規格審查紀錄、ADR 要不要一起 commit 靠推斷；審查紀錄「和修正一起 commit」沒有寫由誰 commit，最後一輪沒有修正時也沒有人 push。開發者通常同時開著自己的編輯器與 dev server，工作目錄可能有不屬於這次開發的改動。

## 決定

- **修改紀錄寫決定與落點**：規格核准後的修改紀錄，「原因」寫「決定的內容（一句話）＋落點（規格的節或 AC、ADR，或術語表）＋檢查過哪些」，有規格的等級都適用。
- **C、Q 編號只在 scratchpad 用**：寫進規格、審查紀錄、ADR、術語表、PR 描述、issue、commit 訊息時，不寫指向 Context／Frontier 項的引用，換成決定的內容與落點；說明編號制度本身、描述既有紀錄的文字不算。問答與寫規格階段的決定只留在規格，不記進審查紀錄的「開發者決策」表。檢查分給 `specification-reviewer`（規格與 ADR 草稿）、`acceptance-reviewer`（規格、ADR、術語表、兩份審查紀錄、commit 訊息、PR 描述）與主 session（開 issue 前、回報前確認最後一次審查之後才產生的內容），不加自動化檢查。
- **術語表**：`docs/glossary.md`，只收產品領域、使用者看得到的概念，格式照 `domain-modeling` 的 `GLOSSARY-FORMAT`（繁體中文），定義在 `/feature`；第一個術語合併時才建立。標準、高風險在核准前確定的術語寫進 scratchpad 的 `<功能>-glossary.md`，核准後由 `feature-implementer` 對照 `origin/main` 後合併：新增的術語在 `origin/main` 有相同或相近的術語，或修改既有定義的術語在 `origin/main` 上的定義和交付清單寫的原定義不一致，或更新本 PR 的術語在 PR 分支上的定義和上一版不一致，就停下來回報。`/feature` 的需求問答加上兩條用詞規則，`specification-reviewer` 檢查規格用詞和術語表一致。
- **交付清單**：主 session 把產品文件交給 `feature-implementer` 時，附上每個檔案的 repo 路徑與 scratchpad 來源，術語表另外列出術語，分成「新增」、「修改既有定義（開發者已確認）」與「更新本 PR 的術語」，修改要寫術語名稱、原定義與新定義，更新本 PR 的術語（這個 PR 先前交付、`origin/main` 還沒有的術語）要寫術語名稱、上一版定義與新定義；核准後第一次交辦、核准後修改規格／ADR／術語表都用。主 session 核准後不自己把產品文件寫進工作目錄。
- **commit 責任**：

  | 種類 | 檔案 | 誰寫內容 | 誰 commit、push |
  |---|---|---|---|
  | 產品文件 | 規格、ADR、術語表 | 主 session（核准前在 scratchpad） | `feature-implementer`，照交付清單 |
  | 審查紀錄 | 規格審查紀錄、實作審查紀錄 | 主 session | 主 session，commit 後 push 到同一個 PR 分支 |
  | 程式碼與測試 | 其他 | `feature-implementer` | `feature-implementer` |

  文字修正沒有 implementer，主 session 自己 commit。commit 一律只用 `git add <路徑>` 加入明確的檔案；工作目錄有歸屬不明的改動時停下來，由主 session 問開發者。主 session 只 commit 這次的 PR 分支與這次的 `docs/reviews/` 紀錄檔：規格審查紀錄在 PR 建立後、交給 `acceptance-reviewer` 前，實作審查紀錄在每一輪整理完、交回 implementer 修正前。
- **取消與暫停**：核准前取消時，列出 `<功能>-glossary.md` 的術語請開發者決定是否另開文字修正 PR 保留；暫停時保留 scratchpad，接續時把 `<功能>-` 開頭的暫存檔複製到新的 scratchpad，編號接續。

## 放棄的做法

- **規格加一節 Context 表**：把 Context 原樣搬進規格，規格會多一份和需求、驗收條件重複的內容，兩者也可能不一致；讀者要的是決定和它落在哪裡，不是問答的編號。
- **修改紀錄寫「C 編號＋內容」**：內容已經說明了決定，編號在 repo 裡仍然查不到，只是多一個看不懂的符號。
- **Context 表附在規格審查紀錄**：審查紀錄記的是審查的發現與處理；把問答的決定放進去，同一個決定會出現在規格與審查紀錄兩處，而且問答階段的決定不是審查產生的。
- **術語核准前直接寫進工作目錄的 `docs/glossary.md`**（`grill-with-docs` 的做法）：會成為「核准前不改 repo」的例外；工作目錄是開發者與其他 session 共用的，未核准的術語可能被別的 commit 帶走，取消時也要還原。
- **問答一開始就開分支**：問答期間可能取消或暫停，分支與工作目錄會留下沒核准的內容，也會和開發者手上的工作衝突。
- **所有 commit 都由 implementer 做**：最後一輪審查沒有修正時，只為了 commit 審查紀錄還要再叫一次 implementer。
- **主 session commit 核准後的規格／ADR／術語表修改**：產品文件的 commit 分給兩方，術語合併前對照 `origin/main` 的檢查也要寫兩份；由 implementer 照交付清單做，責任分明。
- **拆出獨立的 grilling 或 domain-modeling skill**：只有 `/feature` 使用，拆開後兩邊要各自同步（和 [0008](0008-grilling-without-plan-mode.md) 不保留兩個入口的理由相同）。

## 影響

- [0008](0008-grilling-without-plan-mode.md) 的「規格的修改紀錄所有等級都寫 C 編號」由本 ADR 取代；0008 的其他決定照舊。
- 既有規格與審查紀錄裡的 C、D 編號不回補，記錄的是當時的寫法。
- 核准後的規格、ADR、術語表修改都要經過 implementer，比主 session 直接改多一次交辦。
- 主 session 會 commit 到 PR 分支，所以交回 implementer 前紀錄檔必須已經 commit、push，否則 implementer 會把它當成歸屬不明的改動而停下來。
- 已接受的風險：兩個還沒合併的 PR 用不同名稱寫同一個概念時，合併前對照 `origin/main` 看不到對方、git 也不會衝突，兩個都可能進 main。
