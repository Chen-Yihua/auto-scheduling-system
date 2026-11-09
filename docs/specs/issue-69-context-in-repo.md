# 文件的落點與交付：修改紀錄改寫決定與落點、引進術語表、交付清單與 commit 責任

- 狀態：已核准
- 等級：標準（改 `/feature`、agent 與文件的流程規則：修改紀錄的寫法、術語表、文件的交付與 commit 責任；不改程式碼。不涉及安全、資料一致性，也不是重大架構決策）
- issue：#69
- PR：#71

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/69

PR #67 之後，`/feature` 用 Context（開發者確認過的資訊，編號 C1、C2…）與 Frontier（還要問的問題，編號 Q1、Q2…）追蹤問答，兩者寫在 scratchpad 的 `<功能>-grill.md`，這份檔案不 commit（`.claude/skills/feature/SKILL.md:115`）。但規格的修改紀錄要求所有等級在「原因」寫 C 編號（`.claude/skills/feature/SKILL.md:168`、`docs/specs/README.md:96`）。PR 合併、session 結束後，讀 `docs/specs/` 的開發者看到「C3」，在 repo 裡查不到它是什麼決定；PR #67 的規格（`docs/specs/feature-grilling.md`，D9、D11、D12）與規格審查紀錄（`docs/reviews/specification/feature-grilling.md`，D9）也一樣。

開發者決定參考 mattpocock/skills 的 `grill-with-docs`（commit `4ae2317`，MIT 授權）。它由 `grilling`（問答）與 `domain-modeling`（術語表與 ADR）組成：決定一確定就落在持久的位置；專案自己的用詞一確定就寫進術語表；用詞和術語表不一致或模糊時馬上問清楚。它沒有處理規格、分支、commit、多人同時寫入與取消，它的文件也承認「沒有紀錄把每個回答連到規格與測試」。所以這次只整合問答、用詞規則與術語表；檔案由誰、在什麼時候 commit 進 repo，由我們的工程流程定義。

現況的另一個缺口：文字修正以外的等級，分支由 `feature-implementer` 開，它的規則只寫「規格檔要一起 commit」（`.claude/agents/feature-implementer.md:8`），收到不對應驗收條件的要求會拒絕（`:15`）；規格審查紀錄、ADR 要不要一起 commit 沒有寫，靠推斷。審查紀錄「和修正一起 commit」（`.claude/skills/feature/SKILL.md:203`、`docs/reviews/README.md:11`）沒有寫由誰 commit，最後一輪沒有修正時也沒有人 push。開發者通常同時開著自己的編輯器與 dev server（CLAUDE.md「共用的開發環境」），工作目錄可能有不屬於這次開發的改動。

這個 repo 有自己的產品用詞（例如「主任務」「子任務」「階段任務」），目前散在規格與程式碼裡，沒有術語表。

## 需求

### Commit 責任

1. 依文件種類分清楚由誰 commit：

   | 種類 | 檔案 | 誰寫內容 | 誰 commit、push |
   |---|---|---|---|
   | 產品文件 | 規格（`docs/specs/`）、ADR（`docs/decisions/`）、術語表（`docs/glossary.md`） | 主 session（核准前在 scratchpad） | `feature-implementer`，照交付清單 |
   | 審查紀錄 | 規格審查紀錄（`docs/reviews/specification/`）、實作審查紀錄（`docs/reviews/implementation/`） | 主 session | 主 session，commit 後 push 到同一個 PR 分支 |
   | 程式碼與測試 | 其他 | `feature-implementer` | `feature-implementer` |

   文字修正沒有 implementer，主 session 照既有的「文字修正的流程」自己 commit。

### 交付清單與 implementer

2. **交付清單**：主 session 交給 `feature-implementer` 產品文件時附交付清單：每個檔案的 repo 路徑與 scratchpad 來源（規格、ADR、`<功能>-glossary.md`），術語表另外列出術語名稱。用在兩個時間點：
   - 核准後第一次交辦：交付前在 scratchpad 把規格狀態改成「已核准」。主 session 不再自己把規格寫進工作目錄。
   - 核准後修改規格、ADR、術語表（「規格問題的處理」「核准後修改規格」、核准後的重大架構決策）：同樣整理交付清單交辦。
