# API 回應的時間沒有時區：規格審查紀錄

- 規格：[docs/specs/issue-16-utc-datetimes-in-responses.md](../../specs/issue-16-utc-datetimes-in-responses.md)
- PR：#54
- 輪數：2（第 1 輪 2026-11-07 草稿；第 2 輪 2026-11-07 草稿）
- 最終結果：第 2 輪仍有阻擋，依 `/feature` 第 1 節不再自動審查；開發者選定後核准。核准前開發者把做法改成 Mongo client `tz_aware=True`，並要求收斂各模組的補時區函式，改版後的做法沒有再經過規格審查（主要風險由 AC6 的既有測試驗證）

## 摘要

- 發現：12 項（第 1 輪 8 項、第 2 輪 4 項）：Specification Defect 6、Missing AC 1、Factual Error 3、Improvement Suggestion 2；Major 4、Minor 5、Info 3
- 開發者決策：4 項（#1、#2、#10、#12），另外核准前改了做法（見「開發者決策」）
- 尚未處理：0 項

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 編輯手動任務不改截止日，儲存後截止日早 8 小時，規格沒有 AC | Missing AC | Major | 是 | 否 | 讀出再寫回的路徑沒定義 | 新增 AC7 | 開發者 | 規格已修改 |
| 2 | 1 | 「已存資料只差讀出時沒補時區」不成立，編輯過的截止日已經改錯 | Specification Defect | Major | 是 | 否 | — | 選 A：不修已錯資料，列為已接受的風險 | 開發者 | 規格已修改 |
| 3 | 1 | AC3 的測試放在把 sync 換成假的檔案 | Specification Defect | Minor | 是 | 否 | — | 改到 `test_platform_sync.py` | 主 session（依審查建議） | 規格已修改 |
| 4 | 1 | AC5「缺值回 null」和必填欄位衝突 | Specification Defect | Minor | 是 | 否 | — | AC5 限定可為 null 的欄位；改用 `tz_aware` 後改成只保護 Jira 舊字串資料 | 主 session（依審查建議） | 規格已修改 |
| 5 | 1 | 請求 schema `ManualTaskCreate` 不存在、漏列其他請求 schema | Factual Error | Minor | 是 | 否 | — | 改正名稱並補列 | 主 session（不改變行為） | 規格已修改 |
| 6 | 1 | 假設 1 與「不做」的引用位置不精確 | Factual Error | Info | 是 | 否 | — | 改正行號與依據 | 主 session（不改變行為） | 規格已修改 |
| 7 | 1 | 「原因」裡的推論可以改成已驗證 | Improvement Suggestion | Info | 否 | 否 | — | 改成已驗證並附依據 | 主 session | 規格已修改 |
| 8 | 1 | AC2 的同步成功情況與測試對應不完整 | Improvement Suggestion | Info | 否 | 否 | — | AC2 寫明同步成功時 `scheduling_due_date` 是 `null`；測試對應補齊；排程欄位不一致的情況另開 #53 | 主 session；#53 由開發者決定 | 規格已修改；[#53](https://github.com/Chen-Yihua/auto-scheduling-system/issues/53) |
| 9 | 2 | 計畫的 `Optional[UtcDatetime]` 遇到空字串會驗證失敗 | Specification Defect | Major | 是 | 否 | — | 開發者改用 `tz_aware=True`，不再新增 schema 型別，這項不適用；Jira 既有的空字串處理保留（AC5） | 開發者（改做法） | 規格已修改 |
| 10 | 2 | AC7 的測試對應證明不了資料庫裡的截止日不變 | Specification Defect | Major | 是 | 否 | 讀出再寫回的路徑沒定義 | AC4 加「時間值相同」，補後端情境測試 | 開發者 | 規格已修改 |
| 11 | 2 | AC7「改程式前是否失敗」的寫法 | Specification Defect | Minor | 是 | 否 | — | 依實際會失敗的那一步改寫 | 主 session（依審查建議） | 規格已修改 |
| 12 | 2 | 「不做」漏了排程精靈會原樣送回 `due_date` | Factual Error | Minor | 是 | 否 | 讀出再寫回的路徑沒定義 | 補上依據；新增 AC8 | 開發者 | 規格已修改 |

## 問題說明

### #1、#10、#12 讀出再寫回的路徑

- 問題：回應的時間不帶時區，前端當成當地時間；編輯任務或排程精靈把它送回去時，資料庫裡的截止日被改早 8 小時（編輯任務已實測：API 回 `2030-01-09T16:00:00`，存回 `2030-01-09T08:00:00.000Z`）。
- 依據：`frontend/composables/useTaskForm.ts:260`、`:333-342`；`frontend/composables/useScheduleWizard.ts:144`；`backend/routers/manual_task.py:257-270`。
- 處理：AC7、AC8，以及 AC4 的「時間值相同」。

