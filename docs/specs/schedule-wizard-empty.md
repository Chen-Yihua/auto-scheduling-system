# 排程精靈沒有任務時的說明、首頁今日卡片與已逾期任務重新排程

- 狀態：已核准
- 等級：高風險（「修改」與「批次重新排程」會刪除 Google 日曆上的事件，並清掉任務的 `calendar_event_id`，改變了和外部系統同步的一致性保證）
- PR：#179

## 簡短說明

使用者按「產生排程建議」後，排程精靈看不到任何任務，也不知道原因。這次修好重新整理時卡在載入框的 bug，讓精靈說明為什麼沒有任務，並在首頁新增今日卡片，讓已逾期的任務可以重新排程。

## 背景

使用者在首頁按「產生排程建議」，進到 `/schedule` 排程精靈後，看不到任何任務。

這次發現兩個問題。

**問題 1：重新整理 `/schedule` 時，頁面一直停在灰色載入框。**

重現步驟：
1. 登入後打開 `/schedule`。
2. 按瀏覽器的重新整理。

實際：每次都停在 3 條灰色載入框，console 沒有錯誤。

預期：載入完成後顯示精靈。

原因：
- `frontend/pages/schedule.vue:45-46` 的 `onMounted` 開頭寫 `if (!isSignedIn.value) return`。重新整理時 Clerk 還沒載入完，`isSignedIn` 是 `undefined`，函式就直接結束。
- Clerk 載入完之後，沒有任何程式再執行一次初始化，所以 `pageState` 一直停在 `'checking'`。
- jira、github、moodle、productivity 頁與首頁都用 `watch(isSignedIn, …, { immediate: true })` 等 Clerk 載入完再抓資料，例如 `frontend/pages/jira.vue:11-13`、`frontend/components/dashboard/Dashboard.vue:44-49`。

**問題 2：從首頁進入精靈時，三欄都是空的，畫面沒有說明原因。**

開發者的實際資料：`GET /schedule/tasks` 回 200，列出 7 個任務。其中：
- 5 個任務有 `calendar_event_id`，代表已經排進 Google 日曆。
- 2 個任務的 `status` 是 `Done`。

精靈只保留「不是主任務、沒有完成、沒有 `calendar_event_id`」的任務（`frontend/composables/useScheduleWizard.ts:72-75`），和後端排程的規則一致（`backend/services/scheduler.py:219`）。所以篩選照規則運作，問題出在畫面只顯示「拖任務到這裡」，沒有說明原因。

另外，已排進日曆、但過了時段還沒完成的任務，目前只有一種方式可以重新排程：使用者先到 Google 日曆刪掉事件，再進排程精靈的「處理已刪除的事件」步驟（`backend/routers/schedule.py:205-229`、`265-299`）。在這個系統裡改截止日期，不會影響已排程的狀態（`backend/routers/manual_task.py:268`）。

現有程式的相關事實：
- 任務只記事件編號 `calendar_event_id`，不記事件時間。事件時間每次都向 Google 查（`backend/services/google_calendar.py:212`）。
- 確認排程時，`create_calendar_events_for_scheduled_tasks` 知道每筆的開始和結束時間（`backend/services/google_calendar.py:175-176`），但只寫回事件編號（`backend/services/google_calendar.py:187`）。
- 排程時，截止日期還沒到的任務，時段一定排在截止日期之前（`backend/services/scheduler.py:282-297`）。截止日期已過，或沒有截止日期、也沒有從後面階段推算的期限（`backend/services/scheduler.py:27-52`）的任務，不受這個限制。
- 手動任務用表單的日曆選截止日期時，存的是當地當天的 00:00（`frontend/composables/useTaskForm.ts:49-52`）。
- 外部平台同步只寫入平台回傳的欄位（`backend/platforms/sync.py:99-111`），不會蓋掉任務上的排程欄位。

## 需求

**排程精靈**

1. 使用者重新整理 `/schedule` 時，Clerk 載入完成後，頁面照常初始化精靈。
2. 精靈第 1 步沒有可排程的任務時，不顯示三欄，改顯示說明。
3. 說明列出已排進 Google 日曆的任務數。計算的是不是主任務、沒有完成、有 `calendar_event_id` 的任務。
4. 說明列出已完成的任務數。計算的是不是主任務、`status` 是 `Done` 的任務。
5. 說明寫明已逾期的任務可以在首頁的今日卡片重新排程。
6. 說明附「回首頁」按鈕。
7. 使用者沒有任何任務（不算主任務）時，說明只寫「目前沒有任務」，不列數字。
7a. 進入精靈時任務清單載入失敗，不顯示第 2–7 條的說明，改顯示「暫時無法載入任務」與「回首頁」按鈕。
8. 精靈不另外提醒已排程、已逾期的任務。

**資料**

