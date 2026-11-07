# API 回應的時間沒有時區，前端顯示的時間會差 8 小時

- 狀態：已核准
- issue：[#16](https://github.com/Chen-Yihua/auto-scheduling-system/issues/16)
- PR：[#54](https://github.com/Chen-Yihua/auto-scheduling-system/pull/54)

## 背景

**現象**：使用者在 +8 時區看到的時間會差 8 小時，而且編輯手動任務時截止日會被改錯。
- GitHub 同步失敗、退回舊資料時，issue 的建立／更新／關閉時間沒有時區，UTC 16:00–24:00 的項目「更新於」顯示早一天（issue 原本描述的情境）。
- 同步失敗時的提示「資料可能非即時，上次同步：N 小時前」多算 8 小時。
- 排程頁的外部平台項目（GitHub／Jira／Moodle），以及手動任務的截止日、建立時間、更新時間、完成時間，每次從資料庫讀出都沒有時區。
- 使用者打開手動任務的編輯視窗、不改截止日直接儲存，截止日會被往前改 8 小時，每存一次就早 8 小時；排程也跟著用錯的截止日。

**重現步驟**（GitHub 退回舊資料）
1. 使用者連結 GitHub，同步一次，資料寫進資料庫。
2. GitHub 暫時連不上，再打開 GitHub 頁面，後端退回資料庫裡的舊資料。
3. 回應的 `created_at` 是 `2024-01-01T20:00:00`（沒有 `Z`），`X-Synced-At` 也沒有時區；前端 `new Date()` 當成當地時間。

**重現步驟**（編輯手動任務）
1. 在 +8 時區建立一個有截止日的手動任務。
2. 打開編輯視窗，只改標題，儲存。
3. 任務清單回的截止日是 `2030-01-09T16:00:00`（沒有時區），表單當成台北 16:00；儲存時送出 `2030-01-09T08:00:00.000Z`，資料庫裡的截止日早了 8 小時。

**預期／實際**：預期所有 API 回應的時間都是帶時區的 UTC；實際上從 MongoDB 讀出的時間不帶時區。

**原因**（已用 pymongo codec、mongomock 與 Pydantic 序列化實測）
- MongoDB 的日期型別只存 UTC，不存時區，資料庫裡的值是正確的 UTC。問題出在讀出：pymongo 的 client 沒設 `tz_aware`（預設 `False`），讀出的 datetime 不帶時區（`backend/core/database.py:7`），Pydantic 序列化時就不會補 `Z`。
- 只有 `JiraIssue` 的 `updated_at`、`resolved_at` 自己用 `to_utc_datetime` 補了時區（`backend/schemas/jira.py:29-32`），其他回應都沒有。
- 退回舊資料時，`X-Synced-At` 用資料庫讀出的 `synced_at`（`backend/platforms/sync.py:73`）直接 `isoformat()`（`backend/platforms/router.py:70-71`）。
- 建立一般任務的回應直接用記憶體裡的值（`backend/crud/manual_task.py:308-325`），本來就帶時區；其他讀資料庫的路徑都不帶。
- 編輯表單用 `new Date(task.due_date)` 當初始值（`frontend/composables/useTaskForm.ts:260`），儲存時轉成 UTC 一律送出（`:333-342`），後端寫回資料庫（`backend/routers/manual_task.py:257-270`）。

## 需求
1. 從資料庫讀出的時間一律帶 UTC 時區，所以 API 回應與 `X-Synced-At` 都帶時區。
2. 「把時間轉成帶時區的 UTC」只有一份實作（`backend/core/datetimes.py` 的 `to_utc_datetime`），各模組不再各自寫。

## 不做
- 不改資料庫裡的資料：MongoDB 存的就是 UTC，沒有時區可以存。
- 不修正已經被改錯的截止日（開發者決定）：bug 存在期間編輯過的手動任務，截止日已經早了 8 小時的倍數；資料庫沒有欄位能分辨哪些被改過、改過幾次（`updated` 每次更新都會覆寫），寫 migration 很可能把正確的資料改錯。使用者要自己重新設定。
- 不改請求 schema 與前端程式：前端送出的時間已經帶 `Z`（`frontend/composables/useTaskForm.ts:155`、`:278`、`:333`；`frontend/pages/schedule.vue:112`、`:137`、`:142`）；排程精靈會把回應的 `due_date` 原樣送回（`frontend/composables/useScheduleWizard.ts:144`），修正後回應帶時區，送回的也帶時區。
- 不在回應 schema 個別補時區：改在讀出的源頭（client）一次處理，之後新增的欄位也不會漏。Jira 既有的 `_accept_old_string_times` 保留，處理舊資料裡的字串時間。

## 假設
1. 資料庫裡所有日期都是 UTC（依據：MongoDB 日期型別只存 UTC；pymongo 寫入時把帶時區的 datetime 轉成 UTC，實測）。這只代表存的是 UTC，不代表值都正確，見「不做」第 2 點。
2. 後端程式產生的時間都帶時區（依據：`backend/` 沒有不帶時區的 `datetime.now()`、`utcnow()`；外部時間都經過 `to_utc_datetime` 或 `fromisoformat(... "+00:00")`），所以讀出的時間改成帶時區後，和程式產生的時間比較不會因為一邊有時區、一邊沒有而出錯。錯的話 Python 會丟 `TypeError`，AC6 的測試會抓到。

## 驗收條件
| # | 條件 | 類型 |
|---|---|---|
| AC1 | 照第一組重現步驟（GitHub 退回舊資料），回應的 `created_at`、`updated_at`、`closed_at` 都是帶時區的 UTC 字串，時間值和資料庫存的相同 | 使用者行為 |
| AC2 | GitHub、Jira、Moodle 的平台回應裡所有時間欄位都是帶時區的 UTC：同步成功時平台本身的時間欄位帶時區（`scheduling_due_date` 是 `null`）；退回舊資料時全部帶時區，包括 `scheduling_due_date` | 不變條件 |
| AC3 | 退回舊資料時，`X-Synced-At` header 是帶時區的 UTC | 不變條件 |
| AC4 | 手動任務的回應（`ManualTaskOut`、`ManualTaskWithSubtasksOut`）的 `due_date`、`created`、`updated`、`completed_at`，以及排程項目（`SchedulableTaskOut`）的 `due_date`，從資料庫讀出後回應時都是帶時區的 UTC，時間值和資料庫存的相同 | 不變條件 |
| AC5 | Jira 舊資料裡的字串時間（`+0800` 字串、空字串）照舊轉成 UTC 或 `null` | 不變條件（保護既有行為） |
| AC6 | 時間值的比較與排程、統計、刪除事件等結果不變：測試的資料庫也設成 `tz_aware=True` 之後，既有的後端測試全部通過 | 不變條件 |
| AC7 | 照第二組重現步驟（編輯手動任務、不改截止日直接儲存），資料庫裡的截止日不變 | 不變條件（資料一致性） |
| AC8 | 排程精靈不改截止日直接完成（把 `GET /schedule/tasks` 回應的 `due_date` 原樣送回），資料庫裡的截止日不變 | 不變條件（資料一致性） |
| AC9 | 後端「轉成帶時區的 UTC」只有 `core/datetimes.py` 的 `to_utc_datetime` 一份；`backend/` 裡沒有其他 `.replace(tzinfo=timezone.utc)`、`fromisoformat(... "+00:00")` 這類自行補時區或解析的寫法（`to_utc_datetime` 本身與轉成當地牆上時間的函式除外） | 不變條件（可維護性） |

## 不適用的情境
| 情境 | 原因 |
|---|---|
| 未登入／無權限 | 不改 endpoint 的登入與權限檢查 |
| 空資料、載入中 | 缺值照舊回 `null`；前端畫面不改 |
| 併發 | 不改寫入流程 |

## 已接受的風險
- 已經被改錯的截止日不修正（「不做」第 2 點）。
- 同步成功與退回舊資料時，平台回應的排程欄位（`done`、`priority` 等）不一致：`main` 原本就是這樣，和時區無關；這些欄位目前沒有任何呼叫端使用（前端型別沒有定義，排程頁走 `/schedule/tasks` 直接讀資料庫）。開發者決定另開 issue 處理：#53。

## 實作計畫（解決做法）
1. `backend/core/database.py`：`AsyncMongoClient(MONGO_URI, tz_aware=True)`。所有從資料庫讀出的 datetime 都帶 UTC 時區，回應序列化時自然帶時區，`X-Synced-At` 也跟著修好。
2. `backend/tests/conftest.py`：測試用的 `AsyncMongoMockClient` 也設 `tz_aware=True`，和正式環境一致（mongomock 支援，已實測）。
3. 跑全部後端測試（AC6）。如果有測試失敗，先判斷是程式還是測試的問題：程式拿資料庫的時間和不帶時區的時間比較，就修程式；測試的假資料或斷言本身假設讀出的時間不帶時區，才改測試，並在回報說明理由（CLAUDE.md「完成的定義」）。
4. Jira 的 `_accept_old_string_times` 保留（AC5），它已經用 `to_utc_datetime`。
5. 收斂各模組自己寫的補時區／解析函式，改成呼叫 `to_utc_datetime`（需求 2）。它已經處理 `None`、空字串、`Z` 與 `+0800` 字串、不帶時區（視為 UTC）、帶時區（轉成 UTC），涵蓋下列所有用途：
   - `backend/crud/manual_task.py:68-74` 的 `_as_utc`：刪掉，呼叫處改用 `to_utc_datetime`。
   - `backend/services/productivity.py:15-21` 的 `_as_utc`：同上。
   - `backend/services/scheduler.py:55-58` 的 `_parse_iso`、`:70-78` 的 `_due_as_utc`：刪掉，改用 `to_utc_datetime`；`backend/routers/schedule.py:9`、`:156` 的 import 跟著改。
   - `backend/services/scheduler.py:61-67` 的 `_sortable_due_date`：讀出的時間都帶時區後，不用再去掉時區；改成 `to_utc_datetime(due)`，沒有截止日時用帶時區的最大值，排序結果不變。
   - `backend/services/scheduler.py:81-85` 的 `_to_local_wall_time`：「不帶時區視為 UTC」那一段改用 `to_utc_datetime`，轉成當地牆上時間的部分保留（用途不同，不是重複）。
   - `backend/services/google_calendar.py:173-177` 的 `_parse_event_time`、`backend/services/google_calendar_client.py:68` 的 `fmt`：改用 `to_utc_datetime`。
   收斂是重構，不改行為，由 AC6 的既有測試保護；`to_utc_datetime` 本身的測試補齊上面每種輸入（AC9）。
6. 補 AC1～AC9 的測試。

## 測試對應
| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | `backend/tests/integration/test_github_api.py` 或平台情境測試（conftest 的 mongomock）：資料庫有舊資料、GitHub 抓取失敗，回應的三個時間字串帶時區，時間值相同 | 是 |
| AC2 | 平台情境測試：同步成功與退回舊資料兩種情況，GitHub／Jira／Moodle 的時間欄位都帶時區 | 退回舊資料：是；同步成功：否（保護既有行為） |
| AC3 | `backend/tests/unit/test_platform_sync.py`：退回舊資料時的 `synced_at` 帶 UTC 時區（或 endpoint 測試檢查 `X-Synced-At`） | 是 |
| AC4 | `backend/tests/integration/test_manual_task_scenario.py`、`test_schedule_api.py` 或新的 scenario 檔（mongomock）：建立任務後讀出，`due_date`、`created`、`updated`、`completed_at` 帶時區，時間值相同 | 是 |
| AC5 | 既有的 Jira schema 測試：`+0800` 字串、空字串 | 否（保護既有行為） |
| AC6 | 全部既有後端測試（`main` 現況 632 passed），conftest 改成 `tz_aware=True` 後仍通過 | 不適用 |
| AC7 | 後端情境測試 `backend/tests/integration/test_manual_task_scenario.py`：建立有截止日的任務 → GET `/manual-tasks/me`，`due_date` 帶時區且是同一個時間點 → 用前端送的格式（`...000Z`）PUT 只改標題 → 再讀，截止日相同。前端：`frontend/tests/composables/useTaskForm.test.ts`（`TZ='Asia/Taipei'`），收到帶 `Z` 的截止日、不改直接儲存，PUT 的 `due_date` 是同一個時間點 | 後端「GET 回應帶時區、時間值相同」那一步：是；PUT 寫回後的檢查與前端測試：否 |
| AC8 | 後端情境測試（mongomock）：GET `/schedule/tasks` → 把 `due_date` 原樣 PATCH 回去 → 資料庫裡的截止日相同 | GET 回應帶時區那一步：是；寫回後的檢查：否 |
| AC9 | `backend/tests/unit/` 的 `to_utc_datetime` 測試：`None`、空字串、`Z` 字串、`+0800` 字串、`+00:00` 字串、不帶時區、其他時區的 datetime；PR 描述附上 `grep -rn "replace(tzinfo=timezone.utc)\|fromisoformat" backend --include=*.py` 的結果，只剩 `core/datetimes.py` | grep 檢查：是（改前有 6 處）；函式測試：否（保護既有行為） |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