3. **`feature-implementer` 的規則**（`.claude/agents/feature-implementer.md`）：
   - 從 `main` 開分支後（或沿用既有分支），把交付清單上的檔案放到對應位置；照交付清單修改規格、ADR、術語表，即使不對應某條驗收條件。
   - 合併術語表前先 `git fetch origin main`，對照 `origin/main` 的 `docs/glossary.md`：有相同或相近（同一個概念換了說法，或同一個名稱不同定義）的術語時，停下來回報，不自己決定。`origin/main` 沒有 `docs/glossary.md` 時才照格式建立；分支沒有這個檔案但 `origin/main` 有時，先把分支更新到 `origin/main`。
   - commit 前看 `git status`、`git diff`；只用 `git add <路徑>` 加入交付清單上的檔案與這次實作改的檔案，不用 `git add -A`、`git add .`。
   - 工作目錄有交付清單以外、也不是這次實作造成的改動，或無法確認歸屬時，停下來回報，不 commit。
4. **主 session commit 審查紀錄**：只限目前 feature 的 PR 分支與這次的 `docs/reviews/` 紀錄檔（規格審查、實作審查）。commit 前確認目前分支是這次的 PR 分支，只用 `git add <這次的紀錄檔路徑>`，不帶其他未提交的修改；commit 後 push 到同一個 PR 分支，再 `gh pr checks --watch` 等 CI。分支或檔案歸屬無法確認時停止，問開發者。
   - 時機：規格審查紀錄在 implementer 回報 PR 已建立之後、交給 `acceptance-reviewer` 之前 commit；實作審查紀錄在每一輪審查整理完後 commit，交回 implementer 修正前必須已經 commit、push（否則 implementer 會把它當成歸屬不明的改動）。
   - 改 `/feature` 第 1 節「和規格一起 commit」、第 3 節「每一輪都更新紀錄檔」與 `docs/reviews/README.md:11` 舊的「和修正一起 commit」。
5. **implementer 停下來回報**「術語重複或衝突」「工作目錄有歸屬不明的改動」時，主 session 用「需求問答」的格式問開發者；術語的決定照「新的決定一律回到決策樹」。

### 修改紀錄與 C、Q 編號

6. **修改紀錄寫決定與落點**：規格核准後的修改紀錄，「原因」寫「決定的內容（一句話）＋落點＋檢查過哪些」；落點是規格的節或 AC 編號、ADR 編號，或「術語表」，例如「開發者決定輕量也要問答 → AC3；檢查過 AC1、AC4 不用改」。有規格的等級（輕量、標準、高風險）都照這個寫。
7. **C、Q 編號不進最終文件**：C、Q 編號只在 session 中對照 scratchpad 用。禁止的是指向某次開發的 Context／Frontier 項的引用（例如「依 C3」「Q12 的決定」）；說明編號制度本身，或描述既有紀錄的文字不算。寫進規格、審查紀錄、ADR、術語表、PR 描述、issue、commit 訊息時，一律換成決定的內容與落點。規則定義在 `/feature`「Context 與 Frontier」一處，`docs/reviews/README.md`「紀錄檔格式」、`feature-implementer.md`（commit 訊息、PR 描述）引用。
8. **追溯**：問答與寫規格階段的決定只留在規格（內容與落點），不記進「開發者決策」表，當時的選項不保留。審查與核准後產生的決定照既有規則記在審查紀錄的「開發者決策」表。
9. **編號的檢查責任**：
   - `specification-reviewer`：規格草稿與 ADR 草稿沒有 C、Q 編號；報告引用 Context 時寫內容（可附編號供主 session 對照）。
   - `acceptance-reviewer`：規格、這次新增或修改的 ADR 與 `docs/glossary.md`、規格審查紀錄、實作審查紀錄、commit 訊息（`git log`）、PR 描述沒有 C、Q 編號。PR 描述由主 session 交給它時附上全文。
   - 主 session：開 issue 前確認內容；第 4 節回報前確認最後一輪的審查紀錄、最後一次審查之後的 commit 訊息與最終的 PR 描述（這些在最後一次審查之後才產生）。
   - 不加自動化檢查。

