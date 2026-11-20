# 需求問答先確認要防哪些情況與在哪一步處理，規格寫明不處理的情況審查不列成發現

- 狀態：部分被 [issue-155-review-labels.md](issue-155-review-labels.md) 取代（AC5、AC7、AC8）
- 等級：一般（改 `clarify-requirements`、`docs/specs/README.md`、`docs/reviews/README.md`、兩個 reviewer 定義裡的流程規則；不改程式碼，不涉及資料一致性、認證授權、憑證保護，也不是重大架構決策）
- issue：#139
- PR：#141

## 簡短說明

處理安全、資料清理或輸入驗證的需求時，需求問答要先確認「要防哪些情況、不防哪些」，以及「在哪一步處理」；規格「不做」寫明不處理的情況，審查不列成發現，寫在「已接受的風險」。

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/139

**問題**：安全、資料清理這類需求，可能出問題的情況沒有上限。規格沒寫「要防哪些、不防哪些」時，reviewer 沒有依據判斷哪些情況不用防，只能把每個找得到的情況都列成阻擋，審查就沒有停止的時候。另外兩個原因讓問題更嚴重：

1. 需求問答沒有問「問題最後在哪一步發生」。在比那一步更早的地方處理資料，要逐一處理每一種資料的形狀，特殊情況會更多。
2. 「測試對應」只寫「不含某某」、沒寫完整的預期輸出時，實作補的測試只檢查一面，審查又會找到另一面。

現在的規則：

- `docs/reviews/README.md`「分類」規定「規格內容互相矛盾或沒有依據」與「規格沒寫某個情境該怎麼做」一律阻擋（`docs/reviews/README.md:28-29`），沒有排除規格明確不處理的情況。
- 「已接受的風險」機制已經存在：`specification-reviewer` 把規格明確接受的風險寫進報告的「已接受的風險」（`.claude/agents/specification-reviewer.md:44`），`acceptance-reviewer` 不再把它們列成新發現（`.claude/agents/acceptance-reviewer.md:7`）。但 `acceptance-reviewer` 報告裡的「已接受的風險」只定義了 scratchpad 遺失的情況（`.claude/agents/acceptance-reviewer.md:29`、`docs/reviews/README.md:138`）；實作審查紀錄的「已接受的風險」一節只列 scratchpad 遺失時不算問題的情況與決定不補的項目（`docs/reviews/README.md:207`）。
- `clarify-requirements`「工程方案探索」第 2 點（`.claude/skills/clarify-requirements/SKILL.md:125-130`）只問能不能用現有機制，沒問在哪一步用。
- 判斷的規則寫在 `docs/reviews/README.md`，兩個 reviewer 與主 session 都讀；scratchpad 遺失的例外也寫在那裡（`docs/reviews/README.md:37`）。

**案例**：開發者用 `/issue 50` 做「e2e 錯誤印進 CI log 前要清理」。PR #126 的實作審查跑了 8 輪（`docs/reviews/implementation/issue-50-sanitize-error-properties.md`，在 `issue-50-sanitize-error-properties` 分支）。

- 第 2 輪起的阻擋多數是查不到實際來源、要刻意寫出來才會發生的寫法：紀錄的 #5、#10、#12、#15、#16、#18、#19、#20 都寫了查不到來源。例如 `Object.create` 建立的原型、不存值的 setter、會說謊的 Proxy（攔截讀取與列舉、兩次回答不一致的物件）。
- 每一項都要開發者決定，最後 PR 關閉。
- 問題其實發生在 vitest 印出錯誤的那一步，#50 改用 vitest custom reporter 重做，就沒有這些物件的特殊情況。
- 第 1～3 輪的測試對應只寫「不含某某」，第 3 輪開發者決定把完整的預期字串寫進規格（紀錄開發者決策 #9）。

## 需求

1. `.claude/skills/clarify-requirements/SKILL.md`「需求問答」的「提問原則」新增一條，放在「不為了涵蓋所有可能的例外情境而持續增加問題」之前。需求涉及安全、資料清理或輸入驗證時，主 session 先問要防哪些情況：
   1. 列出實際來源（實際會把要防的內容，例如機密、不可信的輸入，帶進來的地方），例如環境變數、外部服務的回應、使用者輸入，各附一個例子，請開發者確認哪些要防。
   2. 查不到實際來源、要刻意寫出來才會出現的情況，建議答案是列進規格的「不做」，寫成「不處理：<情況>」並附上判斷的依據（例如「查不到會產生這種物件的套件」）。
   3. 開發者的決定寫進規格的「需求」或「不做」。
