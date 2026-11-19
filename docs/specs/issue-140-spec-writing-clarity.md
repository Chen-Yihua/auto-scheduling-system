# 規格先寫問題、驗收條件寫出要達成的結果、有先後順序的條件寫成判斷順序

- 狀態：已核准
- 等級：一般（改 `docs/specs/README.md`、`CLAUDE.md`「寫作規則」、`write-spec` skill、兩個 reviewer 定義裡的流程規則；不改程式碼，不涉及資料一致性、認證授權、憑證保護，也不是重大架構決策）
- issue：#140
- PR：#NN

## 簡短說明

規格的「背景」先寫問題本身；驗收條件與「測試對應」寫出要達成的結果和驗證步驟；有先後順序的條件寫成編號的判斷順序。兩個 reviewer 檢查這些寫法。

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/140

**問題**：開發者核准規格前，要能從規格看出要解決什麼問題、怎樣算完成、怎麼驗證。現在的寫法規則沒有要求這三件事，規格常常要開發者自己整理才看得懂，開發者也可能核准一份看不出驗證方式的規格。

**案例**：開發者在 `/issue 139` 讀規格草稿時：

- 「背景」一開頭就是 PR #126 的案例，沒先寫出問題本身。
- 「測試對應」寫「用 #50 走一次」「讀某某節」，看不出要做哪些步驟、看到什麼才算通過。已合併的規格也有同樣的寫法，例如 `docs/specs/issue-69-context-in-repo.md:184` 寫「讀 `/feature`，各走一次流程」。
- 需求 4 的例外寫成「原則＋例外＋例外的例外」，沒有判斷順序。

**現在的規則**：

- `docs/specs/README.md`「格式」的「背景」只寫「為什麼要做」（`docs/specs/README.md:42`）；「修 bug 時」的背景從重現步驟開始寫（`:85`）。
- `docs/specs/README.md`「驗收條件怎麼寫」要求每條「寫得出對應的測試，或寫明手動驗證的步驟」（`:23`），沒有要求寫預期結果；「格式」的「測試對應」範本只有 `AC | 測試` 兩欄（`:68`）。
- `CLAUDE.md`「寫作規則」有 4 條（`CLAUDE.md:70-75`），沒有規定有先後順序的條件怎麼寫。
- `.claude/agents/specification-reviewer.md` 第 6 項「寫法」（`:19`）檢查沒有定義的專有名詞、一條講了不只一件事、「簡短說明」寫不清楚，沒有檢查上面三點。
- `.claude/agents/acceptance-reviewer.md` 第 6 項「寫法」（`:14`）檢查 PR 改到的 md 檔有沒有違反「寫作規則」第 1、2 條。
- `.claude/skills/write-spec/SKILL.md:16` 的驗收條件範本是「在 X 情況下，系統要 Y」；`:17` 只要求「每條驗收條件對應的測試」。

**一般的做法**：

- 驗收條件常見兩種寫法：列出必須達成的結果（規則清單），或結果隨情況不同時寫成「在什麼情況下、做了什麼、結果是什麼」（Given／When／Then 的意思）。兩種依內容挑一種用。參考 Liz Keogh〈Acceptance Criteria vs. Scenarios〉、GitHub spec-kit 的 `spec-template.md`。
- 手動測試案例把「步驟」和「預期結果」分開寫。

## 需求