9. 確認排程寫入 Google 日曆成功時，系統把該筆的開始、結束時間存進任務的 `scheduled_start`、`scheduled_end`。
10. `scheduled_start`、`scheduled_end` 和 `calendar_event_id` 在同一次資料庫更新寫入。
11. 清掉 `calendar_event_id` 時，`scheduled_start`、`scheduled_end` 在同一次更新清成 `null`。既有「處理已刪除的事件」的重新排程也照這條。
12. 手動任務和外部平台任務都有這兩個欄位。
13. `GET /schedule/tasks` 的每筆任務帶上 `scheduled_start`、`scheduled_end`。

**今日卡片**

14. 首頁左欄最上方，在任務列表卡片的上面，新增今日卡片。
15. 今日卡片的內容全部用 `GET /schedule/tasks` 的資料計算，不呼叫 Google。
16. 主任務不列在今日卡片上。
17. 已逾期的任務，是指沒有完成、而且符合下面任一條件的任務：截止日期所在的那一天（使用者瀏覽器時區）早於今天，也就是截止日那一天已經結束；或 `scheduled_end` 早於現在。
18. 已逾期的任務列在卡片最上方。
19. 已逾期的任務依「截止日期與 `scheduled_end` 中較早的那個時間」由早到晚排列。
20. 已逾期以外，`scheduled_start` 落在使用者瀏覽器時區的今天的任務，列在已逾期的任務下面。
21. 第 20 條的任務，沒有完成的依 `scheduled_start` 由早到晚排列，已完成的排在最後。
22. 每筆任務顯示一個中文的狀態標籤，照下面順序判斷，符合一條就停：
    1. 符合第 17 條：標「已逾期」。
    2. `status` 是 `Done`：標「已完成」。
    3. `status` 是 `In Progress`：標「進行中」。
    4. 其他：標「未開始」。
23. 已逾期的任務，日期文字用紅色顯示。
24. 任務清單載入完成、沒有任何要列的任務時，卡片顯示「今天沒有排程的任務，也沒有已逾期的任務」。
24a. 任務清單載入中時，卡片顯示載入框，不顯示第 24 條的文字。
24b. 任務清單載入失敗時，卡片顯示「暫時無法載入任務」，不顯示第 24 條的文字。

**修改、刪除、批次重新排程**

25. 沒有完成的任務，每筆都有「修改」按鈕。
26. 沒有完成的手動任務，每筆都有「刪除」按鈕；外部平台的任務沒有「刪除」按鈕。
27. 已完成的任務沒有任何按鈕。
28. 手動任務按「修改」時，打開現有的任務編輯表單，填入這個任務的資料。
29. 外部平台任務按「修改」時，打開只有截止日期和時長兩個欄位的表單。
30. 從今日卡片打開表單、任務有 `calendar_event_id` 時，表單上方顯示：「儲存後會從 Google 日曆移除這個任務的時段（後面已排程的階段也會一起移除），任務回到排程清單。」
31. 從今日卡片打開表單儲存成功後，任務有 `calendar_event_id` 時，系統把這個任務重新排程（第 36–41 條）。
31a. 第 31 條的情況下，儲存與重新排程結束後只跳一個通知，照下面順序判斷，符合一條就停：
    1. 重新排程因 Google 授權失效而失敗：通知寫「已儲存，但需要重新連接 Google Calendar 才能重新排程」，並附重新連接的按鈕。
    2. 重新排程回其他錯誤，或這個任務列在回應的失敗清單：通知寫「已儲存，但重新排程失敗」，加上錯誤訊息或失敗清單的原因。
    3. 重新排程成功：通知寫「儲存成功」。
32. 從任務頁或首頁任務列表打開同一個表單時，儲存的行為和現在一樣，不重新排程。
33. 按「刪除」時，照現有的任務刪除流程處理：先確認，再連同 Google 日曆事件一起刪除。
34. 卡片上方有「批次重新排程」按鈕，只在有「已逾期、有 `calendar_event_id`」的任務時顯示。
35. 按「批次重新排程」時，先跳出確認，確認後把第 34 條的任務重新排程。
35a. 確認訊息寫「會從 Google 日曆移除 N 個任務的時段，放回排程清單，確定嗎？」。N 是第 34 條的任務數。
35b. 第 34 條的任務裡有階段任務，而且它後面有已排程、沒有完成、不在這 N 個任務裡的階段時，確認訊息另外寫「另外 M 個後面階段的時段也會一起移除」。M 是這些後面階段去掉重複後的數量。

**重新排程**（新增的 `POST /schedule/tasks/reschedule`）

