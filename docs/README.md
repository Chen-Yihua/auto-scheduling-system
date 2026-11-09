# 文件

| 文件 | 內容 | 什麼時候要更新 |
|---|---|---|
| [architecture.md](architecture.md) | 系統由哪些部分組成、資料怎麼流動 | 新增服務、資料庫 collection、外部平台，或改變模組分層 |
| [architecture.drawio](architecture.drawio) | 系統架構圖（用 draw.io 開啟） | 同上 |
| [api.md](api.md) | 後端 API 一覽 | 新增、刪除 endpoint，或改了路徑、登入需求、限流 |
| [decisions/](decisions/) | 架構決策紀錄（ADR）：為什麼這樣做、放棄了什麼 | 做了之後的人會想問「為什麼不用 X」的決定 |
| [specs/](specs/) | 規格：核准當時的需求、假設、驗收條件與修改紀錄 | `/feature`、`/issue` 的每個變更一份（文字修正除外）；核准後驗收條件的修改記在「修改紀錄」 |
| `glossary.md`（第一個術語合併時才建立） | 術語表：產品領域、使用者看得到的概念用哪個名稱、指的是什麼（格式見 `/feature` 第 1 節「術語表」） | 標準、高風險的開發確定了新術語或修改了定義時，由 `feature-implementer` 照交付清單合併 |
| [issues.md](issues.md) | GitHub issue 的寫法：情境與技術背景兩層 | issue 的欄位或寫法改變時 |
| [reviews/](reviews/) | 規格審查與實作審查：每輪的重要發現、分類、開發者決策與處理結果 | 每個變更的每種審查一份，每輪審查完更新 |
| [experiments/](experiments/) | 開發流程的實驗：目的、指標與紀錄 | 開始新的流程實驗，或實驗結束整理結果時 |

欄位層級的 request / response 格式以後端的 `backend/schemas/` 和 FastAPI 自動產生的 `/docs` 為準，這裡不重複列。

## 生命週期

| 類型 | 文件 | 規則 |
|---|---|---|
| 永久保存（歷史紀錄） | `specs/`、`reviews/specification/`、`reviews/implementation/`、`reviews/*-round<N>.md`、`decisions/` | 不刪除，也不因為過時就改寫內容。被取代時只改狀態並連結新的文件：規格照 [specs/README.md](specs/README.md)「規格和目前系統的關係」，ADR 照 [decisions/README.md](decisions/README.md)。記錄的是當時的決定，不是目前的系統 |
| 持續更新（目前狀態） | `api.md`、`architecture.md`、`architecture.drawio`、`issues.md`、`glossary.md` | 和程式碼、流程保持一致，改動時在同一個 PR 更新（時機見上表）。不記歷史，歷史看 git、規格與 ADR |
| 暫存（不 commit） | scratchpad（規格草稿 `<功能>-spec.md`、問答的 Context 與 Frontier `<功能>-grill.md`、術語 `<功能>-glossary.md`、重大架構決策的 ADR 草稿 `<功能>-adr-<名稱>.md`、規格審查紀錄草稿 `<功能>-spec-review.md`、每輪審查報告原文） | 只放當下的開發需要的內容。核准後由 `feature-implementer` 照交付清單把規格存進 `specs/`、ADR 草稿存進 `decisions/`、術語合併進 `glossary.md`；規格審查紀錄草稿由主 session 存進 `reviews/specification/`（`/feature` 第 2 節）。流程回報前確認已確認的內容都已在規格、審查紀錄、ADR 或術語表（文字修正對照 PR 的改動與描述），還沒做完的後續動作列在回報的「待辦」（`/feature` 第 4 節「清理暫存」）。已確認、會影響實作的決定，核准前一定要寫進規格、ADR 草稿或 `<功能>-glossary.md`（落點是術語表的），不能只留在暫存或對話裡 |
| 選擇性保存（實驗） | `experiments/` | README 寫實驗目的、指標與結論，TEMPLATE 是紀錄格式，`records/` 保留有參考價值的紀錄。流程的版本用紀錄裡的「流程版本」（commit）對應，不另外備份每一版的 skill。既有紀錄不自動刪除，也不為了符合新規則修改；要刪除時先寫出它沒有參考價值的理由，由開發者決定 |

暫存的取消與暫停（`/feature` 第 4 節「取消」「暫停與接續」）：

- **取消**：核准前開發者表示不做時，主 session 列出 `<功能>-glossary.md` 的術語，請開發者決定保留或不保留。保留的用文字修正的流程另外開 PR，只改 `glossary.md`，開 PR 前 `git fetch origin main` 對照有沒有相同或相近的術語。PR 關閉時不另外處理：改動只在分支上。
- **暫停與接續**：暫停時 scratchpad 保留，主 session 告訴開發者 scratchpad 的路徑。接續時開發者提供舊路徑，主 session 把舊 scratchpad 裡這次開發的全部暫存檔（`<功能>-` 開頭：Context／Frontier、術語、規格草稿、規格審查紀錄草稿、ADR 草稿、各輪審查報告原文）複製到新的 scratchpad，C、Q 編號接續。舊路徑不存在時告訴開發者：核准前，標準、高風險從需求問答重新開始，輕量從寫規格草稿重新開始；核准後，先 `git fetch` 確認 PR 分支的最新狀態，把 PR 分支上最新的規格、術語表、相關 ADR、審查紀錄直接複製到新的 scratchpad（規格存成 `<功能>-spec.md`），不依記憶重新產生或改寫，C、Q 從 1 重新編號，正式文件仍以 PR 分支為準；核准後、PR 還沒建立時，先看本機與 `origin` 有沒有這次的分支，以及分支上或工作目錄中有沒有 `docs/specs/<功能>.md`，找得到就照核准後的方式複製，找不到就告訴開發者核准後的規格已遺失，用需求問答的格式請開發者選擇重寫草稿再核准一次，或取消。文字修正：核准前從寫改動清單重新開始；核准後以分支上已改的內容為準，重新整理改動清單請開發者確認。
