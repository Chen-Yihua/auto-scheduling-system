# 文件

| 文件 | 內容 | 什麼時候要更新 |
|---|---|---|
| [architecture.md](architecture.md) | 系統由哪些部分組成、資料怎麼流動 | 新增服務、資料庫 collection、外部平台，或改變模組分層 |
| [architecture.drawio](architecture.drawio) | 系統架構圖（用 draw.io 開啟） | 同上 |
| [api.md](api.md) | 後端 API 一覽 | 新增、刪除 endpoint，或改了路徑、登入需求、限流 |
| [decisions/](decisions/) | 架構決策紀錄（ADR）：為什麼這樣做、放棄了什麼 | 做了之後的人會想問「為什麼不用 X」的決定 |
| [specs/](specs/) | 規格：核准當時的需求、假設、驗收條件與修改紀錄 | `/feature`、`/issue` 的每個變更一份（文字修正除外）；核准後驗收條件的修改記在「修改紀錄」 |
| `glossary.md`（第一個術語合併時才建立） | 術語表：產品領域、使用者看得到的概念用哪個名稱、指的是什麼（格式見本文件「術語表」） | 文字修正以外的開發確定了新術語或修改了定義時，由 `feature-implementer` 照交付清單合併 |
| [issues.md](issues.md) | GitHub issue 的寫法：情境與技術背景兩層 | issue 的欄位或寫法改變時 |
| [reviews/](reviews/) | 規格審查與實作審查：每輪的重要發現、分類、開發者決策與處理結果 | 每個變更的每種審查一份，每輪審查完更新 |
| [experiments/](experiments/) | 開發流程的實驗：目的、指標與紀錄 | 開始新的流程實驗，或實驗結束整理結果時 |

欄位層級的 request / response 格式以後端的 `backend/schemas/` 和 FastAPI 自動產生的 `/docs` 為準，這裡不重複列。

## 生命週期

| 類型 | 文件 | 規則 |
|---|---|---|
| 永久保存（歷史紀錄） | `specs/`、`reviews/specification/`、`reviews/implementation/`、`reviews/*-round<N>.md`、`decisions/` | 不刪除，也不因為過時就改寫內容。被取代時只改狀態並連結新的文件：規格照 [specs/README.md](specs/README.md)「規格和目前系統的關係」，ADR 照 [decisions/README.md](decisions/README.md)。記錄的是當時的決定，不是目前的系統 |
| 持續更新（目前狀態） | `api.md`、`architecture.md`、`architecture.drawio`、`issues.md`、`glossary.md` | 和程式碼、流程保持一致，改動時在同一個 PR 更新（時機見上表）。不記歷史，歷史看 git、規格與 ADR |
| 暫存（不 commit） | scratchpad（`<功能>-` 開頭的暫存檔，種類與檔名見 `.claude/skills/feature/references/resume.md`的暫存產物表） | 只放當下的開發需要的內容。核准後由 `feature-implementer` 照交付清單把規格存進 `specs/`、ADR 草稿存進 `decisions/`、術語合併進 `glossary.md`；規格審查紀錄草稿由主 session 存進 `reviews/specification/`（`implement-and-review`「審查紀錄的 commit」）。流程回報前確認已確認的內容都已在規格、審查紀錄、ADR 或術語表（文字修正對照 PR 的改動與描述），還沒做完的後續動作列在回報的「待辦」（`/feature`「清理暫存」）。已確認、會影響實作的決定，核准前一定要寫進規格、ADR 草稿或 `<功能>-glossary.md`（落點是術語表的），不能只留在暫存或對話裡 |
| 選擇性保存（實驗） | `experiments/` | README 寫實驗目的、指標與結論，TEMPLATE 是紀錄格式，`records/` 保留有參考價值的紀錄。流程的版本用紀錄裡的「流程版本」（commit）對應，不另外備份每一版的 skill。既有紀錄不自動刪除，也不為了符合新規則修改；要刪除時先寫出它沒有參考價值的理由，由開發者決定 |

暫存的取消與暫停（`/feature`「取消」、`feature/references/resume.md`）：

- **取消**：核准前取消時這次確定的術語怎麼處理，見 `/feature`「取消」。
- **暫停與接續**：暫停、接續，以及 scratchpad 遺失時以暫存產物為單位的恢復，見 `feature/references/resume.md`。

## 術語表

`docs/glossary.md` 記錄這個專案的產品用詞：使用者看得到的概念用哪個名稱、指的是什麼。

- 位置：`docs/glossary.md`。第一個術語合併時由 `feature-implementer` 建立，不預先填寫。
- 只收產品領域、使用者看得到的概念（例如「主任務」「子任務」「階段任務」）；不收開發流程的用詞（已確認、待問、等級、交付清單等，它們定義在 skill 與 `docs/`）。
- 不寫實作細節，不當規格用：行為與驗收條件寫在規格。
- 什麼時候算術語確定、核准前後怎麼寫與交付，見 `.claude/skills/clarify-requirements/SKILL.md`「術語」。

格式（繁體中文）：檔頭是標題與一兩句說明；每個術語一段：粗體名稱、1–2 句定義（寫它是什麼，不寫它做什麼）、`_避免_：` 列出同一個概念不採用的說法；術語自然形成群組時用小標題分組。

```markdown
# 術語表

這個專案的產品用詞：使用者看得到的概念用哪個名稱、指的是什麼。

## <群組名稱（自然形成群組時才加）>

**<術語>**：
<1–2 句定義：它是什麼>
_避免_：<不採用的說法>、<不採用的說法>
```

格式改寫自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `domain-modeling`（`GLOSSARY-FORMAT`，commit `4ae2317`，MIT 授權）。
