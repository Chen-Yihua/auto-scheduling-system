# 開發流程升級（/issue-triage、/issue）：審查第 2 輪

- 規格：本次為流程文件改動，沒有 `docs/specs/` 規格檔；驗收條件 AC1–AC8 見 PR #18 描述
- PR：#18
- 日期：2026-11-04
- 審查的版本：`290029f`（`git diff 9b3f076..HEAD`：`c1d1b84`、`52e1096`、`290029f`）
- 結果：**有阻擋**（AC8 之外：Missing AC 2、Implementation Defect 1）

## 審查報告

> `acceptance-reviewer` 的報告原文，只調整了標題層級。報告提到的安全問題是這個 PR 的流程文件本身的缺漏，不是程式漏洞，所以不適用「安全發現開 private advisory」的改寫規則。

審查範圍：`git diff 9b3f076..HEAD`（commit `c1d1b84`、`52e1096`、`290029f`）。驗收條件 AC1–AC8 以 `/root/.claude/plans/binary-roaming-charm.md` 與 PR #18 描述為準。

**結論：除了 AC8（settings）以外，還有 3 項阻擋：發現 #1、#2、#3。** 三項都跟第 1 輪 #3（安全發現改開 private advisory）的落實有關。第 1 輪其他項目都已解決。

查證時只跑了唯讀指令：
- `gh api repos/{owner}/{repo}/security-advisories --jq ...`：exit 0，目前沒有 advisory。
- `gh repo view --json visibility,viewerPermission`：結果是 PUBLIC / ADMIN。
- `gh auth status`：token scopes 有 `repo`。
- `gh help api`：確認 `--input` 可以讀檔案，也可以用 `-` 讀 stdin。
- `gh pr view 18 --json body`。

沒有建立任何 advisory，也沒有改 issue。

### private advisory 的 API 欄位

照 GitHub REST API「Create a repository security advisory」對照 `.claude/skills/feature/SKILL.md:67-75`：
- 必填的 `summary`、`description`、`vulnerabilities` 都有寫。
- `vulnerabilities[].package.ecosystem` 是必填，`other` 在允許的值裡。`name` 可以不填，有寫也沒問題。
- `severity` 可用的值是 low / medium / high / critical，不能和 `cvss_vector_string` 同時給，文件沒有同時給。
- 建立的權限是 repo 管理者或 security manager。目前帳號是 ADMIN，token 有 `repo` scope，權限應該夠。
- 列出 advisory 的 GET 實測可用。

結論是照文件應該能執行。POST 沒有實際送出，所以「建立成功」這一步無法實測確認。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | `.claude/skills/issue-triage/SKILL.md:15`：改成 `--json`，和第 1 輪 #1 一樣的寫法實測可用；`:18` 寫明一定要加 `--json`；`:34` 確認前不改任何東西；`CLAUDE.md:28` 補上 `view` 要加 `--json` |
| AC2 | 通過（只看文件） | `.claude/skills/issue-triage/SKILL.md:38-44`；新增的第 4 步 `:44` 會檢查每個 issue 剛好有一個 `priority:*`。寫入指令沒有執行 |
| AC3 | 通過 | `.claude/skills/issue/SKILL.md:14`（參數解析）、`:17`、`:30-34`；`docs/specs/README.md:13`（完整格式加了 issue 欄位）。`Closes #N` 的確認時機見發現 #4 |
| AC4 | 通過 | `docs/specs/README.md:51-92`；`.claude/skills/feature/SKILL.md:22`；`.claude/agents/acceptance-reviewer.md:11` |
| AC5 | 通過（只看文件） | `.claude/skills/feature/SKILL.md:41`、`:54-60`；`:58` 改成附檔案路徑，不用分支上的連結。AC5 的文字還沒反映 advisory 這條分流，見發現 #1 |
| AC6 | 通過 | `.claude/skills/feature/SKILL.md:39`、`:42`、`:45`、`:47-52`；`docs/decisions/0003-issue-workflow.md:16` |
| AC7 | 通過 | `.claude/skills/feature/SKILL.md:38`、`:40` |
| AC8 | 不通過 | `.claude/settings.json:11-15` 仍然沒有 `Bash(gh api *merge*)`。附帶一點：`docs/decisions/0003-issue-workflow.md:26` 用現在式寫「合併由 deny 規則（`gh pr merge`、`gh api *merge*`）擋下」，settings 改好之前這句不成立 |

### 第 1 輪各項的處理確認