2. 同一檔「工程方案探索」第 2 點新增一問：問題最後在哪一步發生（例如寫進 log、印出、存進資料庫）？先找那一步有沒有現成的處理機制，在那一步處理；不在更早的步驟逐一處理資料。
3. `docs/specs/README.md`「驗收條件怎麼寫」新增一條：清理、轉換這類結果，「測試對應」寫出完整的預期輸出，不只寫「不含某某」。
4. `docs/reviews/README.md`「分類」「問題類型」下方的清單新增一條規則。reviewer 找到的情況和規格「不做」寫的內容有關時，照下面的順序判斷，符合第一個就停：
   1. 「涉及安全／架構」是「漏洞」：照「漏洞」的規則，一律阻擋（`docs/reviews/README.md`「涉及安全／架構」）。
   2. 實作做了「不做」排除的改動（例如「不做」寫不改資料庫裡的資料，實作卻改了）：列成發現，照一般的分類判斷。
   3. reviewer 查證到「不做」依據的事實不成立（查到實際來源，或實際後果和「不做」寫的不同）：列成發現，類型與阻擋照根本原因判斷。查到的事實和規格審查的查證紀錄不同時，也照這一步（例如實作新增了會產生這個情況的依賴）。
   4. 規格審查時，reviewer 認為某個情況不該列在「不做」，但沒有上一步那種新查到的事實：列成「沒有錯，但可以更好」，不阻擋。
   5. 情況是「不做」裡寫明不處理的：不列成發現，寫在報告的「已接受的風險」。比 main 退步也一樣。
   6. 都不符合：照一般的分類判斷。
5. 第 4 點第 5 步寫進「已接受的風險」的情況，在下面三處加上，和各處現有的情況並列：
   1. `docs/reviews/README.md`「報告格式」中 `acceptance-reviewer` 檢查表的「已接受的風險」（`:138`）。
   2. `docs/reviews/README.md`「紀錄檔格式」實作審查紀錄的「## 已接受的風險」一節（`:207`）。
   3. `.claude/agents/acceptance-reviewer.md` 回報格式的「已接受的風險」定義（`:29`）。
6. `.claude/agents/specification-reviewer.md` 回報格式的「已接受的風險」定義（`:44`）寫明包括規格「不做」裡寫明不處理的情況。
7. 審查怎麼處理「不做」裡的情況，判斷規則只寫在需求 4 那一處；需求 5、6 新增的句子只寫「已接受的風險」包括哪些情況，並寫「另見『分類』的『不做』判斷順序」；`clarify-requirements` 不寫審查怎麼處理。
8. `.claude/agents/acceptance-reviewer.md:16`、`.claude/agents/specification-reviewer.md:27` 的「只限 scratchpad 遺失」不改：它限制的是 scratchpad 遺失那一條規則的範圍。
9. 新增的文字用同一組詞：「不做」、「不處理：<情況>」、「實際來源」、「已接受的風險」、「發現」、「阻擋」、「判斷順序」。同一個概念不換說法（例如不寫「列為發現」「排除的風險」「真實來源」）；「發現」「阻擋」「已接受的風險」照 `docs/README.md`「流程用語」的意思。

## 不做

- 不改 `implement-and-review` 的「發現處理表」：規格「不做」裡寫明不處理的情況不列成發現，不會走到處理表。
- 不改 `docs/specs/README.md`「格式」的「不做」寫法規定；需求 1 第 2 點只規定需求問答建議的寫法。
- 不改既有規格、審查紀錄（包括 #50 的）的內文。
- 規格寫法的通則（背景先寫問題、驗收方式寫出步驟、例外寫成判斷順序）另外在 #140 處理。
- 不改程式碼。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 主 session 處理涉及安全、資料清理或輸入驗證的需求時，照 `clarify-requirements`「提問原則」，第一輪問答會列出實際會把要防的內容帶進來的地方（各附一個例子），請開發者確認哪些要防 |
| AC2 | 照同一條提問原則，查不到實際來源的情況，主 session 給的建議答案是寫進規格「不做」的「不處理：<情況>」，並附上判斷依據 |
| AC3 | 主 session 做工程方案探索時，照「工程方案探索」第 2 點，會問問題最後在哪一步發生、那一步有沒有現成的處理機制 |
| AC4 | 主 session 寫清理、轉換類需求的規格時，照 `docs/specs/README.md`「驗收條件怎麼寫」，「測試對應」寫出完整的預期輸出 |
| AC5 | reviewer 找到的情況和「不做」有關時，`docs/reviews/README.md`「分類」給出編號的判斷順序，符合第一個就停，內容和需求 4 的 6 步相同 |
| AC6 | 規格「不做」寫明不處理的情況，`acceptance-reviewer` 照 AC5 判斷後，不列成發現，寫在報告的「已接受的風險」；比 main 退步也一樣 |
| AC7 | 同一個情況被標成「漏洞」時，照 AC5 第 1 步阻擋 |
| AC8 | 實作做了「不做」排除的改動時，照 AC5 第 2 步列成發現，「程式沒照規格做」照常阻擋 |
| AC9 | reviewer 查到「不做」依據的事實不成立時，照 AC5 第 3 步列成發現 |
| AC10 | 主 session 整理實作審查紀錄時，照 `docs/reviews/README.md`「紀錄檔格式」，把 AC6 的情況寫進「## 已接受的風險」一節 |
| AC11 | `acceptance-reviewer.md`、`specification-reviewer.md`、`docs/reviews/README.md`「報告格式」對「已接受的風險」的定義，都包括「不做」裡寫明不處理的情況，並指向「分類」的判斷順序 |
| AC12 | 「不做」的判斷順序只寫在 `docs/reviews/README.md`「分類」一處，`clarify-requirements` 沒有寫審查怎麼處理 |
| AC13 | 新增的文字引用的檔案路徑、節名稱都存在 |
| AC14 | PR 描述有 `Closes #139` |
| AC15 | 新增的文字只用需求 9 列的詞指同一個概念 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限、資料處理 | 只改流程文件，沒有畫面、API 與資料 |
| 安全性 | 不改「漏洞的處理」；「漏洞」在判斷順序的第 1 步（AC7） |

