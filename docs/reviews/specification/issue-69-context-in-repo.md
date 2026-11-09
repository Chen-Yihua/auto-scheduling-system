# 文件的落點與交付：規格審查紀錄

- 規格：[docs/specs/issue-69-context-in-repo.md](../../specs/issue-69-context-in-repo.md)
- PR：#71
- 等級：標準
- 輪數：3（第 1 輪 2026-11-09 草稿；第 2 輪 2026-11-09 草稿；第 3 輪 2026-11-09 草稿，開發者要求）
- 最終結果：第 3 輪的阻擋項目都依查證依據或既有決定直接修正，開發者核准

## 摘要

- 發現：31 項（第 1 輪 9 項、第 2 輪 13 項、第 3 輪 9 項）：Specification Defect 15、Missing AC 6、Factual Error 2、Improvement Suggestion 8；Major 3、Minor 21、Info 7
- 開發者決策：12 項（第 1 輪 #1、#3、#5、#6、#7；第 2 輪 #12–#16、#19、#20）
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-09 草稿 | #1–#9（#1–#7） | 開發者重新設計：術語核准前改寫在 scratchpad、核准後由 implementer 照交付清單合併；commit 只加入明確路徑；主 session 可 commit 審查紀錄；編號不進最終文件並寫進 reviewer 檢查；術語表算 Context 的落點 |
| 2 | 2026-11-09 草稿 | #10–#22（#10–#20） | 核准後的修改也走交付清單；commit 責任分成產品文件、審查紀錄、程式碼三類；審查紀錄 commit 後 push；最終文件的編號檢查責任；暫停後接續；術語表只收產品領域用詞 |
| 3 | 2026-11-09 草稿 | #23–#31（#23–#27） | 審查紀錄的 commit 時機；「出現編號」的定義；接續時複製全部暫存檔；最後的 commit 訊息由主 session 檢查 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 標準、高風險由 implementer 開分支與 commit，術語表可能沒被 commit | Specification Defect | Major | 是 | 否 | 文件的 commit 責任 | 交付清單交給 implementer，implementer 只 commit 清單上的檔案（需求 2、3） | 開發者 | 規格已修改 |
| 2 | 1 | 「Context 每一項都要寫進規格或 ADR」和落點＝術語表衝突 | Specification Defect | Major | 是 | 否 | — | 判斷落點的每一處都把術語表算進去（需求 11、AC11） | 主 session（文件同步） | 規格已修改 |
| 3 | 1 | 編號仍會經審查報告進 `docs/reviews/` | Missing AC | Minor | 是 | 否 | 編號不進最終文件 | 編號寫進最終文件前換成內容與落點，reviewer 檢查（需求 7、9） | 開發者 | 規格已修改 |
| 4 | 1 | 「路徑都存在」和「不建立 `docs/glossary.md`」矛盾 | Specification Defect | Minor | 是 | 否 | — | AC17 排除 `docs/glossary.md` | 主 session | 規格已修改 |
| 5 | 1 | 開發取消沒定義；保留術語走文字修正和「文字修正不寫術語表」衝突 | Specification Defect | Minor | 是 | 否 | 取消與暫停 | 定義取消；保留術語是「不做」的例外（需求 14） | 開發者 | 規格已修改 |
| 6 | 1 | 只定義問答中確定的術語 | Missing AC | Minor | 是 | 否 | — | 核准前任何階段都寫進 scratchpad；核准後走交付清單（需求 11） | 開發者 | 規格已修改 |
| 7 | 1 | 共用工作目錄裡別人的術語被一起 commit | Specification Defect | Minor | 是 | 否 | 文件的 commit 責任 | 核准前不改 repo；commit 只用 `git add <路徑>`，歸屬不明就停（需求 3、4） | 開發者 | 規格已修改 |
| 8 | 1 | 修改紀錄的「原因」是否保留「檢查過哪些」 | Improvement Suggestion | Info | 否 | 否 | — | 保留（需求 6） | 主 session | 規格已修改 |
| 9 | 1 | ADR 清單 0008 列狀態、術語表檔頭 | Improvement Suggestion | Info | 否 | 否 | — | 補上（需求 10、17） | 主 session | 規格已修改 |
| 10 | 2 | 背景把 D 編號的出處寫成實作審查紀錄 | Factual Error | Minor | 是 | 否 | — | 改成規格審查紀錄 | 主 session（依查證依據） | 規格已修改 |
| 11 | 2 | ADR 0008 沒有「核准後由誰 commit」的決定 | Factual Error | Minor | 是 | 否 | — | 0008 只標「修改紀錄寫 C 編號」被取代；commit 責任寫進 0009 | 主 session（依查證依據） | 規格已修改 |
| 12 | 2 | 核准後修改規格、ADR、術語表沒有人能寫檔與 commit | Specification Defect | Major | 是 | 否 | 文件的 commit 責任 | 核准後的修改也照交付清單交給 implementer；commit 責任分三類（需求 1–3） | 開發者 | 規格已修改 |
| 13 | 2 | 審查紀錄的 commit 範圍不一致、舊寫法沒改、push 沒定義 | Specification Defect | Minor | 是 | 否 | 文件的 commit 責任 | 範圍含兩種審查紀錄、commit 後 push、改掉舊寫法（需求 4） | 開發者 | 規格已修改 |
| 14 | 2 | `acceptance-reviewer` 讀不到 PR 描述，最終版沒人檢查 | Specification Defect | Minor | 是 | 否 | 編號不進最終文件 | 交辦時附 PR 描述全文；回報前主 session 檢查（需求 9） | 開發者 | 規格已修改 |
| 15 | 2 | 「開發者決策」表放不下問答階段的決定 | Specification Defect | Minor | 是 | 否 | — | 問答階段的決定只留在規格（需求 8） | 開發者 | 規格已修改 |
| 16 | 2 | 編號規則與檢查的範圍有缺口 | Missing AC | Minor | 是 | 否 | 編號不進最終文件 | 涵蓋 ADR、術語表、issue、commit 訊息，並分配檢查責任（需求 7、9） | 開發者 | 規格已修改 |
| 17 | 2 | 新的暫存檔沒列進暫存清單與規格審查的交付內容 | Specification Defect | Minor | 是 | 否 | — | 補上暫存清單、reviewer 的交付內容、核准狀態（需求 2、13） | 主 session（文件同步） | 規格已修改 |
| 18 | 2 | 對照 `origin/main` 前沒有 fetch | Specification Defect | Minor | 是 | 否 | — | 對照前 `git fetch origin main`（需求 3） | 主 session | 規格已修改 |
| 19 | 2 | 暫停後怎麼接續沒定義 | Missing AC | Minor | 是 | 否 | 取消與暫停 | 新 session 複製舊 scratchpad、編號接續（需求 15） | 開發者 | 規格已修改 |
| 20 | 2 | 術語表的收錄範圍不明 | Specification Defect | Minor | 是 | 否 | — | 只收產品領域、使用者看得到的概念（需求 10） | 開發者 | 規格已修改 |
| 21 | 2 | 名稱不同的相近術語在 PR 合併時不會衝突 | Improvement Suggestion | Info | 否 | 否 | — | 寫成已接受的殘留風險；保留術語的文字修正也對照 `origin/main` | 主 session | 規格已修改 |
| 22 | 2 | 這個 PR 交辦時新的 agent 規則還沒生效 | Improvement Suggestion | Info | 否 | 否 | — | 交辦訊息明寫檔案位置與 `git add` 的路徑 | 主 session | 規格已修改 |
| 23 | 3 | 規格審查紀錄的 commit 時機兩處說法不同；第 1 節舊寫法沒列進 AC4 | Specification Defect | Minor | 是 | 否 | 文件的 commit 責任 | PR 建立後、交給 `acceptance-reviewer` 前；實作審查紀錄在交回 implementer 前已 push（需求 4、AC4） | 主 session（對齊既有決定） | 規格已修改 |
| 24 | 3 | ADR 0009「放棄的做法」措辭和決定看起來矛盾 | Specification Defect | Minor | 是 | 否 | 文件的 commit 責任 | 改成「主 session commit 核准後的規格／ADR／術語表修改」（AC16） | 主 session | 規格已修改 |
| 25 | 3 | 接續時複製的清單漏了 ADR 草稿與審查報告原文 | Missing AC | Minor | 是 | 否 | 取消與暫停 | 複製這次開發的全部暫存檔（需求 15、AC14） | 主 session（依既有決定） | 規格已修改 |
| 26 | 3 | 最後一次審查後主 session 的 commit 訊息沒人檢查 | Missing AC | Minor | 是 | 否 | 編號不進最終文件 | 回報前一併檢查（需求 9、AC8） | 主 session（依既有決定） | 規格已修改 |
| 27 | 3 | 沒有定義什麼算「出現 C、Q 編號」 | Specification Defect | Minor | 是 | 否 | 編號不進最終文件 | 禁止的是指向 Context／Frontier 項的引用，說明編號制度不算（需求 7、AC7） | 主 session | 規格已修改 |
| 28 | 3 | 主 session 的 commit、push 和交回 implementer、等 CI 的順序 | Improvement Suggestion | Minor | 否 | 否 | — | 交回前已 push；push 後等 CI（需求 4） | 主 session | 規格已修改 |
| 29 | 3 | 建立 `docs/glossary.md` 的判斷依據 | Improvement Suggestion | Info | 否 | 否 | — | 依 `origin/main`（需求 3） | 主 session | 規格已修改 |
| 30 | 3 | 背景只寫標準、高風險由 implementer 開分支 | Improvement Suggestion | Info | 否 | 否 | — | 改成文字修正以外的等級 | 主 session | 規格已修改 |
| 31 | 3 | 假設 2、AC2、AC14、需求 8 的細節 | Improvement Suggestion | Info | 否 | 否 | — | 依建議補齊 | 主 session | 規格已修改 |