### #2 已經被改錯的資料

- 問題：bug 存在期間編輯過的手動任務，截止日已經早了 8 小時的倍數；資料庫沒有欄位能分辨哪些被改過。
- 處理：不修正，列為已接受的風險；合併後在 #16 留言提醒使用者檢查。

### #9 `Optional` 型別遇到空字串

- 問題：`Optional[Annotated[datetime, BeforeValidator(to_utc_datetime)]]` 遇到空字串會驗證失敗（500），原本的 Jira `field_validator` 會回 `null`（實測）。
- 處理：開發者改用 Mongo client `tz_aware=True`，不新增 schema 型別。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| — | 範圍 | GitHub／Jira／Moodle、X-Synced-At、手動任務與排程項目全部／只修外部平台／先實測 | 所有回應的時間一起修 | 同一個根本原因 |
| 1 | 要不要新增 AC7 | 加／不加 | 加 | 資料一致性 |
| 2 | 已經改錯的截止日 | A 不修／B 加提醒／C migration | A | 分不出哪些被改過，migration 可能改錯正確的資料 |
| 10 | AC7 的驗證方式 | 補 AC4 條件與情境測試／不補 | 補 | 錯的修法會通過原本的測試 |
| 12 | 排程精靈的原樣回送 | 加 AC8／不加 | 加 | 和 AC7 同一類風險 |
| — | 在哪裡補時區 | Mongo client `tz_aware=True`／5 個回應 schema 套型別 | `tz_aware=True` | 在讀出的源頭一次處理，之後新增的欄位也不會漏；MongoDB 本身不存時區，資料庫裡的資料不用改 |
| — | 各模組自己寫的補時區函式 | 收斂成一份／保留 | 收斂成 `core/datetimes.py` 的 `to_utc_datetime`（AC9） | 不要各自寫 |
| 8 | 平台 API 回應帶著沒使用的排程欄位 | 另開 issue／不處理 | 另開 #53 | 和時區無關 |

## 尚未處理

無。

## 查證紀錄（第 2 輪）

| 規格中的事實 | 結果 | 依據（檔案:行號） |
|---|---|---|
| Mongo client 沒有設 `tz_aware`，讀出不帶時區 | 正確 | `backend/core/database.py:7`；mongomock 實測 |
| 只有 `JiraIssue.updated_at`／`resolved_at` 用 `to_utc_datetime` | 正確 | `backend/schemas/jira.py:14-15`、`:29-32` |
| 平台 endpoint 用 schema 序列化 | 正確 | `backend/platforms/router.py:101` |
| 退回舊資料時用資料庫的 `synced_at`、直接 `isoformat()` | 正確 | `backend/platforms/sync.py:73`、`:78`；`backend/platforms/router.py:70-71` |
| 同步成功時的 `synced_at` 帶時區；快取命中時也帶時區 | 正確 | `backend/platforms/sync.py:83`、`:99`；`backend/platforms/router.py:29-35`、`:74-79` |
| 建立一般任務的回應用記憶體裡的值 | 正確 | `backend/crud/manual_task.py:302-325` |
| 編輯表單的初始值與送出；PUT 寫回資料庫 | 正確 | `frontend/composables/useTaskForm.ts:260`、`:333-342`；`backend/routers/manual_task.py:257-270` |
| 排程精靈原樣送回 `due_date` | 正確 | `frontend/composables/useScheduleWizard.ts:124-127`、`:141-150` |
| `updated` 每次更新都會覆寫 | 正確 | `backend/routers/manual_task.py:262-263` |
| 資料庫的日期都是 UTC；backend 沒有不帶時區的 `datetime.now()`、`utcnow()` | 正確 | `backend/core/datetimes.py:19`；mongomock 實測；grep |
| mongomock 支援 `tz_aware=True` | 正確（主 session 實測，核准前補查） | `mongomock.MongoClient(tz_aware=True)` 讀回帶 UTC 的 datetime |
| `main` 現況 632 passed | 正確 | 第 2 輪 `pytest` |
| 前端測試在非 UTC 時區執行 | 正確 | `frontend/vitest.config.ts:6` |
| 其他回應時間欄位不是從資料庫讀出 | 正確 | `backend/schemas/schedule.py:12-13`；`backend/schemas/analytics.py:34` |

## 已接受的風險

- 已經被改錯的截止日不修正。
- 同步成功與退回舊資料時，平台回應的排程欄位不一致（另開 #53）。
- 改用 `tz_aware=True` 之後的做法沒有經過規格審查；比較時間的程式若有遺漏，會以 `TypeError` 讓測試失敗，由 AC6 驗證。