### 術語表

10. **位置與格式**：`docs/glossary.md`，只收產品領域、使用者看得到的概念，不收開發流程的用詞（Context、Frontier、等級、交付清單等，它們定義在 skill 與 `docs/`）。
    - 格式定義在 `/feature`，照 `domain-modeling` 的 `GLOSSARY-FORMAT`，繁體中文，附出處與授權：檔頭是標題與一兩句說明；每個術語一段，粗體名稱、1–2 句定義（寫它是什麼，不寫它做什麼）、`_避免_：` 列出同一個概念不採用的說法；不寫實作細節、不當規格用；自然形成群組時用小標題分組。
    - 第一個術語合併時才建立檔案；這個 PR 不建立、不預先填寫。
    - 列進 `docs/README.md` 的文件表（不加連結，註明第一個術語合併時建立），生命週期歸在「持續更新」。
11. **術語一確定就記錄**（標準、高風險）：
    - 核准前任何階段（問答、寫規格、規格審查）確定一個術語，就編成 Context 項（「寫進哪裡」寫「術語表」），並馬上照格式寫進 scratchpad 的 `<功能>-glossary.md`。核准前仍然只寫 scratchpad，不改 repo。
    - 核准後（實作回報、實作審查）才確定或修改的術語，照「規格問題的處理」寫進規格的修改紀錄（落點「術語表」），照需求 2 交給 `feature-implementer`。
    - 判斷 Context 有沒有落點的地方（「Context 寫進規格」、規格審查、「清理暫存」、`docs/README.md` 暫存列、`specification-reviewer`），「術語表」都算落點，不要求術語再寫進規格。
12. **用詞檢查**寫進 `/feature`「需求問答」：開發者或 issue 用的詞和 `docs/glossary.md`、`<功能>-glossary.md` 的定義不一致時，馬上指出並問清楚；用詞模糊或同一個詞可能指不同概念時，提出明確的說法請開發者選。`specification-reviewer` 的一致性檢查加：標準、高風險的規格用詞和這兩份術語表是否一致（檔案存在時）。

### 暫存檔、取消、暫停

13. **暫存清單**：`/feature` 第 1 節「核准前只寫 scratchpad」與 `docs/README.md` 暫存列，加上 `<功能>-glossary.md` 與規格審查紀錄草稿 `<功能>-spec-review.md`；交給 `specification-reviewer` 的內容加上 `<功能>-glossary.md` 的路徑（有的話）。
14. **取消**：核准前開發者表示不做時，主 session 列出 `<功能>-glossary.md` 的術語，請開發者決定保留或不保留。保留：另外用文字修正的流程開 PR，只改 `docs/glossary.md`，開 PR 前同樣 `git fetch origin main` 對照相同或相近的術語。PR 關閉時不另外處理（改動只在分支上）。
15. **暫停與接續**：暫停時 scratchpad 保留，告訴開發者 scratchpad 的路徑。接續時，開發者提供舊路徑，主 session 把舊 scratchpad 裡這次開發的全部暫存檔（`<功能>-` 開頭：Context／Frontier、術語、規格草稿、規格審查紀錄草稿、ADR 草稿、各輪審查報告原文）複製到新的 scratchpad，C、Q 編號接續；舊路徑不存在時告訴開發者，從問答重新開始。
16. 需求 14、15 寫進 `/feature` 第 4 節與 `docs/README.md`「生命週期」。

### ADR

17. 新增 ADR 0009，寫出決定（含需求 1 的 commit 責任）與放棄的做法；ADR 清單加一列。ADR 0008 的狀態行與清單 0008 列註明「修改紀錄寫 C 編號」的部分被 0009 取代，ADR 0008 內文不變。

### 核准後補充（實作審查第 1 輪）