36. 重新排程一個任務時，系統先刪除它在 Google 日曆上的事件，再清掉 `calendar_event_id`。
37. 重新排程的任務是階段任務時，後面已排程、沒有完成、不在這次請求裡的階段，事件也先刪除，再清掉它們的 `calendar_event_id`。這條和既有「處理已刪除的事件」的規則相同（`backend/routers/schedule.py:191-202`）。
38. 清掉 `calendar_event_id` 時，只在任務的 `calendar_event_id` 仍是處理開始時讀到的值時才清。值已經被換掉時，這一項列為失敗。
39. Google 上的事件已經不存在（404、410）時，當作刪除成功，接著清掉 `calendar_event_id`。
40. 一個請求可以帶多個任務。單一任務的問題（不存在、不屬於自己、是主任務、已完成、編號被換掉）列在回應的失敗清單，接著處理下一個。
41. 呼叫 Google 失敗（包括授權失效）時，整個請求停止並回錯誤；已處理成功的任務不復原。
42. 沒有 `calendar_event_id` 的任務，不呼叫 Google，直接算成功。
43. 重新排程完成或失敗後，畫面都重新抓任務清單，並重新載入首頁的 Google 日曆：失敗時已處理成功的任務不會復原，不重新抓的話畫面會和資料庫不一致。
44. 「批次重新排程」結束後，照下面順序判斷要跳的通知，符合一條就停：
    1. Google 授權失效：跳出既有的重新連接提示（`reauthToast`）。
    2. API 回其他錯誤：通知寫「重新排程沒有全部完成」與錯誤訊息，並寫「已處理的任務已放回排程清單，請再按一次處理剩下的任務」。
    3. 有任務列在失敗清單：通知列出失敗的任務名稱與原因。
    4. 全部成功：通知寫「已把 N 個任務放回排程清單」。N 是送出的任務數。

## 不做

- 使用者在 Google 日曆上拖動事件後，`scheduled_start`、`scheduled_end` 不會更新；今日卡片照存下來的時間判斷。定時同步 Google 日曆時段由 #177 處理。
- 這次上線前已經排進日曆的任務，不補 `scheduled_start`、`scheduled_end`。這些任務只用截止日期判斷是否已逾期，也不會出現在第 20 條的今天任務。
- 今日卡片不查詢 Google，所以不會發現 Google 上已被刪除的事件。這種任務照資料庫的資料顯示，由排程精靈既有的「處理已刪除的事件」步驟處理。
- 標題列改成 4 個頁面、隱藏首頁的 Moodle 和 Jira 卡片，由 #178 處理。
- 從任務頁或首頁任務列表編輯已排程的任務時，不重新排程。
- 精靈不顯示已排程、已逾期的任務的提醒。
- 不新增排程相關 API 的限流（#122 處理）。
- 首頁一直開著時，今日卡片不會隨時間自動更新「現在」：任務的時段結束或跨過午夜後，要重新整理頁面，或任務清單重新抓取後，卡片才會更新。

## 假設

