# 工作效率分析頁面：審查第 1 輪

- 規格：[docs/specs/productivity-analytics.md](../specs/productivity-analytics.md)
- PR：#10
- 日期：2026-11-03
- 審查的版本：`3ea32cb`（整個 PR，`git diff origin/main...HEAD`）
- 結果：**有阻擋**（Test Gap 4 項、Missing AC 1 項）

## 審查報告

> 依 `acceptance-reviewer` 的報告整理：每一項的結論、分類、阻擋判定與依據都保留，敘述有精簡。（本輪在存檔規則建立前完成，事後補檔。）

**結論：** 程式本身符合規格，沒有找到 Implementation Defect，檢查也全部通過。但有 4 項阻擋型 Test Gap（AC9、AC12、AC14、AC15），加上 1 項 Missing AC（載入中狀態），處理完才能合併。

**檢查結果：**
- 後端：`pyright` 0 errors；`pytest` 491 passed。
- 前端：`lint`、`typecheck` 通過；`vitest` 29 個檔案、251 passed。
- PR CI：`backend-test`、`frontend-test`、`frontend-e2e-test` 都是 pass。CI 跑 Python 3.11，所以 Jira 的 `+0800` 時區格式在 3.11 也解析得了。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | `backend/crud/manual_task.py:17`、`backend/routers/manual_task.py:91-94`、`backend/crud/schedulable_items.py:118-120`；測試：`backend/tests/unit/test_manual_task_router.py:192`、`backend/tests/unit/test_schedulable_items.py:319`、`backend/tests/integration/test_analytics_scenario.py:27` |
| AC2 | 通過 | 同上 helper，沒帶 status 時不呼叫 helper（`backend/routers/manual_task.py:91`）；測試：`backend/tests/unit/test_manual_task_router.py:201`、`backend/tests/unit/test_manual_task_crud.py:296` |
| AC3 | 通過 | `backend/crud/manual_task.py:19-20`；測試：`backend/tests/unit/test_manual_task_router.py:214`、`backend/tests/unit/test_schedulable_items.py:319`（t2 改回 False） |
| AC4 | 通過 | `backend/routers/manual_task.py:58`；測試：`backend/tests/unit/test_manual_task_router.py:223` |
| AC5 | 通過 | `backend/crud/schedulable_items.py:125-134`；測試：`backend/tests/unit/test_schedulable_items.py:347`、`:366` |
| AC6 | 通過 | `backend/platforms/github.py:142-144`、`backend/platforms/jira.py:24,148-150`、`backend/crud/schedulable_items.py:44-46`；測試：`backend/tests/unit/test_github_platform.py:270`、`backend/tests/unit/test_jira_platform.py:198,203`、`backend/tests/unit/test_schedulable_items.py:387,409` |
| AC7 | 通過 | `backend/services/productivity.py:43-94`、`backend/schemas/analytics.py`；測試：`backend/tests/unit/test_productivity.py:34,52,63,70` |
| AC8 | 通過 | `backend/services/productivity.py:24-27,44-46,68-72`；測試：`backend/tests/unit/test_productivity.py:90,98,114` |
| AC9 | 通過（測試不足，見 #1） | `backend/services/productivity.py:68-75`；測試：`backend/tests/unit/test_productivity.py:21,127` |
| AC10 | 通過 | `backend/services/productivity.py:63-66`；測試：`backend/tests/unit/test_productivity.py:143`；前端說明文字：`frontend/pages/productivity.vue:102-104` |
| AC11 | 通過 | `backend/routers/analytics.py:19-22`；測試：`backend/tests/integration/test_analytics_api.py:36,45`（401/403 已知，待開發者確認） |
| AC12 | 通過（測試不足，見 #2） | `frontend/pages/productivity.vue:67-121`；測試：`frontend/tests/pages/productivity.test.ts:64,79`、`frontend/tests/components/WeeklyBarChart.test.ts`、`frontend/tests/utils/format.test.ts` |
| AC13 | 通過 | `frontend/pages/productivity.vue:43-48,61-65,102-104`；測試：`frontend/tests/pages/productivity.test.ts:88,97,105` |
| AC14 | 通過（測試不足，見 #3） | `frontend/composables/useProductivity.ts:30-36`；測試：`frontend/tests/composables/useProductivity.test.ts:49` |
| AC15 | 通過（測試不足，見 #4） | `frontend/pages/productivity.vue:55-60`、`frontend/composables/useProductivity.ts:18`；測試：`frontend/tests/pages/productivity.test.ts:114`、`frontend/tests/composables/useProductivity.test.ts:62` |

文件同步：`docs/api.md`、`docs/architecture.md`、`frontend/types/`（`manualTask.ts`、`github.ts`、`jira.ts`、`analytics.ts`）都有跟著改，和後端 schema 一致。`SchedulableTaskOut` 沒有改。`ManualTaskUpdate` 和 `ScheduleTaskFieldsUpdate` 都沒有 `completed_at`，所以規格寫的「client 不能竄改」成立。沒有規格以外的程式改動；沒有新增必填的環境變數；`tzdata` 本來就在 `backend/requirements.txt`，部署環境不會因為少時區資料而一律回 400。

### 發現

