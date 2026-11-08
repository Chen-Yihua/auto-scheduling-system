# acceptance-reviewer 的審查範圍改以 origin/main 為基準

- 狀態：已核准
- 等級：標準（改的是 agent 定義裡決定審查範圍的規則，符合「改定義流程或規則的文件裡的規則」；不是只改措辭，所以不是文字修正。改動只在一個檔案，也可以看成「單一範圍的 bug」，但判斷不確定時取較高的等級）
- issue：[#21](https://github.com/Chen-Yihua/auto-scheduling-system/issues/21)
- PR：[#58](https://github.com/Chen-Yihua/auto-scheduling-system/pull/58)

## 背景

**現象**：開發者執行 `/feature` 或 `/issue`，流程進到第 3 節，主 session 先跑 `git fetch origin main`，再交給 `acceptance-reviewer`。開發者的本機 `main` 如果有一段時間沒 pull，reviewer 審查的範圍會混進其他已合併的 PR。reviewer 可能把別的 PR 的問題當成這次的發現，甚至列成阻擋，多跑幾輪修正與審查；開發者也要另外分辨哪些發現不屬於這次的改動。使用者不受影響。

**重現步驟**（PR #18 審查第 5 輪 #3，`docs/reviews/issue-workflow-round5.md:50`）：
1. 本機 `main` 停在舊的 commit（實測 `5ae21a7`），`origin/main` 已經前進到 `e3286b8`。
2. 在功能分支上照 reviewer 定義跑 `git diff main...HEAD`。

**預期**：審查範圍只有這個分支相對 `origin/main` 的改動（實測 15 個檔案）。
**實際**：68 個檔案，混進了 `5ae21a7..e3286b8` 之間已合併的 PR。

**原因**：
- `.claude/agents/acceptance-reviewer.md:7` 寫「用 `git diff main...HEAD` 看改動」，比對的是本機 `main`。
- `.claude/skills/feature/SKILL.md:72` 交給 reviewer 前的 `git fetch origin main` 只更新 `origin/main`，不會更新本機 `main`。
- `.claude/agents/acceptance-reviewer.md:28` 已經用 `git show origin/main:<檔案>`，`SKILL.md` 第 4 節（`:146`）也用 `origin/main`；只有 `acceptance-reviewer.md:7` 用本機 `main`。

## 需求

- reviewer 定義裡指定審查範圍的指令，改成和 `origin/main` 比對。
- `/feature` 第 3 節交給 reviewer 前先 `git fetch origin main` 的規定保持不變（reviewer 改用 `origin/main` 後，靠這一步讓 `origin/main` 是最新的）。

## 不做

- 不讓 reviewer `git fetch`、`git pull`、切換或改動本機 `main`：reviewer 是唯讀的（issue「必要條件」、`acceptance-reviewer.md:15`）。
- 不處理 `.claude/agents/feature-implementer.md:8`「從 `main` 開指定的分支」：issue 的「待調查」明確列為不在範圍內。
- 不改歷史審查紀錄（`docs/reviews/`）裡的 `main...HEAD` 文字：紀錄保存當時的事實。

## 假設

1. reviewer 只會經由 `/feature`（含經 `/feature` 流程的 `/issue`）第 3 節被叫起，所以 `origin/main` 在審查前一定剛 fetch 過。開發者自己直接叫 reviewer 而沒有 fetch 的情況，`origin/main` 可能是舊的；那時多出的範圍是「`origin/main` 舊於分支起點」才會發生的，不在本 issue 範圍。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 在本機 `main` 落後 `origin/main` 的情況下，reviewer 定義（`.claude/agents/acceptance-reviewer.md`）指定的審查範圍指令，列出的檔案和 `git diff --stat origin/main...HEAD` 相同，不包含本機 `main` 與 `origin/main` 之間已合併的改動 |
| AC2 | `.claude/agents/` 與 `.claude/skills/` 裡決定審查範圍（`git diff <基準>...HEAD`）的指令，基準都是 `origin/main`，沒有用本機 `main` 的 |
| AC3 | 修正後，reviewer 定義仍然只要求唯讀操作（不 fetch、不 pull、不切換或改動任何分支），`/feature` 第 3 節交給 reviewer 前仍有 `git fetch origin main` |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗（fetch 失敗） | `/feature` 第 3 節的 fetch 規定沒有改；fetch 失敗時主 session 會看到錯誤，不屬於這次的修正 |
| 空資料（分支沒有任何改動） | `origin/main...HEAD` 為空時 reviewer 看到沒有改動，行為和修正前用 `main...HEAD` 一樣，沒有新的分支 |
| 分支是從舊的本機 `main` 開的 | `origin/main...HEAD` 以 merge-base 為起點；舊的本機 `main` 是 `origin/main` 的祖先，merge-base 就是分支起點，範圍只有分支自己的 commit，不會多也不會少 |
| 載入中、未登入／無權限 | 沒有改到程式與畫面，只改 agent 定義 |
| 資料處理、安全性 | 不碰資料、憑證或權限；reviewer 仍是唯讀（AC3） |

## 實作計畫

1. 從 `main` 開分支 `issue-21-reviewer-diff-origin-main`。
2. `.claude/agents/acceptance-reviewer.md:7`：「用 `git diff main...HEAD` 看改動」改成「用 `git diff origin/main...HEAD` 看改動（主 session 交給你前已經 fetch；不要用本機 `main`，它可能落後）」。其他文字不動。
   - 為什麼這樣修：`origin/main` 是主 session 已經 fetch 的基準，reviewer 不用做任何寫入操作就能拿到正確範圍；同一檔案 `:28` 已經用 `origin/main`，修正後前後一致。
3. 不改 `.claude/skills/feature/SKILL.md`：`:72` 的 fetch 已經存在，只在 AC3 確認沒被動到。
4. 規格存成 `docs/specs/issue-21-reviewer-diff-origin-main.md`，規格審查紀錄 `docs/reviews/specification/issue-21-reviewer-diff-origin-main.md`，一起 commit；PR 描述加 `Closes #21`。
5. 只改 `.md`，CLAUDE.md「完成的定義」的 pyright／pytest／前端檢查不適用（沒有改到程式）；CI 照常要通過。

## 測試對應

agent 定義是給 LLM 讀的 Markdown，沒有自動化測試能執行它；用以下手動驗證，結果寫進 PR 描述的驗收表。

| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | 手動，不改任何分支：取 `origin/main` 的較舊祖先當「落後的本機 `main`」（例如 `OLD=$(git rev-parse origin/main~5)`），在功能分支上比較 `git diff --stat $OLD...HEAD` 與 `git diff --stat origin/main...HEAD` 的檔案數，前者較多；再確認 `acceptance-reviewer.md` 指定的指令是後者 | 是（修正前定義指定的是 `main...HEAD`，本機 `main` 落後時等同前者） |
| AC2 | `grep -rnE '[^/]main\.\.\.|^main\.\.\.' .claude/` 沒有結果；`grep -rn 'origin/main\.\.\.HEAD' .claude/` 有 `acceptance-reviewer.md` 那一行 | 是（修正前會找到 `acceptance-reviewer.md:7`） |
| AC3 | 讀 `acceptance-reviewer.md` 的唯讀限制段落沒有被改，修正那一行沒有要求 fetch／pull／checkout；`grep -n 'git fetch origin main' .claude/skills/feature/SKILL.md` 有第 3 節那一行 | 否（保護既有行為） |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
