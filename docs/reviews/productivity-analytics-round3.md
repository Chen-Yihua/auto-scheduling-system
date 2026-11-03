# 工作效率分析頁面：審查第 3 輪

- 規格：[docs/specs/productivity-analytics.md](../specs/productivity-analytics.md)
- PR：#10
- 日期：2026-11-03
- 審查的版本：`0d36a18`（實作 AC13、AC15 修改與 AC16–AC19）
- 結果：**有阻擋**（Missing AC 1 項、Test Gap 1 項）

## 審查報告

> 依 `acceptance-reviewer` 的報告整理：每一項的結論、分類、阻擋判定與依據都保留，敘述有精簡。（本輪在存檔規則建立前完成，事後補檔。）

**有兩個阻擋項目**：#1（Missing AC：GitHub 退回舊資料時時間沒有 `Z`）、#2（Test Gap：AC18 的當地時間在 UTC 環境的 CI 驗不出錯誤寫法）。

檢查全部通過：後端 `pyright` 0 errors，`pytest` 499 passed；前端 `lint`、`typecheck` 通過，`vitest` 264 passed（29 files）。之前審過的 AC1–AC12、AC14 沒有被這次改動破壞。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC13 | 通過 | `frontend/pages/productivity.vue:49,70-74`；`frontend/tests/pages/productivity.test.ts:111,121,129` |
| AC15 | 通過 | `frontend/pages/productivity.vue:65-69`（文字相符、沒有按鈕）；`frontend/tests/pages/productivity.test.ts:146,156`；`frontend/tests/composables/useProductivity.test.ts:153` |
| AC16 | 通過 | `frontend/pages/productivity.vue:63`（watch immediate 會同步把 loading 設成 true，不會先閃一下空白）；`frontend/tests/pages/productivity.test.ts:170`；`frontend/tests/composables/useProductivity.test.ts:73` |
| AC17 | 通過 | `frontend/composables/useProductivity.ts`（`setInterval` 每小時、`onScopeDispose` 時停止、失敗不清掉 summary）；`frontend/pages/productivity.vue:16-22`；`frontend/tests/composables/useProductivity.test.ts:111,123,132,144`；`frontend/tests/pages/productivity.test.ts:139,194` |
| AC18 | 通過（測試見 #2） | `backend/services/productivity.py`、`backend/routers/analytics.py`、`backend/schemas/analytics.py:34`、`frontend/utils/format.ts`、`frontend/pages/productivity.vue:58-60`；`backend/tests/integration/test_analytics_api.py`；`frontend/tests/pages/productivity.test.ts:181` |
| AC19 | 通過（回應格式見 #1） | `backend/platforms/github.py:76-78,144`；`backend/platforms/jira.py:87-88,150`；`backend/schemas/jira.py:14-15,29-32`；`frontend/components/platforms/JiraIssuesList.vue:89`；`backend/tests/unit/test_github_platform.py:281,301`；`backend/tests/unit/test_jira_platform.py`；`frontend/tests/components/JiraIssuesList.test.ts` |

### 發現