## 問題說明

### #1、#7、#12、#13、#23、#24 文件的 commit 責任

現行規則只寫 implementer「規格檔要一起 commit」（`.claude/agents/feature-implementer.md:8`），收到不對應驗收條件的要求會拒絕（`:15`）；審查紀錄「和修正一起 commit」（`.claude/skills/feature/SKILL.md:203`、`docs/reviews/README.md:11`）沒寫由誰。第 1 輪發現術語表可能沒被 commit，開發者重新設計成核准前只寫 scratchpad、核准後由 implementer 照交付清單 commit；第 2 輪發現核准後的修改沒有人能 commit，開發者把 commit 責任分成三類；第 3 輪對齊審查紀錄的 commit 時機。

### #3、#14、#16、#26、#27 編號不進最終文件

編號只存在 scratchpad，reviewer 的報告與主 session 整理的紀錄卻可能引用它。各輪依序補上：寫進最終文件前換成內容與落點、檢查的責任分配、reviewer 看不到的最終版由主 session 檢查、「出現編號」的定義。

### #5、#19、#25 取消與暫停

現行流程沒有取消與暫停的步驟；scratchpad 的路徑跟著 session。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 核准後誰 commit 術語表 | 交付清單／只在交辦訊息提／主 session 先開分支 | 交付清單；術語核准前改寫在 scratchpad，合併前確認 main 上有沒有相同或相近的術語 | Git 由工程流程負責，核准前不碰共用的工作目錄 |
| 3 | 編號會進審查紀錄 | 這個 PR 補／另開 issue | 這個 PR 補，並寫進 reviewer 的檢查項目，不加自動化檢查 | 避免只依賴主 session 的記憶 |
| 5、19 | 取消、暫停 | — | 取消時列出術語請開發者決定保留或不保留；暫停後新 session 複製舊 scratchpad、編號接續 | — |
| 6 | 其他階段確定的術語 | — | 核准前任何階段都一樣記錄 | — |
| 7 | 審查紀錄由誰 commit | 嚴格由 implementer／主 session 例外 | 主 session 可 commit，只限這次的 PR 分支與 `docs/reviews/`，限定 staging 範圍，歸屬不明就停止 | 避免最後一輪只為了 commit 紀錄再叫一次 implementer |
| — | 流程順序 | — | 維持 PR → CI → Review | CI 只在 PR 上跑，審查要看 CI 結果 |
| 12 | 核准後的修改由誰寫入與 commit | implementer 照交付清單／擴大主 session 範圍 | implementer 照交付清單；commit 責任分三類：產品文件與程式碼由 implementer，審查紀錄由主 session commit 並 push | 責任分明、術語一定先對照 `origin/main` |
| 13 | 審查紀錄 commit 後要不要 push | — | 要 push 到同一個 PR 分支 | 最後一輪沒有修正時紀錄才不會只留在本機 |
| 14 | 最終 PR 描述與紀錄誰檢查 | — | 交辦時附 PR 描述全文；回報前主 session 檢查 | reviewer 看不到最後一次審查之後才寫的內容 |
| 15 | 問答階段的決定要不要進「開發者決策」表 | 只記審查後的決定／全部都記 | 只記審查後的決定，問答的決定只留在規格 | — |
| 16 | 編號規則的範圍 | — | 涵蓋 ADR、術語表、issue、commit 訊息，補上檢查責任 | — |
| 20 | 術語表收錄範圍 | 產品領域／也收流程用詞 | 只收產品領域、使用者看得到的概念 | 流程用詞已定義在 skill 與 `docs/` |

