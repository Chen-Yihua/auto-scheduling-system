# 工作效率分析頁面：審查第 4 輪

- 規格：[docs/specs/productivity-analytics.md](../specs/productivity-analytics.md)
- PR：#10
- 日期：2026-11-03
- 審查的版本：`cb4e0b9`（第 3 輪的修正：`7d1afe1`、`3d2bb14`、`0f550c4`、`cb4e0b9`）
- 結果：**沒有阻擋項目**，可以合併

## 審查報告

> 依 `acceptance-reviewer` 的報告整理：每一項的結論、分類、阻擋判定與依據都保留，敘述有精簡。（本輪在存檔規則建立前完成，事後補檔。）

**沒有阻擋項目。** 上一輪的 3 個阻擋項目都已解決，#1 可以解除阻擋。這輪只找到 3 項非阻擋的建議。

**檢查結果**
- 後端：`pyright` 0 errors，`pytest` 499 passed。
- 前端：`npm run lint`、`npm run typecheck` 沒有錯誤；`npx vitest run` 29 個檔、265 個測試全部通過。
- 時區另外驗證兩次：shell 設 `TZ=America/Los_Angeles`（預設 forks pool）、設 `TZ=UTC` 並加 `--pool=threads`，AC18 的兩個測試檔都通過。

**修正有沒有真的解決問題**
- #1（GitHub 退回舊資料時沒有 Z）：已記錄完整，可解除阻擋。規格「不做」與修改紀錄都寫了；issue #16 寫了現象、影響範圍、建議的驗收條件和修法參考。
- #2（AC18 測試不足）：已解決。預期值改成寫死的台北時間（`2026/11/03 09:00`、跨日的 `2026/01/05 00:07`），實作改用 `getUTCHours` 會失敗。`vitest.config.ts` 設 `process.env.TZ` 在主程序載入、比 worker 建立早，forks 和 threads 都會套用；會蓋掉 shell 的 TZ，所以本機時區不同也不影響；`vitest.e2e.config.ts` 不受影響。
- #5（登出停止自動更新）：已解決。新測試先確認登入時沒有呼叫 `stopAutoRefresh`，登出後才呼叫一次；少了 `else stopAutoRefresh()` 測試會失敗。

**有沒有改到程式或規格外的內容**：4 個 commit 只改了 `docs/specs/productivity-analytics.md`、`frontend/tests/pages/productivity.test.ts`、`frontend/tests/utils/format.test.ts`、`frontend/vitest.config.ts`。

**規格、測試、PR 描述是否一致**：AC17、假設 12、修改紀錄、測試四者一致；PR 描述有幾處小地方沒對上（發現 #1、#2）。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1–AC16 | 通過 | 0d36a18 之後沒有改程式；前幾輪已確認，這輪測試全部通過 |
| AC17 | 通過 | `frontend/pages/productivity.vue:15-23`；`frontend/composables/useProductivity.ts:46,58`；`frontend/tests/pages/productivity.test.ts:147-156`；`frontend/tests/composables/useProductivity.test.ts:111-144` |
| AC18 | 通過 | `frontend/utils/format.ts`；`frontend/vitest.config.ts:5-6`；`frontend/tests/utils/format.test.ts:26-30`；`frontend/tests/pages/productivity.test.ts:193-204` |
| AC19 | 通過 | 程式沒變；`backend/tests/integration/test_jira_api.py:26-63` 檢查了舊字串讀出後輸出成 `Z` |

### 發現

| # | 分類 | 阻擋 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|
| 1 | Improvement Suggestion | 否 | PR #10 描述沒跟上：摘要少了「登出」；驗收表引用的 AC17、AC18 測試名稱是舊的。 | PR #10 body；`frontend/tests/pages/productivity.test.ts:193`；`frontend/tests/utils/format.test.ts:26`；`frontend/tests/composables/useProductivity.test.ts:111` | 更新摘要與測試名稱 |
| 2 | Improvement Suggestion | 否 | 規格實作計畫裡 `pages/productivity.vue` 那一列沒寫登出時停止自動更新。 | `docs/specs/productivity-analytics.md:97,99` | 補上 |
| 3 | Improvement Suggestion | 否 | 固定 TZ 的副作用：`useProductivity`、`useSchedule`、`useScheduleWizard` 的測試用 `Intl...resolvedOptions().timeZone` 當預期值，寫死 `'Asia/Taipei'` 的錯誤實作也會通過。以前 CI 是 UTC，寫死 `'UTC'` 一樣會通過，所以沒有比以前差。 | `frontend/tests/composables/useProductivity.test.ts:32`；`useSchedule.test.ts:51`；`useScheduleWizard.test.ts:85` | 可以不處理；要補可用 `vi.spyOn(Intl, 'DateTimeFormat')` 換成另一個時區 |

沒有 Missing Acceptance Criteria。

## 處理結果

| # | 處理 | 決定者 | commit / 連結 |
|---|---|---|---|
| 1 | 更新 PR #10 描述 | 主 session（文件同步） | PR #10 描述 |
| 2 | 規格實作計畫補上 | 主 session（文件同步） | `2024223` |
| 3 | 未處理（不阻擋，開發者未要求） | — | — |