18. **規格的 PR 編號**：`feature-implementer` 用 `gh pr create` 建立 PR 後，把規格開頭的「PR」補上編號，commit、push，並在回報寫出 PR 編號。主 session 收到回報後，以 PR 分支上已 commit 的規格為準，同步更新 scratchpad 的 `<功能>-spec.md`，之後的交付清單不會把 PR 編號蓋回去。
19. **修改既有術語**：交付清單的術語分成兩種：
    - **新增**：照需求 3 對照 `origin/main`，有相同或相近的術語時停下來回報。
    - **修改既有定義（開發者已確認）**：交付清單標明是修改，並寫出術語名稱、原定義與新定義。`feature-implementer` 確認 `origin/main` 上的既有定義和交付清單寫的原定義一致後才修改；不一致時停下來回報，不直接覆蓋。
    - `feature-implementer` 因術語停下來、開發者決定要修改既有定義後，主 session 在交付清單把該術語改標成「修改既有定義」再交辦。
20. **舊 scratchpad 不存在時的接續**（取代需求 15「從問答重新開始」那一句）：
    - 核准前：標準、高風險從需求問答重新開始；輕量從寫規格草稿重新開始。
    - 核准後：先 `git fetch`，確認 PR 分支的最新狀態，把 PR 分支上最新的規格、術語表、相關 ADR、審查紀錄直接複製到新的 scratchpad（規格存成 `<功能>-spec.md`），建立新的工作上下文；不依記憶重新產生或改寫。C、Q 從 1 重新編號。正式文件仍以 PR 分支為準。

## 不做

- 不回補既有規格與審查紀錄裡的 C／D 編號（例如 `docs/specs/feature-grilling.md` 的 D9、D11、D12）。
- 文字修正沒有規格與修改紀錄，需求 6 不適用；輕量、文字修正不做問答，不因問答寫術語表（取消時保留術語用文字修正開 PR 是需求 14 的例外）。
- 這個 PR 不建立 `docs/glossary.md`、不預先填寫既有術語；術語表不收開發流程的用詞。
- 問答階段的決定不記進「開發者決策」表。
- ADR 的門檻不加 `grill-with-docs` 的三個條件；不用 `GLOSSARY-MAP.md` 多 context 結構（這個 repo 是單一 context）。
- 不加 C、Q 編號的自動化檢查。
- 不拆出獨立的 grilling 或 domain-modeling skill：只有 `/feature` 使用。
- 不改 PR → CI → Review 的順序。
- 不改程式碼。

## 假設

1. 術語表格式寫在 `/feature`：檔案第一個術語合併時才建立，格式需要先有地方定義。
2. 規格審查的術語檢查只對標準、高風險（需求 12），因為術語表只在做問答的等級使用；這是開發者的決定，列在這裡只為了說明需求 12 的範圍。
3. 術語算「確定」：開發者回答了名稱與定義（含接受建議答案），和其他 Context 項相同。
4. 「相近術語」由 implementer 判斷到「可能是」就停下來回報，寧可多問：重複或衝突的定義進了術語表，比多問一次的成本高。
5. 規格審查紀錄的 commit 時機（需求 4）：分支與 PR 由 implementer 建立，主 session 只 commit 到已存在的 PR 分支，而 `acceptance-reviewer` 要讀已 commit 的紀錄。

## 驗收條件