## 尚未處理

無。

## 查證紀錄（第 3 輪）

| 規格中的事實 | 結果 | 依據（檔案:行號） |
|---|---|---|
| `<功能>-grill.md` 不 commit | 正確 | `.claude/skills/feature/SKILL.md:115` |
| 修改紀錄要求寫 C 編號，所有等級 | 正確 | `.claude/skills/feature/SKILL.md:168`、`docs/specs/README.md:96` |
| PR #67 的規格有 D9、D11、D12，規格審查紀錄有 D9 | 正確 | `docs/specs/feature-grilling.md:121-122`、`docs/reviews/specification/feature-grilling.md:7` |
| implementer 的規則只寫「規格檔要一起 commit」，拒絕不對應驗收條件的要求 | 正確 | `.claude/agents/feature-implementer.md:8`、`:15` |
| 審查紀錄「和修正一起 commit」「和規格一起 commit」沒寫由誰 commit | 正確 | `.claude/skills/feature/SKILL.md:132`、`:203`、`docs/reviews/README.md:11` |
| 文字修正以外的等級由 implementer 開分支 | 正確 | `.claude/skills/feature/SKILL.md:30-32` |
| 沒有術語表，產品用詞散在規格與程式碼 | 正確 | `docs/glossary.md` 不存在；`backend/schemas/manual_task.py` |
| `acceptance-reviewer` 只能跑 git 唯讀指令與測試，讀不到 PR 描述 | 正確 | `.claude/agents/acceptance-reviewer.md:15` |
| ADR 0008 決定「修改紀錄所有等級都寫 C 編號」，沒有 commit 責任的決定；下一個 ADR 是 0009 | 正確 | `docs/decisions/0008-grilling-without-plan-mode.md:26`、`docs/decisions/` |
| 判斷 Context 落點的位置 | 正確 | `.claude/skills/feature/SKILL.md:115-117`、`:223`、`docs/README.md:22`、`.claude/agents/specification-reviewer.md:22` |
| `grill-with-docs`、`domain-modeling`、`GLOSSARY-FORMAT` 的內容（mattpocock/skills `4ae2317`，MIT） | 無法在 repo 查證 | 外部來源；主 session 在規格撰寫時用 `gh api` 讀過原文 |

## 已接受的風險

- 兩個還沒合併的 PR 用不同名稱寫同一個概念時，合併前的對照看不到對方，git 也不會衝突，兩個都可能進 `main`（規格「不適用的情境」併發列）。
- 不加 C、Q 編號的自動化檢查，靠 reviewer 與主 session 人工確認（開發者決定）。
- 既有規格與審查紀錄裡的 C／D 編號不回補（開發者決定）。
- 這個 PR 交辦時新的 agent 規則還沒生效，交辦訊息明寫檔案位置與 `git add` 的路徑。