| 第 1 輪 # | 是否解決 | 依據 |
|---|---|---|
| 1 | 已解決 | `issue-triage/SKILL.md:15`、`:18`；`CLAUDE.md:28` |
| 2 | 未解決（AC8，等開發者手動修改） | `.claude/settings.json:11-15` |
| 3 | 部分解決，見發現 #1–#3 | `feature/SKILL.md:42`、`:62-78` |
| 4 | 已解決；三處的說法一致，只有細節可以補，見發現 #5 | `feature/SKILL.md:22`；`acceptance-reviewer.md:11`；`docs/specs/README.md:51-92` |
| 5 | 已解決 | `issue/SKILL.md:5`、`:10`、`:14`、`:17` |
| 6 | 已解決，確認時機見發現 #4 | `issue/SKILL.md:34`；`docs/specs/README.md:13` |
| 7 | 已解決 | `docs/decisions/0003-issue-workflow.md:23` 與 `issue-triage/SKILL.md:30` 一致 |
| 8 | 已解決 | `feature/SKILL.md:58` |
| 9 | 已解決 | `issue-triage/SKILL.md:44` |
| 10 | 已解決 | PR #18 描述「計畫外的補充」段 |

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Missing Acceptance Criteria | 是 | 安全 | 第 1 輪 #3 由開發者決定「在這個 PR 補」，但驗收條件沒有跟著更新。計畫檔和 PR #18 的驗收表仍是 AC1–AC8，AC5 還寫著「不阻擋的發現一律自動開 issue」，和新增的 advisory 分流（`feature/SKILL.md:42`）衝突，也沒有任何一條 AC 驗證這個分流。照 `/feature` 自己的規則，確認後的驗收條件要寫進規格並記修改紀錄，這次沒有做。影響範圍：之後再審查時，沒有 AC 可以判斷 advisory 流程對不對；只看 AC5 的人會以為安全發現也開公開 issue | `.claude/skills/feature/SKILL.md:51`；`.claude/agents/acceptance-reviewer.md:12`；PR #18 描述的驗收表 AC5；`/root/.claude/plans/binary-roaming-charm.md` 的驗收條件表 | 建議（尚待開發者確認）：AC5 加上「『涉及安全／架構』為『安全』的除外」；新增 AC9：「不阻擋的發現涉及安全時，主 session 先查重複再建立 draft private security advisory，不開公開 issue；審查紀錄與 PR 描述只寫 advisory 編號；建立失敗時停下來問開發者」。在 PR 描述記下修改紀錄（日期、修改、原因、確認者）。產品行為已經由開發者決定，這裡只是規格同步，沒有新的未定義行為 |
| 2 | Implementation Defect | 是 | 安全 | 改寫範圍不夠完整，而且和「原文照貼」的規則互相矛盾。`feature/SKILL.md:76` 只要求把發現表裡那一項的「說明」「依據」「建議」改寫，但 reviewer 報告的其他地方也可能寫到漏洞位置，例如驗收條件表的「依據」欄（像「AC3 通過，但 X 檔第 N 行沒做權限檢查」）、Missing AC 的補充段落、「執行過的查證」「其他檢查結果」段落。另外有三處規定要原文照貼，都沒有提到這個例外：`docs/reviews/README.md:5`（「報告原文照貼」）、`:20`、`feature/SKILL.md:80`（「把報告原文存成」），以及 reviewer 定義 `acceptance-reviewer.md:19`。照 `docs/reviews/README.md` 存檔的人會把細節原文貼進公開 repo。開發者第 1 輪的決定是審查紀錄不留細節，目前只做到一部分 | `.claude/skills/feature/SKILL.md:76`、`:80`；`docs/reviews/README.md:5`、`:20`；`.claude/agents/acceptance-reviewer.md:19` | 把 `:76` 改成「存檔前檢查整份報告（包括驗收條件表、補充段落），所有提到這個安全問題位置或利用方式的地方都改寫成 advisory 編號」。`docs/reviews/README.md:5` 和 `feature/SKILL.md:80` 的「原文」加上例外：「涉及安全的內容照『安全發現開 private advisory』改寫」。也可以考慮在 reviewer 定義寫明「涉及安全的項目，主 session 存檔前會改寫」，讓 reviewer 知道報告不會被原樣公開 |
| 3 | Missing Acceptance Criteria | 是 | 安全 | 缺漏的情境：不走「不阻擋」路徑的安全內容，目前沒有規定能不能公開，但 `feature/SKILL.md:64` 的總則寫成全部都不能出現在 issue、PR 描述、commit、`docs/reviews/`，兩邊對不起來。一共三種情況。(a) 涉及安全的 Missing AC，開發者選「另開 issue」時，`:52` 規定用 `gh issue create`，會開成公開 issue，例如「既有的 endpoint 缺少權限檢查的 AC」。(b) 涉及安全的 Implementation Defect，開發者決定在這個 PR 修時，審查紀錄的原文（`:80`）、implementer 寫的 commit 訊息和 PR 描述會寫到漏洞位置；如果漏洞在 main 已經有的程式裡，修好之前就公開了。(c) implementer 修正時寫的 commit 訊息，沒有任何文件提醒它不能寫細節（`feature-implementer.md:10`）。影響範圍：`/feature` 和 `/issue` 的暫停處理與修正流程 | `.claude/skills/feature/SKILL.md:39`、`:52`、`:64`、`:76-80`；`.claude/agents/feature-implementer.md:10` | 建議（尚待開發者確認，涉及安全性與資料處理，選項由開發者決定）：選項 A：`:64` 的總則適用到所有涉及安全的項目，(a) 另開時改開 advisory，(b)(c) 在 commit、PR 描述、審查紀錄都只寫 advisory 或一般性的描述。選項 B：限定範圍，只有「漏洞存在於 main 已有的程式」才保密，只在這個 PR 新增、還沒合併的程式可以公開討論。並把 `:64` 改成和選定範圍一致的寫法 |
| 4 | Improvement Suggestion | 否 | 否 | `/issue` 規定「第 4 節回報前」確認 PR 描述有 `Closes #N`，但 `/feature` 第 4 節本身就會更新 PR 描述，放進驗收表（`feature/SKILL.md:93`）。如果確認做在更新之前，更新時整份描述被覆寫，`Closes #N` 可能被拿掉，合併後 issue 不會自動關閉。另外 `gh api -X PATCH ... -F body=@<檔案>` 會取代整份描述，補上時要以原本的描述為基礎 | `.claude/skills/issue/SKILL.md:34`；`.claude/skills/feature/SKILL.md:93`；`CLAUDE.md:28` | 改成「每次更新 PR 描述後（包括第 4 節），用 `gh api repos/{owner}/{repo}/pulls/<PR> --jq .body` 確認有 `Closes #<N>`；補上時保留原本的描述內容」 |
| 5 | Improvement Suggestion | 否 | 否 | bug 簡化格式的豁免範圍：`/feature` 第 1 節和 reviewer 第 3 項的說法一致。但有兩個小落差。(1) `docs/specs/README.md` 的 bug 格式段落沒有寫出豁免，只是格式裡少了那幾段；只讀這份文件的人不知道這是刻意省略的。`/feature:22` 另外豁免「假設」「實作計畫」，reviewer 沒有提到這兩項，雖然 reviewer 本來也不檢查這兩項。(2) reviewer 要檢查「回歸測試是否在改程式前就會失敗」，但 reviewer 只能讀、不能切換分支，實際上只能看規格「回歸測試」表的「改程式前是否失敗」欄，或 implementer 的回報 | `docs/specs/README.md:51-53`、`:83-85`；`.claude/skills/feature/SKILL.md:22`；`.claude/agents/acceptance-reviewer.md:11`、`:15` | `docs/specs/README.md:53` 加一句「不用寫假設、不適用的情境、實作計畫（見 `/feature` 第 1 節）」；reviewer 第 3 項改成「回歸測試表的『改程式前是否失敗』欄有填，而且測試內容確實會重現 bug」 |
| 6 | Improvement Suggestion | 否 | 否 | 分類表裡，一項「不阻擋、涉及安全」的 Improvement Suggestion 同時符合第 41 列（開 issue）和第 42 列（開 advisory），沒有寫哪一列優先，只能靠讀者推斷。implementer 回報的處理寫在 `:30`，只指向「開 issue」，安全的例外要讀到 `:77` 才看得到 | `.claude/skills/feature/SKILL.md:30`、`:41-42`、`:77` | 第 41 列加「（不涉及安全）」，和第 38/39 列的寫法一致；`:30` 補上「涉及安全的照『安全發現開 private advisory』」 |