1. 外部平台任務的修改表單，用既有的 `PATCH /schedule/tasks/fields` 儲存截止日期和時長。
2. 「今天」與「現在」用使用者瀏覽器的時間和時區判斷，在前端計算。
3. 從今日卡片修改任務時，先儲存表單，成功後才重新排程：表單的驗證（例如階段的截止日期限制）失敗時，Google 日曆上的事件不會先被刪掉。
4. 已逾期任務第 19 條的排序，只有其中一個時間時用那一個時間。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 已登入的使用者重新整理 `/schedule`，Clerk 載入完成後，頁面抓取任務並顯示精靈，不再停在載入框 |
| AC2 | 精靈沒有可排程的任務時，第 1 步不顯示三欄，改顯示說明與「回首頁」按鈕 |
| AC3 | 使用者有 5 個已排進日曆、2 個已完成的任務時，說明寫出「5」個已排進 Google 日曆、「2」個已完成 |
| AC4 | 精靈的說明寫明已逾期的任務可以在首頁的今日卡片重新排程 |
| AC5 | 使用者沒有任何非主任務的任務時，說明只顯示「目前沒有任務」 |
| AC5a | 進入精靈時任務清單載入失敗，不顯示 AC2–AC5 的說明，改顯示「暫時無法載入任務」與「回首頁」按鈕 |
| AC6 | 精靈有可排程的任務時，照常顯示三欄 |
| AC7 | 確認排程成功的任務，資料庫的 `scheduled_start`、`scheduled_end` 是寫入 Google 的開始、結束時間 |
| AC8 | 確認排程寫入 Google 失敗的任務，`calendar_event_id`、`scheduled_start`、`scheduled_end` 都不變 |
| AC9 | 外部平台任務確認排程成功後，同樣存有 `scheduled_start`、`scheduled_end` |
| AC10 | 「處理已刪除的事件」把任務重新排程後，`calendar_event_id`、`scheduled_start`、`scheduled_end` 都是 `null` |
| AC11 | `GET /schedule/tasks` 回應的每筆任務都有 `scheduled_start`、`scheduled_end` 欄位；沒有存的任務是 `null` |
| AC12 | 外部平台同步後，任務的 `scheduled_start`、`scheduled_end` 不變 |
| AC13 | 首頁的今日卡片位於左欄最上方，在任務列表卡片上面 |
| AC14 | 沒有完成、截止日期是昨天（含）以前的任務，列在今日卡片的已逾期區，標「已逾期」，日期文字是紅色 |
| AC14a | 沒有完成、截止日期是今天 00:00、`scheduled_end` 還沒到或沒有的任務，今天不算已逾期 |
| AC15 | 沒有完成、截止日期還沒到、`scheduled_end` 早於現在的任務，列在已逾期區，標「已逾期」 |
| AC16 | 已完成的任務，即使截止日期已過，也不列在已逾期區 |
| AC17 | 已逾期區的任務依截止日期與 `scheduled_end` 較早的時間由早到晚排列 |
| AC18 | `scheduled_start` 在今天、還沒逾期的任務列在已逾期區下面，依 `scheduled_start` 排列，已完成的排在最後 |
| AC19 | `scheduled_start` 不在今天、也沒有逾期的任務，不列在今日卡片 |
| AC20 | 截止日期是今天、沒有今天時段、`scheduled_end` 沒有過的任務，不列在今日卡片 |
| AC21 | 主任務不列在今日卡片 |
| AC22 | 不是已逾期的任務，依 `status` 標「未開始」「進行中」「已完成」 |
| AC23 | 任務清單載入完成、沒有任何要列的任務時，卡片顯示「今天沒有排程的任務，也沒有已逾期的任務」 |
| AC23a | 任務清單載入中時，卡片顯示載入框，不顯示 AC23 的文字 |
| AC23b | 任務清單載入失敗時，卡片顯示「暫時無法載入任務」，不顯示 AC23 的文字 |
| AC24 | 沒有完成的手動任務有「修改」「刪除」按鈕；沒有完成的外部平台任務只有「修改」；已完成的任務沒有按鈕 |
| AC25 | 手動任務按「修改」，打開編輯表單並填入這個任務的資料 |
| AC26 | 外部平台任務按「修改」，打開只有截止日期與時長的表單 |
| AC27 | 從今日卡片打開有 `calendar_event_id` 的任務的表單，表單上方顯示會移除時段、回到排程清單的說明；沒有 `calendar_event_id` 的任務不顯示 |
| AC28 | 從今日卡片修改已排程的手動任務並儲存成功，任務的欄位已更新、Google 上的事件已刪除、`calendar_event_id` 是 `null`，任務出現在排程精靈的三欄 |
| AC29 | 從今日卡片修改已排程的外部平台任務並儲存成功，截止日期與時長已更新，任務被重新排程 |
| AC30 | 從今日卡片修改時，表單儲存成功但重新排程因 Google 授權失效而失敗，通知寫「已儲存，但需要重新連接 Google Calendar 才能重新排程」並附重新連接按鈕，任務仍有 `calendar_event_id` |
| AC31 | 從今日卡片修改時，表單儲存失敗，不呼叫重新排程，Google 上的事件仍在 |
| AC32 | 從今日卡片修改時，表單儲存成功、重新排程因授權失效以外的原因失敗，只跳一個通知，寫出「已儲存，但重新排程失敗」與原因，任務仍有 `calendar_event_id` |
| AC32a | 從今日卡片修改時，表單儲存與重新排程都成功，只跳「儲存成功」一個通知 |
| AC32b | 從今日卡片修改外部平台任務時，小表單儲存成功、重新排程因授權失效以外的原因失敗，只跳一個通知，寫出「已儲存，但重新排程失敗」與錯誤訊息 |
| AC33 | 從任務頁打開同一個任務的表單並儲存，不呼叫重新排程 |
| AC34 | 按手動任務的「刪除」，跳出確認；確認後任務與它的 Google 日曆事件都被刪除；取消時什麼都不變 |
| AC35 | 有已逾期、已排程的任務時顯示「批次重新排程」；沒有時不顯示 |
| AC36 | 按「批次重新排程」跳出確認，寫出 N（已逾期、已排程的任務數）；確認後只把這 N 個任務的 id 送去重新排程 |
| AC36a | 批次重新排程後，不是這 N 個任務、也不是它們後面階段的任務，Google 事件與 `calendar_event_id` 都不變 |
| AC36b | 已逾期的階段 1 後面有排在今天、還沒逾期的已排程階段 2 時，確認訊息寫「另外 1 個後面階段的時段也會一起移除」 |
| AC36c | 承 AC36b，確認後階段 2 的 Google 事件已刪除，`calendar_event_id` 是 `null` |
| AC37 | 「批次重新排程」確認時按取消，不呼叫 API |
| AC38 | `POST /schedule/tasks/reschedule` 處理一個已排程的任務後，Google 上的事件已刪除，`calendar_event_id`、`scheduled_start`、`scheduled_end` 都是 `null` |
| AC39 | 重新排程某個階段時，後面已排程、沒有完成的階段，Google 事件都被刪除，`calendar_event_id` 都被清掉 |
| AC40 | 重新排程某個階段時，前面的階段、已完成的後面階段都不變 |
| AC41 | Google 上的事件已經不存在（404 或 410）時，重新排程仍然成功，`calendar_event_id` 被清掉 |
| AC42 | 處理期間任務的 `calendar_event_id` 被換成別的值時，這一項列為失敗，新的值不被清掉 |
| AC43 | 請求裡有不屬於自己或不存在的任務 id，這一項列為失敗、原因和不存在時相同，其他任務照常處理 |
| AC44 | 請求裡有主任務或已完成的任務，這一項列為失敗，任務與 Google 事件不變 |
| AC45 | 呼叫 Google 失敗時，API 回錯誤；還沒處理的任務的 `calendar_event_id` 與 Google 事件都不變 |
| AC46 | Google 授權失效時，API 回需要重新連接的錯誤；「批次重新排程」時畫面顯示重新連接 Google Calendar 的提示 |
| AC47 | 沒有 `calendar_event_id` 的任務送去重新排程，不呼叫 Google，算成功 |
| AC48 | 沒登入時呼叫 `POST /schedule/tasks/reschedule` 回 401 |
| AC49 | 同一個任務在一個請求裡重複出現，只處理一次的結果和處理一次相同 |
| AC50 | 重新排程完成後，今日卡片與首頁的 Google 日曆都重新載入 |
| AC50a | 重新排程失敗（API 回錯誤）後，今日卡片與首頁的 Google 日曆也都重新載入 |
| AC51 | 「批次重新排程」有任務列在失敗清單時，通知列出失敗的任務名稱與原因 |
| AC51a | 「批次重新排程」時 API 回 500，通知寫「重新排程沒有全部完成」、錯誤訊息，以及「已處理的任務已放回排程清單，請再按一次處理剩下的任務」 |
| AC51b | 「批次重新排程」全部成功，通知寫「已把 N 個任務放回排程清單」 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 未登入時的今日卡片 | 首頁未登入時本來就顯示登入提示卡片，不載入任務；這次在同一個位置不顯示今日卡片 |
| 今日卡片的 Google 查詢失敗 | 今日卡片不呼叫 Google（需求 15） |
| 同時有兩個分頁重新排程同一個任務 | 第二個請求讀到的 `calendar_event_id` 已是 `null`，走需求 42 算成功；條件清除（AC42）讓兩個請求不會清掉對方寫入的新值 |
| 重新排程時把資料寫錯人的資料 | 每一項都用登入者的 `sub` 查詢，AC43 涵蓋 |
| 輸入注入 | 任務 id 只用來查詢資料庫的等值條件，格式錯誤時照既有的組合 id 規則回失敗（AC43） |