| # | 條件 | 類型 |
|---|---|---|
| AC1 | `/feature`、`feature-implementer.md` 與 ADR 0009 對 commit 責任的描述一致：規格、ADR、術語表與程式碼由 `feature-implementer` commit；規格審查與實作審查紀錄由主 session commit 並 push 到同一個 PR 分支；文字修正由主 session 自己 commit。沒有任何一處寫「所有 commit 都由 implementer 做」或讓 implementer commit 審查紀錄 | 不變條件 |
| AC2 | 核准後第一次交辦與核准後修改規格、ADR、術語表時，流程要求主 session 附交付清單（repo 路徑、scratchpad 來源、術語名稱）；第一次交辦前在 scratchpad 把規格狀態改成已核准；主 session 核准後不自己把產品文件寫進工作目錄 | 使用者行為（用 agent 的開發者） |
| AC3 | `feature-implementer` 的規則：照交付清單放檔案、修改規格／ADR／術語表（不因不對應驗收條件而拒絕）；合併術語表前 `git fetch origin main` 並對照 `origin/main`，有相同或相近的術語就停下來回報；只用 `git add <路徑>` 加入清單上的檔案與這次實作改的檔案；工作目錄有歸屬不明的改動時停下來回報、不 commit | 不變條件 |
| AC4 | 主 session commit 審查紀錄時，流程要求確認目前分支是這次的 PR 分支、只 `git add` 這次的 `docs/reviews/` 紀錄檔、commit 後 push；規格審查紀錄在 PR 建立後、交給 `acceptance-reviewer` 前 commit，實作審查紀錄在交回 implementer 前已 commit、push；歸屬無法確認就停止並問開發者；`docs/reviews/README.md`、`/feature` 第 1 節與第 3 節不再寫「和規格一起 commit」「和修正一起 commit」 | 不變條件 |
| AC5 | `feature-implementer` 因術語或歸屬停下來回報時，主 session 用「需求問答」的格式問開發者 | 使用者行為 |
| AC6 | 照 `/feature`、`docs/specs/README.md` 寫規格修改紀錄時，「原因」要求寫決定的內容、落點（規格的節或 AC、ADR、術語表）與檢查過哪些，不使用 C 編號；有規格的等級都適用 | 不變條件 |
| AC7 | `/feature` 規定 C、Q 編號只在 scratchpad 使用，並定義禁止的是指向 Context／Frontier 項的引用（說明編號制度或描述既有紀錄不算），寫進規格、審查紀錄、ADR、術語表、PR 描述、issue、commit 訊息時換成決定的內容與落點；`docs/reviews/README.md`、`feature-implementer.md` 引用這條；問答與寫規格階段的決定不記進「開發者決策」表；`.claude/`、`docs/` 的現行規則沒有要求把 C、Q 編號寫進這些地方 | 不變條件 |
| AC8 | 編號的檢查責任照需求 9 寫進 `specification-reviewer.md`、`acceptance-reviewer.md` 與 `/feature`（交給 `acceptance-reviewer` 時附 PR 描述全文、開 issue 前確認、第 4 節回報前確認最後一輪紀錄、最後一次審查之後的 commit 訊息與 PR 描述） | 不變條件 |
| AC9 | `/feature` 定義術語表的位置、收錄範圍（只收產品領域、使用者看得到的概念）與格式（含檔頭），附 `domain-modeling` 的出處（commit `4ae2317`）與 MIT 授權；這個 PR 沒有建立 `docs/glossary.md` | 不變條件 |
| AC10 | 標準、高風險在核准前任何階段確定術語時，流程要求編成「寫進哪裡＝術語表」的 Context 項，馬上寫進 scratchpad 的 `<功能>-glossary.md`，不改 repo；核准後才確定或修改的術語，寫進修改紀錄並照交付清單交給 `feature-implementer` | 使用者行為 |
| AC11 | 判斷 Context 有沒有落點的每一處都把術語表算成落點；暫存清單與交給 `specification-reviewer` 的內容包含 `<功能>-glossary.md`，暫存清單包含 `<功能>-spec-review.md` | 不變條件 |
| AC12 | `/feature`「需求問答」有兩條用詞規則；`specification-reviewer` 檢查標準、高風險的規格用詞和 `docs/glossary.md`、`<功能>-glossary.md` 一致 | 不變條件 |
| AC13 | 核准前取消時，流程要求列出 `<功能>-glossary.md` 的術語請開發者決定；保留時用文字修正 PR，開 PR 前對照 `origin/main`；`docs/README.md`「生命週期」有同樣的規則 | 使用者行為 |
| AC14 | 暫停時告知 scratchpad 路徑；接續時把舊 scratchpad 裡這次開發的全部暫存檔（含 ADR 草稿與各輪審查報告原文）複製到新的 scratchpad，C、Q 編號接續；舊路徑不存在時告訴開發者並從問答重新開始；`docs/README.md`「生命週期」有同樣的規則 | 使用者行為 |
| AC15 | 輕量、文字修正的流程不要求寫術語表；文字修正不適用 AC6 | 不變條件 |
| AC16 | `docs/README.md` 文件表有 `glossary.md` 一列（不加連結，註明建立時機），持續更新列包含它；ADR 0009 寫出背景、決定（含 commit 責任）、放棄的做法（規格加 Context 表、修改紀錄寫「C 編號＋內容」、Context 表附在規格審查紀錄、術語核准前直接寫進工作目錄、問答一開始就開分支、所有 commit 都由 implementer 做、主 session commit 核准後的規格／ADR／術語表修改、拆出獨立 skill）；ADR 清單有 0009，0008 列與 ADR 0008 狀態行只註明「修改紀錄寫 C 編號」被取代，ADR 0008 內文不變 | 不變條件 |
| AC17 | 所有 skill、agent、文件引用的路徑與節名稱都存在（`docs/glossary.md` 除外：第一個術語合併時才建立）；歷史文件（既有規格、審查紀錄、既有 ADR 內文、實驗紀錄）沒有被修改 | 不變條件 |
| AC18 | `feature-implementer` 建立 PR 後補上規格的 PR 編號、commit、push 並回報編號；主 session 收到後以 PR 分支上的規格同步 scratchpad 的 `<功能>-spec.md` | 不變條件 |
| AC19 | 交付清單的術語分成「新增」與「修改既有定義（開發者已確認）」；修改要寫術語名稱、原定義、新定義；`feature-implementer` 只在 `origin/main` 的既有定義和原定義一致時修改，不一致，或新增的術語和 `origin/main` 相同或相近時停下來回報；開發者決定修改後，主 session 改標再交辦 | 不變條件 |
| AC20 | 舊 scratchpad 不存在時：核准前標準、高風險從需求問答、輕量從規格草稿重新開始；核准後先確認 PR 分支最新狀態，直接複製 PR 分支上的規格、術語表、相關 ADR、審查紀錄到新的 scratchpad，不依記憶重新產生，C、Q 從 1 重新編號；`docs/README.md`「生命週期」同樣寫明 | 使用者行為 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中、未登入／無權限 | 只改流程文件，沒有畫面與 API |
| 空資料 | 術語表不存在時：合併第一個術語時建立（AC3）；規格審查只在檔案存在時對照（AC12） |
| 失敗 | implementer 停下來回報（AC3、AC5）、主 session 歸屬不明時停止（AC4）、取消與暫停（AC13、AC14） |
| 併發 | 核准前只寫各自的 scratchpad，不碰共用的工作目錄；commit 只加入明確的路徑（AC3、AC4）。殘留風險（已接受）：兩個還沒合併的 PR 用不同名稱寫同一個概念時，合併前的對照看不到對方、git 也不會衝突，兩個都可能進 main |
| 資料處理 | 不碰資料 |
| 安全性 | 術語表是公開文件，只收產品用詞的定義、不寫實作細節，不含憑證或個資；不改「漏洞的處理」 |