| # | 分類 | 阻擋 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|
| 1 | Missing Acceptance Criteria | 是（開發者決定另開 issue 才解除） | 「沒有 Z」只發生在 GitHub，而且只在同步失敗、退回舊資料時。（a）同步成功：GitHub 和 Jira 都序列化成 `...Z`。（b）退回舊資料：從 Mongo 讀出的 datetime 不帶時區；Jira 有 validator 補上 UTC，`GitHubIssue` 沒有，會輸出 `2024-01-01T20:00:00`。（c）資料庫裡還沒重新同步的 GitHub 舊字串本來就帶 `Z`。（d）`/schedule/tasks` 不受影響。這是這次 commit 造成的退化：GitHub 清單的「更新於」在 +8 時區、UTC 16:00–24:00 的項目會顯示成前一天。AC19 沒規定 API 回應的時間格式，所以歸為 Missing AC。涉及資料處理（時間序列化），不涉及權限或安全性。 | `backend/schemas/github.py:15-17`；`backend/platforms/sync.py:69-78`；`backend/schemas/jira.py:29-32`；`frontend/components/platforms/GithubIssuesList.vue:101` | 建議的驗收條件（供開發者決定）：「GitHub / Jira 的 API 回應中，時間欄位一律是帶時區的 UTC（`Z`），同步成功和退回舊資料都一樣」。修法參考：`GitHubIssue` 加上和 Jira 一樣的 validator。不建議對 Mongo client 全域開 `tz_aware=True`。 |
| 2 | Test Gap | 是 | AC18 要求「瀏覽器當地時間」。`formatDateTime` 的測試先用當地時間建立 Date 再轉 ISO，在 UTC 環境分辨不出當地時間和 UTC；寫錯成 `getUTCHours()` 在 GitHub Actions（TZ=UTC）照樣會通過。頁面測試用 `formatDateTime` 自己算預期值，是循環驗證。 | `frontend/tests/utils/format.test.ts:25-29`；`frontend/tests/pages/productivity.test.ts:181` | 測試固定一個非 UTC 的時區，並寫死預期結果，例如 `'2026-11-03T01:00:00Z'` → `'2026/11/03 09:00'`。 |
| 3 | Improvement Suggestion | 否 | 規格外調整 1（`resolved_at` 改成 `Optional[datetime]`）：屬實且必要，AC19 明確要求，只是實作計畫沒寫到。 | `backend/schemas/jira.py:15` | 實作計畫補上 `resolved_at`。 |
| 4 | Improvement Suggestion | 否 | 規格外調整 2（`field_validator`）與 3（`core/datetimes.py`）：屬實且必要，在 AC19 範圍內。validator 也替 Mongo 讀出的 datetime 補上 UTC，但註解只寫了舊格式。 | `backend/schemas/jira.py:27-32`；`backend/core/datetimes.py` | validator 的註解補上「Mongo 讀出不帶時區」這個原因。 |
| 5 | Improvement Suggestion | 否 | 規格外調整 4（登出時停止自動更新）：屬實、有必要（不停的話每小時跳一次錯誤 toast），但規格只寫「離開頁面」，也沒有測試。 | `frontend/pages/productivity.vue:20-22`；`frontend/tests/pages/productivity.test.ts:22` | 請開發者確認後補進假設 12，並補測試。 |
| 6 | Test Gap | 否 | 假設 12 寫「載入失敗後等一小時才重試」，但寫成 10 秒就重試也會通過。AC15 沒禁止提早重試，所以不阻擋。 | `frontend/tests/composables/useProductivity.test.ts:153` | 失敗後先前進 `HOUR - 1`，斷言沒有再呼叫 API。 |
| 7 | Improvement Suggestion | 否 | 「測試對應」表裡 AC19 沒列 `test_jira_api.py`，AC18 沒列 `format.test.ts`。 | 規格「測試對應」 | 補上。 |
| 8 | Improvement Suggestion | 否 | 原本就有的問題：（a）退回舊資料時 `X-Synced-At` 與 `scheduling_due_date` 也不帶時區；（b）Clerk 初始化時頁面沒有載入提示；（c）`to_utc_datetime` 遇到格式錯誤的字串會丟 ValueError。 | `backend/platforms/router.py`；`backend/platforms/sync.py:69-78`；`frontend/pages/productivity.vue:49,55`；`backend/core/datetimes.py` | 視需要另開 issue。 |

## 處理結果

| # | 處理 | 決定者 | commit / 連結 |
|---|---|---|---|
| 1 | 另開 issue；規格「不做」與修改紀錄記下 | 開發者 | #16、規格 `0f550c4` |
| 2 | 交回 `feature-implementer`：測試固定 `Asia/Taipei`、預期值寫死 | 規則（阻擋的 Test Gap） | `3d2bb14` |
| 3、7 | 規格實作計畫與測試對應表補齊 | 主 session（文件同步） | `7d1afe1` |
| 4、6 | 未處理（不阻擋，開發者未要求） | — | — |
| 5 | 寫進規格（假設 12、AC17），交回 `feature-implementer` 補測試 | 開發者 | 規格 `0f550c4`、測試 `cb4e0b9` |
| 8 | （a）寫進 #16；（b）（c）未處理 | — | #16 |