| # | 分類 | 阻擋 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|
| 1 | Test Gap | 是 | AC9 依假設 8，準時率只算「近 8 週內」完成的項目。但準時率測試裡的項目全都在窗口內；測窗口外的那個測試沒有截止日，也沒檢查 `on_time`。把準時率的計算移到 `weekly.get` 判斷之前的錯誤實作，照樣全部通過。 | `backend/services/productivity.py:68-75`；`backend/tests/unit/test_productivity.py:114,127` | 在準時率測試加一筆窗口外有截止日的已完成項目，斷言 `completed_with_due` 沒有變多。 |
| 2 | Test Gap | 是 | AC12 要求頁面顯示長條圖和完成進度。頁面測試沒檢查 `WeeklyBarChart` 有沒有出現在頁面上，依來源／優先度也只檢查了中文標籤。拿掉 `<WeeklyBarChart>`，或進度列不顯示 done/total，測試都照樣通過。 | `frontend/pages/productivity.vue:101,112,118`；`frontend/tests/pages/productivity.test.ts:64,79` | 頁面測試補上：圖表存在，`by-source` 的文字含 `1 / 4`。 |
| 3 | Test Gap | 是 | AC14 寫明要「沿用 `getFriendlyErrorTitle`」，但測試只丟一般的 `Error`，斷言的是 fallback 文字。直接寫死 fallback 標題的錯誤實作照樣通過，429 時不會顯示「請求太頻繁，請稍後再試」。 | `frontend/composables/useProductivity.ts:33`；`frontend/tests/composables/useProductivity.test.ts:49` | 加一個 case：reject `{ status: 429 }`，斷言 toast 的 title 是限流訊息。 |
| 4 | Test Gap | 是 | AC15 明訂按鈕文字是「重試」，但測試用 `find('button')` 抓按鈕、直接點，沒驗證文字。 | `frontend/tests/pages/productivity.test.ts:128`；`frontend/pages/productivity.vue:58` | 點擊前斷言按鈕文字是「重試」。 |
| 5 | Missing Acceptance Criteria | 是（開發者決定另開 issue 才解除） | 載入中狀態沒有任何 AC 涵蓋，「不適用的情境」也沒說明原因。程式已經有載入狀態，只是規格沒定義、也沒有測試。這個狀態壞掉時畫面會一片空白，和 AC15 要防的問題一樣。建議的驗收條件（只是建議）：「還沒有統計資料、API 載入中時，頁面顯示『載入中…』，不顯示錯誤狀態或空狀態」。屬於未定義的產品行為（只是顯示），不涉及權限、安全性、資料處理。 | `frontend/pages/productivity.vue:53`；規格驗收條件表與「不適用的情境」 | 補上 AC 和頁面測試，或在「不適用的情境」寫明原因。 |
| 6 | Improvement Suggestion | 否 | 失敗時 toast 和錯誤卡片同時出現。AC14 和 AC15 各自要求了兩者，所以是照規格做的；要改就先改 AC14。 | `frontend/composables/useProductivity.ts:30-36`；`frontend/pages/productivity.vue:55` | 交給開發者決定。 |
| 7 | Improvement Suggestion | 否 | `GithubPlatform.completed_at` 和 `JiraPlatform.completed_at` 直接 `fromisoformat`，沒有接 `ValueError`。平台回一筆格式不對的時間字串，壞掉的不只統計頁，還有排程精靈 `/schedule/tasks`。目前兩個平台的格式都解析得了，風險不高。 | `backend/platforms/github.py:144`、`backend/platforms/jira.py:150`、`backend/crud/schedulable_items.py:46` | 解析失敗時回 `None` 並記 log。 |
| 8 | Improvement Suggestion | 否 | 沒帶 `timezone` 參數時預設用 `UTC`。`docs/api.md` 有寫，規格沒寫。 | `backend/routers/analytics.py:15`；`docs/api.md` | 在規格需求 2 補一句預設值。 |
| 9 | Improvement Suggestion | 否 | 測試檔開頭的說明提到別的檔案，和 CLAUDE.md「模組 docstring 不提其他檔案」不一致。 | `backend/tests/integration/test_analytics_api.py:1` | 刪掉後半句。 |

## 處理結果

| # | 處理 | 決定者 | commit / 連結 |
|---|---|---|---|
| 1–4 | 交回 `feature-implementer` 補測試 | 規則（阻擋的 Test Gap） | `c4718ab` |
| 5 | 在 PR #10 補上 AC16（載入中） | 開發者 | 規格 `58a3c76`、實作 `0d36a18` |
| 6 | 維持 toast 與錯誤卡片同時出現，不改 AC14 | 開發者 | — |
| 7 | 改成「GitHub / Jira 時間先統一格式再存資料庫」，成為 AC19 | 開發者 | 規格 `58a3c76`、實作 `0d36a18` |
| 8 | 規格需求 2 補上預設 UTC | 開發者 | `58a3c76` |
| 9 | 不改測試檔，改 CLAUDE.md 的註解規定 | 開發者 | PR #12 |
| — | 另外：開發者確認 AC11 為「未登入回 403」 | 開發者 | 規格 `a75c6ac`、測試 `6e1c70f` |
