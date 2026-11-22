# 排程精靈記住上次填的排程偏好

- 狀態：已核准
- 等級：一般（新增兩支 endpoint，偏好存在 `users` 文件的新選填欄位，舊文件沒有這個欄位也照常讀得出來；偏好只是使用者自己的排程設定，不是憑證或個資；不改其他資料的一致性、登入或授權的保證）
- issue：#182
- PR：#183

## 簡短說明

使用者在排程精靈第 2 步填的「排程偏好設定」，按「完成」並成功產生排程建議後，系統把這份偏好存到使用者的帳號上。下次打開排程頁時，第 2 步自動顯示上次存的設定。

## 背景

來源：[#182](https://github.com/Chen-Yihua/auto-scheduling-system/issues/182)

使用者每次打開排程頁，第 2 步「排程偏好設定」都是空白，要重新填一次每週固定的不工作時段、一次性不工作時段、任務間緩衝時間、每日上限。忘了填的話，任務就會被排進不能工作的時間。

這是原本刻意的設計：

- `frontend/composables/useScheduleWizard.ts:37`：`preferences` 的註解寫「每次執行精靈都重新填，不存進資料庫」。
- `frontend/composables/useScheduleWizard.ts:81`：`initWizard` 每次都把 `preferences` 重設成 `defaultSchedulePreferences()`。
- `backend/schemas/schedule.py:154`：`SchedulePreferences` 的 docstring 寫「不存進資料庫，只影響這一次的計算」。
- `frontend/types/schedule.ts:80`：`SchedulePreferences` 上面的註解寫「不存資料庫，每次請求都要帶」。
- `frontend/composables/useSchedule.ts:27`：`lastPreferences` 的註解寫「preferences 不存資料庫」。
- 偏好只在 `POST /schedule/suggest` 的 request body 送給後端（`frontend/composables/useSchedule.ts:30-42` 的 `fetchScheduleSuggestion`）。

精靈回到第 1 步（呼叫 `initWizard`）的情況有 3 種，都在 `frontend/pages/schedule.vue`：

1. 打開排程頁（`initPage`，`:45-60`）。
2. 處理完或取消「已刪除的事件」這一步（`enterWizardAfterRemovedStep`，`:117-122`）。
3. 第 3 步按「重新產生」（`regenerate`，`:222-225`；按鈕在 `frontend/components/tasks/ScheduleSuggestion.vue:42-50`）。第 3 步任何時候都能按，產生建議失敗時也能按。

確認排程後、建議過期時，`frontend/composables/useSchedule.ts:108`、`:118` 會用 `lastPreferences` 自動再算一次建議，不回到第 1 步。

`users` collection 的文件目前只有 `_id`（Clerk user id）、`email`、`name`（`backend/crud/user.py:7-19`）。刪除帳號時會刪掉整份 `users` 文件（`backend/crud/user.py:50`）。`GET /users/me` 的回應用 `UserOut`，只回 `id`、`email`、`name`（`backend/schemas/user.py:9-12`）。

`fetchScheduleSuggestion` 失敗時不丟例外，只清空結果、跳 toast（`frontend/composables/useSchedule.ts:46-65`）。`handleFinish`（`frontend/pages/schedule.vue:214-219`）不管成功或失敗，都會進到第 3 步。

`BlockedRecurringRule`（`backend/schemas/schedule.py:136-144`）的 `days_of_week` 是不限長度的數字清單，`start_time`、`end_time` 是不限長度的字串；`SchedulePreferences` 的兩個清單也沒有長度上限。第 2 步的時間欄位是 `<input type="time">`（`frontend/pages/schedule.vue:501`、`:503`），送出的格式是 `HH:MM`。

## 需求

1. 系統記住的偏好有 4 種：每週固定不工作時段（`blocked_recurring`）、一次性例外（`blocked_exceptions`）、任務間緩衝時間（`buffer_minutes`）、每日上限（`daily_max_minutes`）。
2. 系統不記住時區。每次排程都用瀏覽器當時的時區。
3. 偏好存在使用者的 `users` 文件上，同一個帳號在不同裝置、不同瀏覽器都讀到同一份。
4. 使用者在第 2 步按「完成」，而且系統成功產生排程建議時，系統才存這次的偏好。
5. 系統存的內容和這次送去產生排程建議的內容一樣：只有填完整的時段（`sanitizedPreferences` 濾過的結果），不含時區。
6. 使用者在第 2 步改了設定、沒有按「完成」就離開，系統不存這些修改。
7. 產生排程建議失敗時，系統不存這次的偏好。
8. 打開排程頁時，系統把存的偏好帶進第 2 步。
9. 系統帶入偏好時，拿掉結束時間已經過去的一次性例外。每週規律的時段一律保留。
10. 使用者從來沒有存過偏好時，第 2 步顯示原本的空白預設值。
11. 同一次打開排程頁的期間，精靈回到第 1 步（處理完或取消「已刪除的事件」、第 3 步按「重新產生」）時，第 2 步保留使用者目前在畫面上填的內容，不管有沒有存成。
12. 存偏好失敗時，第 3 步照常顯示排程建議。
13. 存偏好失敗時，系統另外跳一個提示：「排程偏好沒有存成功，下次要重新填」。
14. 打開排程頁時讀取偏好失敗，第 2 步顯示空白預設值。
15. 打開排程頁時讀取偏好失敗，系統另外跳一個提示：「讀不到上次的排程偏好，請重新填寫」。
16. 刪除帳號時，偏好跟著 `users` 文件一起刪除。
17. 使用者只讀得到、改得到自己的偏好。
18. 儲存偏好時，每週規律、一次性例外各最多 50 條。
19. 儲存偏好時，每條每週規律的 `days_of_week` 最多 7 個，每個是 0 到 6 的整數。
20. 儲存偏好時，`start_time`、`end_time` 是 `null` 或 `HH:MM` 格式（00:00 到 23:59）；空字串不合法。
21. 儲存偏好的內容不符合需求 18–20 時，系統回 422，不寫入。
22. 第 2 步一次性例外的標題從「這次額外不排的時段」改成「額外不排的時段（過了就自動移除）」。
23. 沒有一次性例外時的提示從「沒有這次額外的例外時段」改成「沒有額外的例外時段」。
24. 使用者勾選「整天」時，這條每週規律的兩個時間輸入框維持顯示、不能編輯，起訖時間自動變成 `00:00`、`23:59`。
25. 使用者取消勾選「整天」時，兩個時間輸入框變回可以編輯，起訖時間清空（畫面顯示 `--:--`）。
26. 勾了「整天」的每週規律，系統送出（產生排程建議與儲存偏好）時，起訖時間一律是 `"00:00"`、`"23:59"`，不管規律裡原本存的是什麼（例如舊資料）。排程計算照舊依 `all_day` 擋掉整天（`backend/services/scheduler.py:98-100`），所以排程結果不變。

## 不做

- 不記住時區（需求 2）。
- 不保留過去每一次的偏好紀錄，只留最近一次。
- 不加另外的「儲存」按鈕。
- 不處理兩個分頁同時按「完成」的情況：最後存的那次為準。偏好只影響使用者自己的下一次排程，不會讓資料前後不一致。
- 使用者在另一個分頁改了偏好，這個分頁要重新整理才看得到：偏好只在打開排程頁時讀一次（需求 8）。
- 確認排程後、建議過期時自動重新產生的建議，不另外存偏好：用的是剛送出、已經存過的同一份偏好。
- 不改 `POST /schedule/suggest` 的 request 格式、驗證與計算方式：需求 18–21 的上限只加在儲存偏好的 endpoint；需求 26 只改前端送出的值，排程結果不變。
- 不另外處理「讀取偏好失敗後，使用者填了一部分就按『完成』，存成功時蓋掉之前存的完整偏好」：這是需求 14、15 的直接結果，提示已經請使用者重新填寫。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 使用者在第 2 步填好 4 種偏好、按「完成」、成功產生排程建議後，重新打開排程頁，第 2 步顯示上次填的每週規律、一次性例外、緩衝時間、每日上限 |
| AC2 | 同一個帳號在另一個瀏覽器打開排程頁，第 2 步顯示 AC1 存的同一份偏好 |
| AC3 | 使用者從來沒有存過偏好時，打開排程頁，第 2 步顯示空白預設值（沒有時段、緩衝 0、沒有每日上限） |
| AC4 | 第 2 步有一條沒填完的每週規律（沒選星期），使用者按「完成」並成功產生排程建議，系統存的偏好不含這一條 |
| AC5 | 系統存偏好時，送出的內容不含時區 |
| AC6 | 系統帶入偏好時，時區是瀏覽器當時的時區 |
| AC7 | 使用者改了第 2 步的設定，沒有按「完成」，系統不送出儲存偏好的請求 |
| AC8 | 產生排程建議失敗時（例如後端回 500），系統不送出儲存偏好的請求 |
| AC9 | 存的偏好裡有一條已經結束的一次性例外、一條還沒結束的一次性例外、一條每週規律，使用者打開排程頁，第 2 步只顯示還沒結束的那條一次性例外和那條每週規律 |
| AC10 | 使用者按「完成」並成功存了偏好後，在第 3 步按「重新產生」，走到第 2 步時顯示剛才填的偏好，系統不再向後端讀取偏好 |
| AC11 | 使用者在第 2 步改了設定、按「完成」，產生排程建議失敗，在第 3 步按「重新產生」，走到第 2 步時顯示剛才改過的內容 |
| AC12 | 打開排程頁時有「已刪除的事件」，使用者處理完這一步，進入精靈第 2 步時，顯示打開頁面時讀到的偏好 |
| AC13 | 存偏好失敗時，第 3 步照常顯示排程建議 |
| AC14 | 存偏好失敗時，畫面跳出提示「排程偏好沒有存成功，下次要重新填」 |
| AC15 | 打開排程頁時讀取偏好失敗，第 2 步顯示空白預設值 |
| AC16 | 打開排程頁時讀取偏好失敗，畫面跳出提示「讀不到上次的排程偏好，請重新填寫」 |
| AC17 | 沒登入時打讀取和儲存偏好的 endpoint，都回 401，資料庫不變 |
| AC18 | 使用者 A 存偏好後，使用者 B 讀到的是 B 自己的偏好（沒存過就是空白預設值），A 的偏好不變 |
| AC19 | 儲存偏好時內容的型別不對（例如 `buffer_minutes` 是 `"abc"`），系統回 422，資料庫裡原本的偏好不變 |
| AC20 | 儲存偏好時每週規律有 51 條，系統回 422，資料庫裡原本的偏好不變 |
| AC21 | 儲存偏好時一次性例外有 51 條，系統回 422，資料庫裡原本的偏好不變 |
| AC22 | 儲存偏好時某條每週規律的 `days_of_week` 有 8 個，或含有 7，系統回 422，資料庫裡原本的偏好不變 |
| AC23 | 儲存偏好時 `start_time` 是 `"24:00"`、`"9:00"` 或 `"abc"`，系統回 422，資料庫裡原本的偏好不變 |
| AC24 | 儲存偏好時每週規律、一次性例外各 50 條，`days_of_week` 是 `[0,1,2,3,4,5,6]`，`start_time` 是 `"00:00"`、`end_time` 是 `"23:59"`，系統存成功 |
| AC25 | `POST /schedule/suggest` 收到 51 條每週規律時，照舊產生建議，不回 422 |
| AC26 | 刪除帳號後，資料庫裡找不到這個使用者的偏好 |
| AC27 | 存了偏好之後，`GET /users/me` 的回應仍然只有 `id`、`email`、`name` |
| AC28 | 第 2 步一次性例外的標題是「額外不排的時段（過了就自動移除）」 |
| AC29 | 沒有一次性例外時，第 2 步顯示「沒有額外的例外時段」 |
| AC30 | 一條每週規律選了星期、開始時間填了又清掉（空字串）、勾了「整天」，使用者按「完成」並成功產生排程建議後，系統存偏好成功，存的這條規律是 `start_time: "00:00"`、`end_time: "23:59"` |
| AC31 | 使用者勾選「整天」，這條規律的兩個時間輸入框顯示 `00:00`、`23:59`，而且不能編輯 |
| AC32 | 使用者取消勾選「整天」，這條規律的兩個時間輸入框變成空白、可以編輯 |
| AC33 | 存的偏好裡有一條勾了「整天」的規律，使用者打開排程頁後取消勾選，兩個時間輸入框變成空白 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中 | 讀取偏好和打開頁面時原本的查詢一起做，頁面原本就有「checking」狀態（`frontend/pages/schedule.vue:33-34`），讀完才顯示精靈，不另外加載入畫面 |
| 同時操作 | 兩個分頁同時存偏好，以最後一次為準（見「不做」）；偏好不和其他資料連動，不會不一致 |
| 新功能和既有規則交會 | 排程計算照舊只看 `POST /schedule/suggest` 送來的偏好（見「不做」，AC25），既有的不工作時段、緩衝、每日上限規則不變 |

## 實作計畫

### 後端

1. `backend/schemas/schedule.py`：
   - 新增 `SavedBlockedRecurringRule`：繼承 `BlockedRecurringRule`，加上需求 19、20 的驗證（`days_of_week` 最多 7 個、每個 0–6；`start_time`、`end_time` 是 `None` 或符合 `HH:MM`、00:00–23:59）。
   - 新增 `SavedSchedulePreferences`：欄位是 `blocked_recurring: list[SavedBlockedRecurringRule]`、`blocked_exceptions: list[BlockedException]`（兩個清單都 `max_length=50`）、`buffer_minutes`、`daily_max_minutes`，預設值和 `SchedulePreferences` 相同，沒有 `timezone`。
   - `SchedulePreferences` 不加上限（AC25），只改 docstring，拿掉「不存進資料庫」。
   - 兩個 model 分開寫，不用繼承讓 `SchedulePreferences` 得到上限：`POST /schedule/suggest` 的驗證不改。
2. `backend/crud/user.py`：新增兩個函式。
   - 讀取：回傳 `users` 文件的 `schedule_preferences` 欄位；欄位不存在時回傳預設值；使用者不存在時丟 `NotFoundError`。
   - 儲存：用 `$set` 整份換掉 `schedule_preferences`（只留最近一次）；`matched_count == 0` 時丟 `NotFoundError`。`blocked_exceptions` 的時間照 `model_dump()` 存成 datetime。
3. `backend/routers/user.py`：新增兩支 endpoint，都要登入，只用 JWT 的 `sub` 找使用者（需求 17）。
   - `GET /users/me/schedule-preferences` → `SavedSchedulePreferences`。
   - `PUT /users/me/schedule-preferences`，body 是 `SavedSchedulePreferences` → 200，不回內容。
4. 不改 `UserOut`、`UserUpdate`：`PUT /users/me` 不會碰到偏好，`GET /users/me` 也不會回傳偏好（AC27）。
5. 不用改刪除帳號：`delete_user_by_clerk_id` 刪整份 `users` 文件，偏好一起刪除（AC26）。

不另外開 collection，原因：偏好是一個使用者一份、資料很小、總是和使用者一起讀，MongoDB 建議一對一的小資料直接放在本人的文件裡；放在 `users` 上，刪除帳號也不用多寫。新增選填欄位不算重大架構決策（`/feature`「重大架構決策」）。

### 前端

1. `frontend/types/schedule.ts`：新增 `SavedSchedulePreferences`（對應後端），`SchedulePreferences` 改成它加上 `timezone`。改掉「不存資料庫」的註解。
2. `frontend/composables/useScheduleWizard.ts`：
   - 新增讀取函式：呼叫 `GET /users/me/schedule-preferences`。成功時把回傳的內容加上瀏覽器時區、拿掉結束時間已過的一次性例外（需求 9），設成 `preferences`。失敗時把 `preferences` 設成空白預設值，跳需求 15 的提示。
   - `initWizard` 不再重設 `preferences`（需求 11）。
   - 新增切換「整天」的函式：勾選時把這條規律的 `start_time`、`end_time` 設成 `"00:00"`、`"23:59"`；取消勾選時設成 `null`（需求 24、25）。
   - `sanitizedPreferences` 對勾了「整天」的每週規律，回傳 `start_time`、`end_time` 是 `"00:00"`、`"23:59"` 的新物件，不改畫面上的規律物件（需求 26、需求 11）；產生排程建議和儲存偏好都用它，所以兩邊送出的內容一樣（需求 5）。
   - 新增儲存函式：用 `sanitizedPreferences` 去掉 `timezone` 後呼叫 `PUT`；失敗時跳需求 13 的提示，不丟例外。
   - 改掉 `preferences` 上「不存進資料庫」的註解。
3. `frontend/composables/useSchedule.ts`：
   - `fetchScheduleSuggestion` 改成回傳是否成功，讓呼叫的地方知道要不要存偏好。其他呼叫的地方不用改。
   - 改掉 `lastPreferences` 上「preferences 不存資料庫」的註解。
4. `frontend/pages/schedule.vue`：
   - `initPage` 讀任務時一起讀偏好（只在這裡讀，需求 8）。
   - `handleFinish` 在 `fetchScheduleSuggestion` 成功後才存偏好（需求 4、7）；存偏好失敗不擋住第 3 步（需求 12）。
   - 需求 22、23 的兩段文字（`:511`、`:515`）。
   - 每週規律的時間輸入框（`:500-504`）拿掉 `v-if="!rule.all_day"`，改成勾了「整天」時 `disabled`；「整天」勾選框改呼叫切換「整天」的函式（需求 24、25）。

### 文件

1. `docs/api.md`：在 users 那張表加上兩支新 endpoint，寫明需求 18–21 的上限與 422。
2. `docs/architecture.md`：`users` 那一列的內容加上「排程偏好」。
3. `docs/specs/` 裡沒有規格寫過「偏好不存」，所以不用把舊規格標成被取代。

### 既有測試要改的

`frontend/tests/composables/useScheduleWizard.test.ts:75`「initWizard 每次都把 preferences 重置成預設值」驗的是舊需求。這次需求 11 改成 `initWizard` 保留 `preferences`，所以要改成驗新行為，並在 PR 描述寫明原因。

`frontend/tests/pages/schedule.test.ts:426` 的註解「沒勾整天才顯示起訖時間」在需求 24 之後不成立（勾了整天也顯示，只是不能編輯），斷言本身照樣成立；註解要跟著改。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | 後端 `tests/integration/test_user_api.py`：PUT 一份 4 種都有的偏好，再 GET；前端 `tests/composables/useScheduleWizard.test.ts`：讀取函式拿到這份偏好（一次性例外還沒結束） | GET 回傳的內容和 PUT 的一樣（一次性例外的時間是同一個時間點）；`preferences` 等於那份偏好加上瀏覽器時區 |
| AC2 | 由 AC1 的後端測試涵蓋：偏好存在後端，只要用同一個帳號讀，結果就一樣 | 同 AC1 |
| AC3 | 後端 `tests/unit/test_user_crud.py`：`users` 文件沒有 `schedule_preferences` 時讀取；前端：讀取函式拿到空白偏好 | 回傳 `{"blocked_recurring": [], "blocked_exceptions": [], "buffer_minutes": 0, "daily_max_minutes": null}`；`preferences` 等於 `defaultSchedulePreferences()` |
| AC4 | 前端：`preferences` 有一條沒選星期的每週規律和一條完整的規律，呼叫儲存函式 | PUT 的 body 的 `blocked_recurring` 只有那條完整的 |
| AC5 | 前端：`preferences` 是 `{blocked_recurring: [{days_of_week: [0], all_day: false, start_time: "12:00", end_time: "13:00"}], blocked_exceptions: [], buffer_minutes: 15, daily_max_minutes: 240, timezone: "Asia/Taipei"}`，呼叫儲存函式 | PUT 的 body 完全等於 `{"blocked_recurring": [{"days_of_week": [0], "all_day": false, "start_time": "12:00", "end_time": "13:00"}], "blocked_exceptions": [], "buffer_minutes": 15, "daily_max_minutes": 240}` |
| AC6 | 前端：mock 瀏覽器時區成 `Asia/Tokyo`，讀取函式拿到一份偏好 | `preferences.timezone` 是 `Asia/Tokyo` |
| AC7 | 前端 `tests/pages/schedule.test.ts`：走到第 2 步，改一條每週規律的星期、新增一條一次性例外，不按「完成」 | 沒有送出 `PUT /users/me/schedule-preferences` |
| AC8 | 前端頁面測試：`POST /schedule/suggest` 回 500，按「完成」 | 沒有送出 `PUT /users/me/schedule-preferences` |
| AC9 | 前端：用假時間固定「現在」，讀取函式拿到一條已結束、一條還沒結束的一次性例外，加上一條每週規律 | `preferences.blocked_exceptions` 只剩還沒結束的那條；`preferences.blocked_recurring` 是那一條每週規律 |
| AC10 | 前端頁面測試：按「完成」成功、存偏好成功，在第 3 步按「重新產生」，走到第 2 步；前端 composable 測試（改寫 `tests/composables/useScheduleWizard.test.ts:75`）：讀取函式帶入一條每週規律，改這條規律的 `days_of_week`、新增一條一次性例外、改 `buffer_minutes`，再呼叫 `initWizard`（頁面測試把 `useScheduleWizard` 換成假的，驗不到 `initWizard` 有沒有重設偏好，所以要有 composable 測試） | 頁面測試：整個測試只呼叫一次 `GET /users/me/schedule-preferences`；composable 測試：`preferences` 完全等於改過之後的值 |
| AC11 | 前端頁面測試：第 2 步改一條每週規律的星期，按「完成」，`POST /schedule/suggest` 回 500，在第 3 步按「重新產生」，走到第 2 步；同 AC10 的 composable 測試 | 頁面測試：沒有送出 `PUT /users/me/schedule-preferences`；composable 測試同 AC10 |
| AC12 | 前端頁面測試：有已刪除的事件，處理完後進入第 2 步（按「取消」走同一個函式 `enterWizardAfterRemovedStep`，不另外測） | 整個測試只呼叫一次 `GET /users/me/schedule-preferences`（`initWizard` 不改 `preferences` 由 AC10 的 composable 測試負責） |
| AC13 | 前端頁面測試：建議成功、`PUT` 回 500 | 畫面在第 3 步，顯示排程建議 |
| AC14 | 同 AC13 | 跳出 toast，標題或說明是「排程偏好沒有存成功，下次要重新填」 |
| AC15 | 前端頁面測試：`GET /users/me/schedule-preferences` 回 500 | 進到第 2 步時，`preferences` 等於空白預設值 |
| AC16 | 同 AC15 | 跳出 toast「讀不到上次的排程偏好，請重新填寫」 |
| AC17 | 後端 `tests/integration/test_user_api.py`：不帶登入打 GET、PUT | 都回 401；PUT 後資料庫的 `users` 文件沒有改變 |
| AC18 | 後端 `tests/integration/test_user_api.py`：用 A 的登入身分 PUT，換成 B 的身分 GET，再換回 A 的身分 GET | B 拿到空白預設值；A 拿到 A 存的內容 |
| AC19 | 後端 `tests/integration/test_user_api.py`：先存一份合法的偏好，再 PUT `{"buffer_minutes": "abc"}`，再 GET | PUT 回 422；GET 是原本那份 |
| AC20 | 同 AC19 的做法，PUT 51 條每週規律 | PUT 回 422；GET 是原本那份 |
| AC21 | 同 AC19 的做法，PUT 51 條一次性例外 | PUT 回 422；GET 是原本那份 |
| AC22 | 同 AC19 的做法，分別 PUT `days_of_week` 是 `[0,1,2,3,4,5,6,0]`、`[7]` | 都回 422；GET 是原本那份 |
| AC23 | 同 AC19 的做法，分別 PUT `start_time` 是 `"24:00"`、`"9:00"`、`"abc"`、`""`，以及 `end_time` 是 `"24:00"` | 都回 422；GET 是原本那份 |
| AC24 | 後端 `tests/integration/test_user_api.py`：PUT AC24 寫的邊界內容，再 GET | PUT 回 200；GET 回傳的內容和 PUT 的一樣 |
| AC25 | 後端 `tests/integration/test_schedule_api.py`：`POST /schedule/suggest` 送 51 條每週規律 | 不回 422 |
| AC26 | 後端 `tests/unit/test_user_crud.py`：存偏好後刪除使用者 | `users` collection 裡找不到這個使用者 |
| AC27 | 後端 `tests/integration/test_user_api.py`：存偏好後 GET `/users/me` | 回應的鍵只有 `id`、`email`、`name` |
| AC28 | 手動：讀 `frontend/pages/schedule.vue` 第 2 步一次性例外的標題（只改文字，不寫自動化測試） | 文字是「額外不排的時段（過了就自動移除）」，檔案裡找不到「這次額外不排的時段」 |
| AC29 | 手動：讀 `frontend/pages/schedule.vue` 沒有一次性例外時的提示 | 文字是「沒有額外的例外時段」，檔案裡找不到「沒有這次額外的例外時段」 |
| AC30 | 前端 composable 測試：`preferences.blocked_recurring` 是 `[{days_of_week: [1], all_day: true, start_time: "", end_time: null}]`（模擬舊資料或沒經過切換函式），看 `sanitizedPreferences`，再呼叫儲存函式 | `sanitizedPreferences.blocked_recurring` 和 PUT body 的 `blocked_recurring` 都完全等於 `[{"days_of_week": [1], "all_day": true, "start_time": "00:00", "end_time": "23:59"}]`；`preferences` 裡那條規律仍是 `start_time: ""`、`end_time: null` |
| AC31 | 前端 composable 測試：一條 `start_time: "09:00"`、`end_time: "10:00"` 的規律，呼叫切換「整天」的函式勾選；前端頁面測試：勾了整天的規律，再點一條沒勾整天的規律的「整天」勾選框（寫法照 `tests/pages/schedule.test.ts:412-419`） | composable：規律是 `{all_day: true, start_time: "00:00", end_time: "23:59"}`；頁面：勾了整天的規律兩個時間輸入框有 `disabled`；點勾選框後，切換「整天」函式的 spy 收到這條規律與勾選狀態 |
| AC32 | 前端 composable 測試：接 AC31，再呼叫切換函式取消勾選；前端頁面測試：沒勾整天的規律（可併進 `tests/pages/schedule.test.ts:423-426`） | composable：規律是 `{all_day: false, start_time: null, end_time: null}`；頁面：兩個時間輸入框沒有 `disabled` |
| AC33 | 前端 composable 測試：讀取函式帶入一條 `{all_day: true, start_time: "00:00", end_time: "23:59"}` 的規律，呼叫切換函式取消勾選 | 規律是 `{all_day: false, start_time: null, end_time: null}` |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