## 實作計畫

分支 `issue-69-context-in-repo`：

- `.claude/skills/feature/SKILL.md`
  - 第 1 節開頭：暫存清單（需求 13）。
  - 「Context 與 Frontier」：C、Q 編號只在 scratchpad（需求 7）；「寫進哪裡」加「術語表」；術語在各階段的記錄方式（需求 11）。
  - 「需求問答」：兩條用詞規則（需求 12）；術語表的位置、範圍、格式、出處與授權（需求 10）。
  - 「Context 寫進規格」「規格審查」：術語表算落點（需求 11）；交給 reviewer 的內容（需求 13）；核准後改成交付清單、規格審查紀錄由主 session commit（需求 2、4）。
  - 第 2 節：交付清單與 commit 責任（需求 1、2）；implementer 停下來回報的處理（需求 5）。
  - 第 3 節：交給 `acceptance-reviewer` 附 PR 描述全文（需求 9）；「規格問題的處理」「核准後修改規格」走交付清單（需求 2）、修改紀錄的寫法（需求 6）；「每一輪都更新紀錄檔」改成主 session commit 並 push（需求 4）；「不阻擋的發現開 issue」開前確認編號（需求 9）。
  - 第 4 節：回報前確認紀錄與 PR 描述（需求 9）；「清理暫存」術語表算落點、取消、暫停與接續（需求 14–16）。