1. `docs/specs/README.md`「格式」的「背景」（`:42`）改成：「先用一兩句寫出問題本身，再用實際案例說明。由 issue 來的規格，來源連結寫在問題前面。」
2. `docs/specs/README.md`「修 bug 時」的「背景」（`:85`）：把「寫重現步驟、預期與實際的結果，以及原因」換成「先用一兩句寫出問題本身，再寫重現步驟、預期與實際的結果，以及原因」，後半句不變。
3. `docs/specs/README.md`「驗收條件怎麼寫」的清單最前面加一條：「驗收條件定義怎樣算完成：列出必須達成的具體結果。結果會隨情況不同時，寫出在什麼情況下、做了什麼、結果是什麼。」
4. `docs/specs/README.md`「格式」的驗收條件範本（`:56`）改成兩列例子：`AC1 | <必須達成的結果>`、`AC2 | 在 X 情況下，做 Y，結果是 Z`。
5. `docs/specs/README.md`「驗收條件怎麼寫」的「每條都要能驗證」（`:23`）改成：「每條都要能驗證：寫出對應的測試，或手動驗證的步驟（讀哪個檔案的哪一節、輸入什麼、跑什麼指令、查看哪個 CI run 或部署紀錄）與預期結果。」
6. `docs/specs/README.md`「格式」的「測試對應」範本（`:68`）改成三欄：`AC | 測試或驗證步驟 | 預期結果`。
7. `CLAUDE.md`「寫作規則」新增第 5 條：「5. 幾個條件有先後順序時，寫成編號清單，照順序判斷。每一條寫明符合後停止，還是繼續看下一條；每一條的做法都相同時，在清單前寫一次就好。不寫成「原則＋例外＋例外的例外」。」
8. `CLAUDE.md`「寫作規則」開頭的「寫文件時照下面 4 條」改成「5 條」。
9. `.claude/agents/specification-reviewer.md` 第 6 項「寫法」（`:19`）的清單後面加上：「「背景」沒有先寫出問題本身；驗收條件看不出必須達成的結果；「測試對應」缺少步驟或預期結果；有先後順序的條件沒有照「寫作規則」第 5 條寫。」
10. `.claude/agents/acceptance-reviewer.md` 第 6 項（`:14`）的「第 1、2 條」改成「第 1、2、5 條」，檢查範圍照舊。
11. `.claude/skills/write-spec/SKILL.md:16` 的「驗收條件」改成：「編號 AC1、AC2…，照 `docs/specs/README.md`「驗收條件怎麼寫」，每條都要能驗證。」後半句「逐一想過失敗…」不變。
12. `.claude/skills/write-spec/SKILL.md:17` 的「每條驗收條件對應的測試」改成「每條驗收條件對應的測試或驗證步驟，與預期結果」。

## 不做

- 不改 `docs/issues.md`：它的「建議的驗收條件」寫法連到 `docs/specs/README.md`「驗收條件怎麼寫」，範本的例子也還適用。
- 不改既有規格、審查紀錄的內文。
- 不改程式碼。
- 不處理同一條規則重複寫在多個檔案、不把全部流程文件對照一般工程做法：另開 issue #147、#148。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | `docs/specs/README.md`「格式」的「背景」寫明先寫問題本身、再寫案例，由 issue 來的規格來源連結寫在問題前面 |
| AC2 | `docs/specs/README.md`「修 bug 時」的「背景」寫明問題本身寫在重現步驟之前 |
| AC3 | `docs/specs/README.md`「驗收條件怎麼寫」的第一條寫明驗收條件列出必須達成的結果，結果隨情況不同時寫出情況、動作、結果 |
| AC4 | `docs/specs/README.md`「格式」的驗收條件範本有需求 4 的兩列例子 |
| AC5 | `docs/specs/README.md`「驗收條件怎麼寫」要求手動驗證寫出具體步驟與預期結果 |
| AC6 | `docs/specs/README.md`「格式」的「測試對應」範本是 `AC \| 測試或驗證步驟 \| 預期結果` 三欄 |
| AC7 | `CLAUDE.md`「寫作規則」有第 5 條，內容和需求 7 相同，開頭寫「5 條」 |
| AC8 | `specification-reviewer.md` 第 6 項包括需求 9 的四點 |
| AC9 | `acceptance-reviewer.md` 第 6 項檢查「寫作規則」第 1、2、5 條，檢查範圍仍是這個 PR 改到的 md 檔 |
| AC10 | 在這個 PR 的實作審查中，`acceptance-reviewer` 照改完的 `specification-reviewer.md` 第 6 項與「寫作規則」第 5 條檢查 `docs/specs/issue-69-context-in-repo.md`，結果是列出「測試對應」缺少步驟或預期結果的發現 |
| AC11 | 在這個 PR 的實作審查中，`acceptance-reviewer` 照同樣的規則檢查 `docs/specs/issue-139-protection-scope.md`，結果是沒有需求 9 那四點的發現 |
| AC12 | 新增的文字引用的檔案路徑、節名稱都存在 |
| AC13 | `write-spec/SKILL.md` 的「驗收條件」與「計畫與測試對應」內容和需求 11、12 相同 |
| AC14 | PR 描述有 `Closes #140` |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限、資料處理、安全性 | 只改流程文件，沒有畫面、API 與資料 |