## 實作計畫

分支 `issue-139-protection-scope`：

1. `.claude/skills/clarify-requirements/SKILL.md`：「提問原則」加一條（需求 1）；「工程方案探索」第 2 點加一問（需求 2）。
2. `docs/specs/README.md`「驗收條件怎麼寫」加一條（需求 3）。
3. `docs/reviews/README.md`：
   - 「分類」「問題類型」下方的清單加判斷順序（需求 4），放在 scratchpad 遺失的例外之後。
   - 「報告格式」`:138`、「紀錄檔格式」`:207` 加上這類情況（需求 5）。
4. `.claude/agents/acceptance-reviewer.md:29`、`.claude/agents/specification-reviewer.md:44`：「已接受的風險」的定義各加一句（需求 5、6）。
5. 新增的文字照 CLAUDE.md「寫作規則」寫。
6. `docs/specs/issue-139-protection-scope.md`、`docs/reviews/specification/issue-139-protection-scope.md`、`docs/reviews/implementation/issue-139-protection-scope.md`。
7. PR 描述加 `Closes #139`。

只改 `.md`，CLAUDE.md「完成的定義」的檢查不用跑。

## 測試對應

每項演練由 `acceptance-reviewer` 照改完的文件做一次，結果寫在 PR 描述的對照表。

| AC | 驗證步驟 | 預期結果 |
|---|---|---|
| AC1、AC2 | 讀改完的「提問原則」；以 #50 的需求「e2e 錯誤印進 CI log 前要清理」為輸入，照條文列出第一輪問答的題目 | 題目列出至少兩個實際來源（例如 Playwright 錯誤帶的頁面內容、環境變數），各附一個例子；`Object.create` 原型、會說謊的 Proxy 的建議答案是「不做」裡的「不處理：…」，附上「查不到來源」的依據 |
| AC3 | 讀改完的「工程方案探索」第 2 點；以同一個需求照條文回答新增的那一問 | 答出問題發生在 vitest 印出錯誤的那一步，並指出要先找那一步現成的機制（vitest reporter） |
| AC4 | 讀改完的「驗收條件怎麼寫」 | 有一條要求清理、轉換類結果的測試對應寫出完整預期輸出 |
| AC5 | 讀改完的「分類」 | 有編號 1～6 的判斷順序，寫明「符合第一個就停」，每一步的條件與結果和需求 4 相同 |
| AC6 | 假設 #50 的規格在「不做」寫「不處理：原型鏈上會說謊的 Proxy（查不到會產生這種物件的套件）」；以 #126 紀錄的 #16 照 AC5 判斷 | 停在第 5 步：不列成發現，寫在「已接受的風險」 |
| AC7 | 同 AC6 的假設，把 #16 的「涉及安全／架構」改成「漏洞」再判斷一次 | 停在第 1 步：阻擋 |
| AC8 | 假設規格「不做」寫「不改程式碼」，實作改了 `backend/` 的檔案，照 AC5 判斷 | 停在第 2 步：列成「程式沒照規格做」，阻擋 |
| AC9 | 同 AC6 的假設，再假設 reviewer 查到 e2e 用到的某個套件會產生這種 Proxy，照 AC5 判斷 | 停在第 3 步：列成發現，類型照根本原因判斷 |
| AC10 | 讀改完的「紀錄檔格式」`## 已接受的風險` 的規則 | 列出的情況包括「規格『不做』裡寫明不處理的情況」，並寫出「分類」的節名稱 |
| AC11 | 讀三處「已接受的風險」的定義 | 三處都包括這類情況，並寫出「分類」的節名稱 |
| AC12 | 跑 `git grep -n "不處理" -- .claude docs/reviews/README.md docs/specs/README.md`，再讀 `clarify-requirements` 新增的條文 | 判斷順序只出現在 `docs/reviews/README.md`「分類」；`clarify-requirements` 的條文沒有寫阻不阻擋、記在哪裡 |
| AC13 | 對新文字裡每個引用的節名稱跑 `grep -n "<節名稱>" <檔案>` | 每個都找得到 |
| AC14 | 跑 `gh api repos/{owner}/{repo}/pulls/<PR> --jq .body` | 輸出有 `Closes #139` |
| AC15 | 跑 `git diff origin/main -- .claude docs/reviews/README.md docs/specs/README.md`，看新增的行；再對 `列為發現`、`排除的風險`、`真實來源`、`接受風險` 各跑一次 `git grep -n` | 新增的行裡同一個概念只用需求 9 的詞；四個說法在改到的檔案裡都沒有出現在新增的行 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