## 實作計畫

### 後端

1. `backend/schemas/schedule.py`：`SchedulableTaskOut` 加上選填的 `scheduled_start`、`scheduled_end`（`Optional[datetime] = None`）。新增 `RescheduleTasksInput`（`task_ids: list[str]`，至少 1 筆）和回應格式。回應沿用 `ResolveRemovedEventsResult` 的 `succeeded`、`failed` 結構。
2. `backend/crud/manual_task.py`：
   - `set_calendar_event_id` 改成同時寫入 `scheduled_start`、`scheduled_end`。
   - `clear_calendar_event_id` 改成同時把兩個欄位設成 `None`，條件仍是 `calendar_event_id` 等於讀到的值。
3. `backend/crud/schedulable_items.py`：
   - `set_calendar_event_id_for_composite`、`clear_calendar_event_id_for_composite` 對外部平台做同樣的改動。
   - `_normalize_external` 帶出 `scheduled_start`、`scheduled_end`。
4. `backend/services/google_calendar.py:187`：呼叫 `set_calendar_event_id_for_composite` 時傳入該筆的 `start`、`end`。
5. `backend/routers/schedule.py`：新增 `POST /schedule/tasks/reschedule`。
   - 逐筆處理，去掉重複的 id。
   - 每一筆照 `_reschedule_removed_item` 的順序：讀任務 → 檢查是不是主任務、是不是已完成 → 刪除後面階段的事件並逐一條件清除 → 刪除自己的事件 → 條件清除自己的編號。
   - 和 `_reschedule_removed_item` 的差別：不檢查事件是否已被刪除，而是直接刪除自己的事件。
   - 共用的「後面階段」處理抽成一個函式，兩支 API 都呼叫。
6. `docs/api.md` 加上新的 endpoint。

### 前端

7. `frontend/types/schedulableTask.ts`：加上 `scheduled_start`、`scheduled_end`。
8. `frontend/pages/schedule.vue`：
   - `onMounted` 的初始化改成 `watch(isSignedIn, …, { immediate: true })`，`isSignedIn` 變成 `true` 時執行一次。
   - 第 1 步沒有任務（`hasTasks` 是 `false`）時，改顯示空狀態說明。數字用 `schedulableTasks` 計算（需求 3、4、7）。