## 實作計畫

分支 `issue-140-spec-writing-clarity`：

1. `docs/specs/README.md`：需求 1～6。
2. `CLAUDE.md`：需求 7、8。
3. `.claude/agents/specification-reviewer.md`：需求 9。
4. `.claude/agents/acceptance-reviewer.md`：需求 10。
5. `.claude/skills/write-spec/SKILL.md`：需求 11、12。
6. 新增 `docs/specs/issue-140-spec-writing-clarity.md`、`docs/reviews/specification/issue-140-spec-writing-clarity.md`、`docs/reviews/implementation/issue-140-spec-writing-clarity.md`。
7. PR 描述加 `Closes #140`。

只改 `.md`，CLAUDE.md「完成的定義」的檢查不用跑。

## 測試對應

AC10、AC11 是這個 PR 對新審查規則做的一次性驗證，不改 `acceptance-reviewer` 平常的檢查範圍。主 session 交給 `acceptance-reviewer` 的驗證指示只寫要檢查哪一份規格、照哪幾條規則，不寫預期會找到的問題；結果寫在 PR 描述，每份規格寫出：是否符合下表的預期結果、每項發現的位置（`檔案:行號`）、違反哪條規則、判斷理由。

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1、AC2 | 讀改完的 `docs/specs/README.md`「格式」的「背景」與「修 bug 時」的「背景」 | 兩處都寫明先寫問題本身；「格式」寫明由 issue 來的規格，來源連結寫在問題前面；「修 bug 時」寫明問題寫在重現步驟之前 |
| AC3 | 讀改完的「驗收條件怎麼寫」第一條 | 內容和需求 3 相同 |
| AC4、AC6 | 讀改完的「格式」範本的「驗收條件」與「測試對應」 | 驗收條件有兩列例子；測試對應是三欄 |
| AC5 | 讀改完的「驗收條件怎麼寫」的「每條都要能驗證」 | 內容和需求 5 相同 |
| AC7 | 讀改完的 `CLAUDE.md`「寫作規則」 | 開頭寫「5 條」；第 5 條內容和需求 7 相同 |
| AC8 | 讀改完的 `specification-reviewer.md` 第 6 項 | 包括需求 9 的四點 |
| AC9 | 讀改完的 `acceptance-reviewer.md` 第 6 項 | 寫「第 1、2、5 條」；範圍仍是「這個 PR 改到的 md 檔」 |
| AC10 | 照改完的 `specification-reviewer.md` 第 6 項與「寫作規則」第 5 條，檢查 `docs/specs/issue-69-context-in-repo.md` | 至少一項「測試對應」缺少步驟或預期結果的發現 |
| AC11 | 照同樣的規則，檢查 `docs/specs/issue-139-protection-scope.md` | 沒有需求 9 那四點的發現 |
| AC12 | 對新文字裡每個引用的節名稱跑 `grep -n "<節名稱>" <檔案>`；對每個引用的檔案路徑跑 `test -e <路徑>` | 每個節名稱都找得到；每個路徑都存在 |
| AC13 | 讀改完的 `.claude/skills/write-spec/SKILL.md`「規格內容」 | 「驗收條件」與「計畫與測試對應」兩條內容和需求 11、12 相同 |
| AC14 | 跑 `gh api repos/{owner}/{repo}/pulls/<PR> --jq .body` | 輸出有 `Closes #140` |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
