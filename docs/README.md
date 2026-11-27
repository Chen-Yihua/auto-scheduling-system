# 文件

| 文件 | 內容 | 什麼時候要更新 |
|---|---|---|
| [architecture.md](architecture.md) | 系統由哪些部分組成、資料怎麼流動 | 新增服務、資料庫 collection、外部平台，或改變模組分層 |
| [architecture.drawio](architecture.drawio) | 系統架構圖（用 draw.io 開啟） | 同上 |
| [api.md](api.md) | 後端 API 一覽 | 新增、刪除 endpoint，或改了路徑、登入需求、限流 |
| [glossary.md](glossary.md) | 術語表：使用者看得到的概念叫什麼、指的是什麼 | 開發中確定了新術語或改了定義 |
| [issues.md](issues.md) | GitHub issue 的寫法 | issue 的寫法改變時 |
| [decisions/](decisions/) | 架構決策紀錄（ADR）：為什麼這樣做、放棄了什麼 | 做了之後的人會想問「為什麼不用 X」的架構決定 |
| [specs/](specs/) | 規格：核准時的需求與驗收條件 | `/feature`、`/issue` 的每個變更一份（文字修正與快速路徑除外） |
| [reviews/](reviews/) | 規格審查與實作審查的標籤、報告格式 | 審查的格式改變時 |

欄位層級的 request / response 格式以 `backend/schemas/` 和 FastAPI 自動產生的 `/docs` 為準，這裡不重複列。

## 生命週期

| 類型 | 文件 | 規則 |
|---|---|---|
| 目前狀態 | `api.md`、`architecture.md`、`architecture.drawio`、`glossary.md`、`issues.md` | 和程式碼保持一致，在同一個 PR 更新 |
| 核准時的紀錄 | `specs/`、`decisions/` | 合併後不跟著程式更新，目前的行為以程式碼和上一列的文件為準。被新的規格或 ADR 推翻時，只改「狀態」那一行。沒有程式、測試、文件或 open issue 引用時可以刪除，在 PR 描述列出檔案與理由，由開發者決定 |
| 暫存（不進 git） | 草稿資料夾 `.drafts/` | 只放這次開發用的暫存檔，清單見 `.claude/skills/feature/references/resume.md` |

## 術語表

`docs/glossary.md` 只收產品用詞：使用者看得到的概念用哪個名稱、指的是什麼（例如「主任務」「子任務」）。不寫實作細節；行為與驗收條件寫在規格。什麼時候算術語確定，見 `.claude/skills/clarify-requirements/SKILL.md`「術語」。

格式：每個術語一段，粗體名稱、1–2 句定義（寫它是什麼，不寫它做什麼）、`_避免_：` 列出同一個概念不採用的說法。術語自然形成群組時用小標題分組。

```markdown
**<術語>**：
<1–2 句定義：它是什麼>
_避免_：<不採用的說法>、<不採用的說法>
```

### 流程用語

skill（`.claude/skills/`，主 session 照著做的流程）、agent（`.claude/agents/`，主 session 派去做單一工作的另一個 Claude）與 `docs/` 的說明文件用到的詞：

**主 session**：
和開發者對話、指派其他 agent 的那個 Claude。

**等級**（高風險／一般／文字修正）：
依變更碰到什麼分成的三種處理深度，決定規格寫多細、審查做幾次。

**快速路徑**：
一般等級裡需求清楚、沒有要開發者決定的事的改動：短版規格寫在 PR 描述，不做規格審查。

**草稿資料夾**：
repo 根目錄的 `.drafts/`，放核准前的草稿與開發中的暫存檔，不進 git。

**決策樹**：
把要問開發者的問題，依「哪一題要先回答」排出的順序。

**已確認／待問**：
已確認：開發者已經回答的決定。待問：還沒問的問題。

**交付清單**：
交給 `feature-implementer` 放進 repo 的規格、ADR、術語表，以及各自在草稿資料夾的來源。

**發現**：
審查找到的一個問題或建議。

**阻擋／不阻擋**：
阻擋：要先處理完（或開發者決定另開 issue）才能往下走；規格審查是指核准前，實作審查是指交給開發者決定合併前。不阻擋：不用先處理。

**已接受的風險**：
確定不處理、之後的審查也不再提出的風險。

**不變條件**：
只看畫面驗不出來，但一定要守住的系統狀態。

**advisory**：
GitHub 上不公開的漏洞報告（private security advisory）。

## 備註

術語表的格式改寫自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `domain-modeling`（`GLOSSARY-FORMAT`，commit `4ae2317`，MIT 授權）。