9. `frontend/utils/todayTasks.ts`（新增）：純函式，輸入任務清單與「現在」，回傳已逾期區與今天區的任務、每筆的狀態標籤，以及批次重新排程的 N 個 id 與 M（需求 35b）。今日卡片和測試都用它，「現在」由參數傳入，測試才能固定時間。
10. `frontend/components/dashboard/TodayTasks.vue`（新增）：今日卡片，用 `useSchedulableTasks` 的清單與第 9 步的函式。放進 `Dashboard.vue` 左欄最上方。
11. `frontend/composables/useSchedulableTasks.ts`：
    - 新增 `rescheduleTasks(ids)`，呼叫新 API。完成或失敗後都重新抓清單，並呼叫 `useGoogleCalendar` 的 `triggerCalendarReload` 重新載入首頁日曆（需求 43、AC50、AC50a）。
    - `rescheduleTasks` 不跳通知，回傳結果給呼叫端：結果的種類（授權失效、其他錯誤、成功）、其他錯誤時的錯誤訊息、回應的失敗清單。
    - 批次重新排程的呼叫端（今日卡片）依回傳結果照需求 44 通知；授權失效時用 `useGoogleCalendarAuth` 的 `reauthToast`。
    - 新增載入失敗的狀態（例如 `loadFailed`），今日卡片依它顯示需求 24b。
12. `frontend/composables/useTaskForm.ts`：
    - 今日卡片的任務 id 是組合 id（`manual:<uuid>`）。照 `frontend/components/tasks/TaskForm.vue:91-96` 的做法去掉前綴、從 `all_tasks` 找出對應的手動任務，再呼叫 `startEditTask`。
    - `startEditTask` 加一個選項，標記這次是從今日卡片打開的。
    - `onEdit` 儲存成功後，有這個標記、任務有 `calendar_event_id` 時，呼叫 `rescheduleTasks`。
    - 儲存成功後的通知照需求 31a，延後到重新排程結束才跳，原本 `onEdit` 立刻跳的「儲存成功」在這個情況下不跳。`onEdit` 依 `rescheduleTasks` 的回傳結果（第 11 步）決定通知文字，失敗清單裡有這個任務時用它的原因，不在 `rescheduleTasks` 裡另外跳 `reauthToast`，避免同一次失敗跳兩個通知。
    - 表單關閉或從其他地方打開時，清掉標記。
    - `TaskForm.vue` 的編輯視窗依標記顯示需求 30 的說明。
13. 外部平台任務的修改表單：在 `TodayTasks.vue` 裡用 `UModal`，欄位是截止日期與時長，用 `PATCH /schedule/tasks/fields` 儲存，成功後照第 12 步同樣的條件重新排程，通知照需求 31a，每次只跳一個。

### 考慮過、沒選的做法