- `.claude/agents/feature-implementer.md`：需求 3、7（commit 訊息、PR 描述）。
- `.claude/agents/specification-reviewer.md`：需求 9、11、12、13。
- `.claude/agents/acceptance-reviewer.md`：需求 9。
- `docs/reviews/README.md`：`:11` 的 commit 寫法（需求 4）、「紀錄檔格式」（需求 7、8）。
- `docs/specs/README.md`「核准後」：需求 6。
- `docs/README.md`：文件表、生命週期（需求 10、13、14、15）。
- `docs/decisions/0009-<名稱>.md`（新增）、`docs/decisions/README.md` 清單、ADR 0008 狀態行（需求 17）。
- `docs/specs/issue-69-context-in-repo.md`（implementer commit）、`docs/reviews/specification/issue-69-context-in-repo.md`、`docs/reviews/implementation/issue-69-context-in-repo.md`（主 session commit）。

這個 PR 交辦時，新的 agent 規則還沒合併、不會生效，所以交辦訊息明寫檔案要放的位置與要 `git add` 的路徑。

## 測試對應

| AC | 驗證方式 |
|---|---|
| AC1 | 讀 `/feature`、`feature-implementer.md`、ADR 0009 中 commit 責任的每一處，確認一致 |
| AC2、AC5、AC10、AC13、AC14、AC15 | 讀 `/feature`，各走一次流程：標準功能在問答中確定術語、在規格審查中確定術語、核准後交辦、在實作審查中修改術語、implementer 回報術語衝突、核准前取消、暫停後在新 session 接續（舊路徑存在／不存在）、輕量 bug、文字修正 |
| AC3 | 讀 `feature-implementer.md`，走一次：工作目錄有開發者自己的改動、`origin/main` 已有相近術語、收到不對應驗收條件的術語修改 |
| AC4 | 讀 `/feature` 第 1、3 節與 `docs/reviews/README.md`，走一次：最後一輪沒有修正、目前不在 PR 分支、工作目錄有其他改動 |
| AC6、AC7 | 讀 `/feature`「核准後修改規格」「Context 與 Frontier」、`docs/specs/README.md`「核准後」、`docs/reviews/README.md`「紀錄檔格式」；`git grep -nE "\b[CQ][0-9]+\b"` 與 `git grep -n "C 編號"` 的每個結果，依需求 7 的定義判斷是引用還是說明編號制度 |
| AC8、AC12 | 讀兩個 reviewer 的檢查項目與 `/feature` 第 3、4 節 |
| AC9 | 讀 `/feature` 的術語表規則；`test ! -e docs/glossary.md` |
| AC11 | 讀判斷落點的每一處與暫存清單 |
| AC16 | 讀 `docs/README.md`、ADR 0009、`docs/decisions/README.md`；`git diff` ADR 0008 只有狀態行 |
| AC17 | `grep` 節名稱與路徑；`git diff --stat` 沒有歷史文件 |
| AC18–AC20 | 讀 `/feature`、`feature-implementer.md`、`docs/README.md`，走一次：PR 建立後補編號再交付一次規格修改、修改一個既有術語（原定義一致／不一致）、核准前與核准後舊 scratchpad 不存在 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-09 | 新增需求 18–20、AC18–AC20；需求 15 的「舊路徑不存在時從問答重新開始」改由需求 20 取代 | 開發者決定：PR 編號由 implementer 建立 PR 後補上，主 session 以 PR 分支同步 scratchpad → 需求 18、AC18；修改既有術語要在交付清單寫原定義與新定義，implementer 確認一致才改 → 需求 19、AC19；舊 scratchpad 不存在時依核准前後分別處理，核准後直接複製 PR 分支上的文件 → 需求 20、AC20。來源：實作審查第 1 輪 #1–#3。檢查過 AC2、AC3、AC10、AC14：AC14 的「從問答重新開始」由 AC20 取代，其他不用改 | 開發者（2026-11-09） |