阻擋項目總結：除了 AC8（settings）以外，發現 #1（Missing AC）、#2（Implementation Defect，涉及安全）、#3（Missing AC，涉及安全）是阻擋項目。照 `/feature` 的規則：#2 涉及安全，要暫停問開發者，不能自動交回修正；#3 牽涉安全性與資料處理，要由開發者選擇範圍。#4–#6 不阻擋。

## 處理結果

| # | 處理 | 決定者 | commit / 連結 |
|---|---|---|---|
| 1 | AC5 排除涉及安全的發現；新增 AC9（private advisory）；PR 描述記下修改紀錄 | 開發者（照建議） | PR #18 描述、見下一個 commit |
| 2 | 存檔前檢查整份報告，所有安全細節改寫成 advisory 編號；「原文照貼」加上這個唯一例外（`/feature`、`docs/reviews/README.md`、reviewer 定義） | 開發者（選「存檔前檢查整份報告」） | 見下一個 commit |
| 3 | 保密範圍選 A：所有涉及安全的項目都不公開細節；Missing AC 另開改開 advisory；implementer 的 commit、PR 描述、註解只寫一般性描述；新增 AC10 | 開發者（選 A） | 見下一個 commit |
| 4–6 | 在本 PR 直接修：每次更新 PR 描述後確認 `Closes #N` 並保留原描述；bug 豁免寫進規格格式文件與 reviewer；分類表標明「不涉及安全／涉及安全」 | 開發者（選「在這個 PR 直接修」） | 見下一個 commit |
| AC8 | 開發者已手動加上 allow 規則，deny `Bash(gh api *merge*)` 尚未加 | 開發者 | 待處理 |