- **今日卡片每次向 Google 查事件時間**：可以拿到使用者拖動後的最新時間，但每個已排程的任務都要查一次 Google。Google 連不上時卡片也會出錯。開發者決定今日卡片只用資料庫的資料。
- **新增一個 collection 存任務和事件的對應**：任務和事件是一對一，放在同一筆文件裡，一次更新就能讓三個欄位一致；分兩個 collection 要另外處理中途失敗時的不一致。開發者選擇存在任務本身。
- **改了截止日期才重新排程**：使用者只改標題或時長時，任務會留在原本的時段；想重排卻不想改日期時，要故意改日期。開發者選擇從今日卡片打開的表單儲存後一律重新排程。
- **一支 API 同時儲存欄位並重新排程**：要把 `PUT /manual-tasks/{id}` 和 `PATCH /schedule/tasks/fields` 的驗證再寫一次。分兩次呼叫的話，任一步失敗時的狀態都一致：儲存失敗，什麼都沒變；重新排程失敗，欄位已更新，任務仍是已排程，使用者可以再按一次。
- **先清掉 `calendar_event_id`，再刪 Google 事件**：Google 刪除失敗時，Google 上會留下系統不再追蹤的事件，重新排程後同一個任務會有兩個事件。先刪事件再清編號，中途失敗只會留下「Google 上沒有事件、任務還有編號」，既有的「處理已刪除的事件」會再列出來處理。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 | 改程式前是否失敗 |
|---|---|---|---|
| AC1 | `frontend/tests/pages/schedule.test.ts`：掛載時 `isSignedIn` 是 `undefined`，之後改成 `true` | `fetchSchedulableTasks` 被呼叫一次，`initWizard` 被呼叫 | 是 |
| AC2 | `schedule.test.ts`：`hasTasks` 是 `false` | 沒有三欄，有說明與「回首頁」按鈕 | 是 |
| AC3 | `schedule.test.ts`：5 個有 `calendar_event_id`、2 個 `Done` | 說明含「5」與「2」 | 是 |
| AC4 | `schedule.test.ts`：同 AC2 | 說明含「今日卡片」 | 是 |
| AC5 | `schedule.test.ts`：任務清單只有主任務或是空的 | 只顯示「目前沒有任務」 | 是 |
| AC5a | `schedule.test.ts`：`fetchSchedulableTasks` 後 `loadFailed` 是 `true` | 顯示「暫時無法載入任務」與「回首頁」按鈕，沒有「目前沒有任務」 | 是 |
| AC6 | `schedule.test.ts` 既有的「step 1：三欄渲染各自的任務」 | 照常通過 | 否（既有行為） |
| AC7 | `backend/tests/unit/test_google_calendar_service.py`：寫入成功 | 任務的 `scheduled_start`、`scheduled_end` 等於該筆的 start、end | 是 |
| AC8 | `test_google_calendar_service.py`：寫入失敗 | 三個欄位都不變 | 否（既有行為加斷言） |
| AC9 | `backend/tests/unit/test_schedulable_items.py`：對外部平台呼叫 `set_calendar_event_id_for_composite` | 兩個欄位已寫入 | 是 |
| AC10 | `backend/tests/unit/test_schedule_router.py`：「處理已刪除的事件」重新排程 | 三個欄位都是 `null` | 是 |
| AC11 | `test_schedule_api.py`：`GET /schedule/tasks` | 每筆都有兩個欄位，沒存的是 `null` | 是 |
| AC12 | `backend/tests/unit/test_platform_sync.py`：`upsert_items` 前已有兩個欄位 | 同步後兩個欄位不變 | 否（保護既有行為） |
| AC13 | `frontend/tests/components/Dashboard.test.ts` | 左欄第一個元件是今日卡片，在任務列表前面 | 是 |
| AC14–AC22 | `frontend/tests/utils/todayTasks.test.ts`：固定「現在」為 2026-11-21 10:00（當地），截止日期用具體時間準備，例如 2026-11-20T00:00、2026-11-21T00:00，另加一筆外部平台任務 2026-11-21T09:00 截止、`scheduled_end` 沒過 | 分區、排序、標籤符合各 AC；AC14a 的任務與 09:00 截止的那一筆都不在已逾期區 | 是 |
| AC14（紅字） | `frontend/tests/components/TodayTasks.test.ts` | 已逾期任務的日期元素有紅色的 class | 是 |
| AC23 | `TodayTasks.test.ts`：載入完成、沒有任務 | 顯示「今天沒有排程的任務，也沒有已逾期的任務」 | 是 |
| AC23a | `TodayTasks.test.ts`：`loading` 是 `true` | 有載入框，沒有 AC23 的文字 | 是 |
| AC23b | `TodayTasks.test.ts`：載入失敗狀態 | 顯示「暫時無法載入任務」，沒有 AC23 的文字 | 是 |
| AC24 | `TodayTasks.test.ts`：手動、外部、已完成各一筆 | 按鈕符合 AC | 是 |
| AC25 | `TodayTasks.test.ts`：按手動任務「修改」 | 用原始 id 對應的 `all_tasks` 手動任務呼叫 `startEditTask`，帶今日卡片的標記 | 是 |
| AC26 | `TodayTasks.test.ts`：按外部任務「修改」 | 打開只有截止日期與時長的表單 | 是 |
| AC27 | `frontend/tests/components/TaskForm.test.ts`：有標記、有／沒有 `calendar_event_id` | 有編號時顯示說明，沒有時不顯示 | 是 |
| AC28 | `frontend/tests/composables/useTaskForm.test.ts`：有標記、有編號，`PUT` 成功，斷言 `PUT` 的網址是原始 id（沒有 `manual:` 前綴）；另外 `backend/tests/integration/test_schedule_scenario.py`：確認排程 → 重新排程 → `GET /schedule/tasks` | 前端：`PUT` 後呼叫重新排程；後端：三個欄位都是 `null`，任務符合精靈的篩選 | 是 |
| AC29 | `TodayTasks.test.ts`：外部任務表單儲存成功 | 先呼叫 `PATCH /schedule/tasks/fields`，再呼叫重新排程 | 是 |
| AC30 | `useTaskForm.test.ts`：`PUT` 成功、重新排程回授權失效 | 只有一個通知，含「已儲存，但需要重新連接 Google Calendar 才能重新排程」與重新連接按鈕；沒有 `reauthToast`、「儲存成功」或「已儲存，但重新排程失敗」 | 是 |
| AC31 | `useTaskForm.test.ts`：`PUT` 失敗 | 不呼叫重新排程 | 是 |
| AC32 | `useTaskForm.test.ts`：`PUT` 成功、重新排程回 500；另一個案例回 200 但這個任務在失敗清單 | 兩個案例都只有一個通知，含「已儲存，但重新排程失敗」與原因 | 是 |
| AC32a | `useTaskForm.test.ts`：`PUT` 與重新排程都成功 | 只有「儲存成功」一個通知 | 是 |
| AC32b | `TodayTasks.test.ts`：外部任務小表單 `PATCH` 成功、重新排程回 500 | 只有一個通知，含「已儲存，但重新排程失敗」與錯誤訊息 | 是 |
| AC33 | `useTaskForm.test.ts`：沒有標記 | 不呼叫重新排程 | 否（既有行為） |
| AC34 | `TodayTasks.test.ts`：按「刪除」後確認、取消 | 確認時呼叫既有的刪除；取消時不呼叫 | 是 |
| AC35 | `TodayTasks.test.ts` | 有已逾期、已排程任務時有按鈕，沒有時沒有 | 是 |
| AC36 | `TodayTasks.test.ts`：2 個已逾期已排程、1 個今天未逾期已排程 | 確認訊息含「2」；只送出那 2 個 id | 是 |
| AC36a | `test_schedule_router.py`：重新排程任務 A，另有不相關的已排程任務 B | B 的事件與編號不變 | 是 |
| AC36b | `todayTasks.test.ts` 與 `TodayTasks.test.ts`：階段 1 已逾期、階段 2 今天已排程 | M 是 1；確認訊息含「另外 1 個後面階段」 | 是 |
| AC36c | `test_schedule_router.py`：只送出階段 1 | 階段 2 的事件已刪除、編號是 `null` | 是 |
| AC37 | `TodayTasks.test.ts`：確認時取消 | 不呼叫 API | 是 |
| AC38 | `backend/tests/unit/test_schedule_router.py`：已排程任務 | 呼叫刪除事件；三個欄位都是 `null` | 是 |
| AC39 | `test_schedule_router.py`：3 個階段都已排程，重新排程階段 1 | 刪除 3 個事件；3 個 `calendar_event_id` 都是 `null` | 是 |
| AC40 | `test_schedule_router.py`：重新排程階段 2，階段 1 已排程、階段 3 已完成 | 階段 1、3 不變 | 是 |
| AC41 | `test_schedule_router.py`：Google 刪除回 404 | 成功，編號清掉 | 是 |
| AC42 | `test_schedule_router.py`：清除前把 `calendar_event_id` 換成新值 | 列為失敗，新值保留 | 是 |
| AC43 | `test_schedule_router.py`：別人的任務 id、不存在的 id | 兩者失敗原因相同；其他任務成功 | 是 |
| AC44 | `test_schedule_router.py`：主任務、已完成任務 | 列為失敗；不呼叫 Google；資料不變 | 是 |
| AC45 | `test_schedule_router.py`：第 2 筆刪除時 Google 回 500 | 回錯誤；第 3 筆不變 | 是 |
| AC46 | `test_schedule_router.py`：Google 回 401；`TodayTasks.test.ts`：批次重新排程時 API 回需要重新連接；`useSchedulableTasks.test.ts`：`rescheduleTasks` 回傳的失敗種類是授權失效 | 後端丟需要重新連接的錯誤；今日卡片顯示 `reauthToast` | 是 |
| AC47 | `test_schedule_router.py`：沒有編號的任務 | 不呼叫 Google；列在成功 | 是 |
| AC48 | `test_schedule_api.py`：沒登入 | 401 | 是 |
| AC49 | `test_schedule_router.py`：同一個 id 出現兩次 | 只刪一次事件，結果列一次成功 | 是 |
| AC50 | `useSchedulableTasks.test.ts` | 完成後重新抓清單，並呼叫 `triggerCalendarReload` | 是 |
| AC50a | `useSchedulableTasks.test.ts`：API 回 500 | 仍重新抓清單，並呼叫 `triggerCalendarReload` | 是 |
| AC51 | `TodayTasks.test.ts`：批次重新排程的回應有失敗清單 | 通知含失敗任務的名稱與原因 | 是 |
| AC51a | `TodayTasks.test.ts`：批次重新排程時 API 回 500 | 只有一個通知，含「重新排程沒有全部完成」、錯誤訊息與「請再按一次」 | 是 |
| AC51b | `TodayTasks.test.ts`：批次重新排程全部成功（2 個） | 通知含「已把 2 個任務放回排程清單」 | 是 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-21 | 新增需求 7a、AC5a 與測試對應 | 開發者決定精靈在任務清單載入失敗時改顯示「暫時無法載入任務」→ 需求 7a、AC5a；檢查過 AC2–AC5 不用改（載入成功時的行為不變） | 開發者 |
| 2026-11-21 | 「不做」新增：今日卡片不隨時間自動更新 | 開發者決定維持只在清單變動或重新整理時更新 →「不做」；檢查過 AC14–AC22、AC35 不用改（判斷規則不變，只是判斷的時間點） | 開發者 |
| 2026-11-21 | 測試對應的位置：AC10 改為 `backend/tests/unit/test_schedule_router.py`；AC28、AC30–AC33 的前端測試改為 `frontend/tests/composables/useTaskForm.test.ts` | 實作時發現 `TaskForm.actions.test.ts` 把 `useTaskForm` 整個 mock 掉，驗證不到 `PUT` 與通知；驗收條件本身不變 → 測試對應；檢查過其他 AC 的測試位置不用改 | 開發者 |

## 請你決定

無
