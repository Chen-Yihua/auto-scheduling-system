# 標題列改成首頁、任務管理、排程、分析 4 個頁面

- 狀態：已核准
- 等級：一般（只改前端的版面、導覽與頁面；不改後端、API、登入流程與資料，不碰高風險範圍）
- issue：#178
- PR：#180

## 簡短說明

標題列加上「首頁」「任務管理」「排程」「分析」4 個連結，把現在擠在首頁的卡片分到各自的頁面；任務管理頁改成能看出完成狀態、排程狀態與排程時間的任務清單。

## 背景

來源：[#178](https://github.com/Chen-Yihua/auto-scheduling-system/issues/178)。使用者打開首頁時，要找的資訊和功能散在同一頁的很多張卡片裡，也沒有導覽列可以切換到各功能頁。

現在的狀態（以 `main` 為準）：

- 首頁（`frontend/components/dashboard/Dashboard.vue:76-117`）是三欄版面。左欄由上到下是今日卡片、任務列表（最多 5 筆）、排程建議、Moodle、GitHub、Jira 卡片；中欄是 Google 行事曆；右欄是 Hacker News、LeetCode。左上角另有「立即同步外部平台」按鈕（函式 `Dashboard.vue:33-42`、按鈕 `:60-72`），同時同步 GitHub、Jira、Moodle。
- 標題列（`frontend/components/header/AppHeader.vue`）只有歡迎文字、深淺色切換、連到 `/productivity` 的「工作效率」圖示、新增任務按鈕、登入或帳號設定。
- 新增、編輯任務的視窗寫在任務列表元件 `frontend/components/tasks/TaskForm.vue:172` 裡。標題列的新增任務按鈕、今日卡片的「編輯」都透過共用的 `showEditModal` 打開它（`AppHeader.vue:11`、`TodayTasks.vue:58`）。只有首頁和 `/tasks` 放了 `TaskForm`，所以在 `/schedule`、`/productivity`、`/github`、`/jira`、`/moodle` 按標題列的新增任務按鈕，畫面沒有反應。
- 今日卡片編輯手動任務時，從 `useTaskForm` 的 `all_tasks` 找出完整的任務資料（`TodayTasks.vue:51-54`）；`all_tasks` 由 `TaskForm` 掛載時讀進來（`TaskForm.vue:161-164`）。首頁拿掉 `TaskForm` 後，沒有人讀 `all_tasks`，今日卡片的編輯會找不到任務。
- 任務列表每一列顯示來源圖示、名稱、主任務的階段進度、優先級、截止日，以及「展開階段」「編輯」「標記完成」；外部任務按一下會開啟原網頁（`TaskForm.vue:461-563`）。看不到完成狀態、排程狀態與排程時間。
- 排程的流程：首頁排程建議卡片按「產生排程建議」→ 進入 `/schedule` 排程精靈（`ScheduleSuggestion.vue:21`）→ 精靈完成後產生建議並導回 `/`（`schedule.vue:215-224`）→ 在首頁的排程建議卡片按「確認排程並寫入 Calendar」。排程建議的結果是共用狀態（`useSchedule.ts:9`），換頁後還在。
- 排程精靈進入時會向 Google 查已排程任務的日曆事件有沒有被刪掉（`schedule.vue:46-60`），不會同步 GitHub、Jira、Moodle。
- 任務資料（`GET /schedule/tasks`，型別 `frontend/types/schedulableTask.ts`）：`status` 手動任務有 `To Do`、`In Progress`、`Done`，外部任務只有 `To Do`、`Done`；`calendar_event_id` 有值表示已寫進 Google 日曆；`scheduled_start`、`scheduled_end` 是確認排程時存下的時段，PR #179 之前確認的排程沒有這兩個值。
- 「已逾期」的判斷在 `frontend/utils/todayTasks.ts:26-31` 的 `isOverdue`（沒有 export）。

## 需求

### 標題列

1. 標題列有「首頁」（`/`）、「任務管理」（`/tasks`）、「排程」（`/schedule`）、「分析」（`/productivity`）4 個連結。
2. 目前所在頁面的連結有標示。`/schedule/wizard` 算在「排程」。
3. 「分析」連結取代原本的「工作效率」圖示按鈕。
4. 標題列的新增任務按鈕在每一個有標題列的頁面都能打開新增任務的視窗。
5. 標題列其他現有的元素（歡迎文字、深淺色切換、登入、帳號設定）保留。

### 首頁 `/`

6. 已登入時，首頁只顯示今日卡片、Google 行事曆、Hacker News、LeetCode。
7. 首頁不再顯示任務列表、排程建議、Moodle、GitHub、Jira 卡片，也不再顯示「立即同步外部平台」按鈕。
8. 訪客打開首頁時，今日卡片與 Google 行事曆的位置各顯示一張登入提示卡，Hacker News、LeetCode 照常顯示。今日卡片位置的提示卡標題是「今日」，文字是「登入後即可查看今天的任務」；行事曆沿用現在的提示卡。
9. 今日卡片的「編輯」在首頁照常能打開手動任務的編輯視窗。

### 任務管理 `/tasks`

10. 已登入時，任務管理頁列出所有任務（所有來源），每一列有名稱、截止日、優先級、完成狀態、排程狀態、排程時間 6 欄。
11. 完成狀態顯示「未開始」（`To Do`）、「進行中」（`In Progress`）、「已完成」（`Done`）。
12. 排程狀態顯示「已排程」（有 `calendar_event_id`）或「未排程」（沒有）。
13. 排程時間顯示 `scheduled_start`–`scheduled_end`；沒有時段時顯示「—」。
14. 優先級沒有值時顯示「—」；截止日沒有值時顯示「無期限」（沿用現在的列表）。
15. 主任務（有子任務的任務）的排程狀態與排程時間都顯示「—」。
16. 已逾期的任務（定義見術語表「已逾期」）在名稱旁顯示「已逾期」標籤。主任務沒有自己的排程時段，所以只依自己的截止日判斷。
17. 外部任務在名稱旁顯示來源標籤（「GitHub」「Jira」「Moodle」）；手動任務不顯示來源標籤。來源標籤取代現在每一列最前面的來源圖示。
18. 保留現在名稱旁的「進度 k/N」（主任務）與「階段 k/N」（階段）文字。
19. 保留現有的操作：主任務的「展開階段／收合階段」、手動任務與階段的「編輯」、「標記完成／取消完成」（主任務不能手動標記）、按外部任務那一列開啟原網頁。
20. 展開主任務後，各階段顯示在主任務下面，欄位與第 10–17 條相同。
21. 任務列表卡片的右上角有「立即同步外部平台」按鈕（顯示的條件見第 23 條），按下後同時同步 GitHub、Jira、Moodle，一個平台失敗不影響其他平台。
22. 「立即同步外部平台」完成後，任務管理頁重新讀取任務列表。
23. 「立即同步外部平台」按鈕與未連結提示依下面順序判斷，符合一條就停：
   1. 帳號資料（`GET /users/me/linked-accounts/`）還在讀取時，按鈕與提示都不顯示。
   2. 帳號資料讀取失敗時，顯示按鈕，不顯示提示（不知道連結狀態時，使用者仍可同步）。
   3. GitHub、Jira、Moodle 都沒有金鑰時，不顯示按鈕；任務列表最上方顯示一行提示「尚未連結外部平台，請前往 **帳號設定 → 金鑰** 新增」（寫法與首頁行事曆未連接的提示相同），手動任務照常列在提示下面。
   4. 其他情況（至少一個平台有金鑰，包括「憑證無法讀取、要重新連結」的平台）顯示按鈕，不顯示提示。
24. 沒有任務時的說明改成「目前沒有任務，點擊標題列的新增任務按鈕新增一個吧」（新增任務按鈕在標題列，卡片右上角是同步按鈕）。
25. 訪客打開任務管理頁時，顯示「登入後即可查看」的提示卡（沿用現在的提示卡）。

### 排程 `/schedule` 與排程精靈 `/schedule/wizard`

26. 「排程」頁 `/schedule` 顯示排程建議卡片（現在首頁的 `ScheduleSuggestion`）。
27. 排程精靈的網址改成 `/schedule/wizard`。
28. 排程建議卡片的「產生排程建議」「重新產生」進入 `/schedule/wizard`。
29. 排程精靈按「完成」或「取消」後，回到 `/schedule`。
30. 排程精靈在沒有可排程的任務、或任務載入失敗時顯示的「回首頁」按鈕，照舊回到首頁 `/`（畫面上的說明指向首頁的今日卡片）。
31. 排程精靈的內容與行為不變，包括進入時的 Google 日曆已刪除事件檢查。
32. 訪客打開 `/schedule` 時，顯示「登入後即可查看排程建議」的提示卡。

### 分析 `/productivity`

33. 分析頁的內容與功能不變。

### 其他頁面

34. `/tasks`、`/schedule`、`/productivity` 拿掉左上角的「返回主頁」連結；`/github`、`/jira`、`/moodle` 保留。

## 不做

- 任務管理頁的排序、篩選：另開 issue。
- 進入排程頁或排程精靈時自動同步 GitHub、Jira、Moodle。
- 使用者在 Google 刪除或拖動事件後，首頁行事曆或系統存的排程時段沒有自動更新的問題（排程時段的同步由 #177 處理）。
- `/github`、`/jira`、`/moodle` 頁面、帳號設定裡的平台連結入口、後端與已同步的資料都不改。這 3 頁在畫面上不再有入口，要直接輸入網址。
- 不改後端、API 與 `docs/api.md`。
- 使用者在任務管理頁打開帳號設定新增或刪除金鑰後，未連結提示與同步按鈕不會馬上更新，要重新整理或換頁才會重新判斷（和首頁行事曆「打開頁面時判斷一次」的做法相同）。

## 假設

1. 標題列在窄螢幕（手機寬度）時，4 個連結可以換行或橫向排列，不另外做收合選單；之後覺得擠再開 issue。依據：issue 沒有提到手機版，現在的標題列也沒有收合選單。
2. 首頁維持三欄版面：左欄今日卡片、中欄行事曆、右欄 Hacker News 與 LeetCode。依據：只拿掉卡片，不重新設計版面。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 標題列有「首頁」「任務管理」「排程」「分析」4 個連結，分別連到 `/`、`/tasks`、`/schedule`、`/productivity` |
| AC2 | 在 `/`、`/tasks`、`/schedule`、`/schedule/wizard`、`/productivity` 時，對應的連結有「目前頁面」的標示（`aria-current="page"`），其他 3 個沒有 |
| AC3 | 標題列不再有「工作效率」圖示按鈕 |
| AC4 | 已登入時，在 `/schedule`（或 `/productivity`）按標題列的新增任務按鈕，新增任務的視窗打開 |
| AC5 | 已登入時，首頁只掛載今日卡片、Google 行事曆、Hacker News、LeetCode 4 張卡片 |
| AC6 | 首頁沒有「立即同步外部平台」按鈕 |
| AC7 | 訪客打開首頁時，今日卡片與行事曆的位置各是一張登入提示卡，Hacker News、LeetCode 照常顯示，而且不呼叫需要登入的 API |
| AC8 | 已登入時，在首頁按今日卡片裡手動任務的「編輯」，編輯視窗打開並帶入那筆任務的資料 |
| AC9 | 任務管理頁每一列顯示名稱、截止日、優先級、完成狀態、排程狀態、排程時間 |
| AC10 | 優先級沒有值的任務（包括主任務）優先級欄顯示「—」；沒有截止日的任務截止日欄顯示「無期限」 |
| AC11 | 完成狀態依 `status` 顯示：`To Do` →「未開始」、`In Progress` →「進行中」、`Done` →「已完成」 |
| AC12 | 有 `calendar_event_id` 的任務排程狀態顯示「已排程」，沒有的顯示「未排程」 |
| AC13 | 有 `scheduled_start`、`scheduled_end` 的任務排程時間顯示兩者的時段；沒有時段的任務（未排程，或已排程但是 PR #179 之前的舊資料）顯示「—」 |
| AC14 | 主任務的排程狀態與排程時間顯示「—」 |
| AC15 | 還沒完成、截止日那一天已結束的任務，名稱旁顯示「已逾期」標籤 |
| AC16 | 還沒完成、排程時段結束時間已過的任務，名稱旁顯示「已逾期」標籤 |
| AC17 | 已完成的任務即使截止日已過，也不顯示「已逾期」標籤 |
| AC18 | 外部任務名稱旁顯示對應的來源標籤（「GitHub」「Jira」「Moodle」）；手動任務沒有來源標籤 |
| AC19 | 任務管理頁保留：主任務的「展開階段／收合階段」；手動任務與階段的「編輯」；「標記完成／取消完成」；主任務的標記完成按鈕停用；按外部任務那一列開啟原網頁 |
| AC20 | 主任務名稱旁顯示「進度 k/N」，階段名稱旁顯示「階段 k/N」 |
| AC21 | 已登入、沒有任何任務時，任務管理頁顯示「目前沒有任務，點擊標題列的新增任務按鈕新增一個吧」 |
| AC22 | 展開主任務後，各階段顯示在主任務下面，各自有 AC9 的 6 個欄位 |
| AC23 | 至少一個平台有金鑰（或帳號資料讀取失敗）時，在任務管理頁按任務列表卡片右上角的「立即同步外部平台」，同時呼叫 GitHub、Jira、Moodle 的同步，其中一個失敗不影響其他平台 |
| AC24 | 「立即同步外部平台」完成後（包括部分平台失敗），任務管理頁重新讀取一次任務列表 |
| AC25 | 帳號資料還在讀取時，任務管理頁沒有「立即同步外部平台」按鈕，也沒有未連結提示 |
| AC26 | 帳號資料讀取失敗時，任務管理頁顯示「立即同步外部平台」按鈕，沒有未連結提示 |
| AC27 | GitHub、Jira、Moodle 都沒有金鑰時，任務管理頁沒有「立即同步外部平台」按鈕，任務列表最上方顯示「尚未連結外部平台，請前往 帳號設定 → 金鑰 新增」，手動任務照常列在下面 |
| AC28 | 只有一個平台有金鑰（或只有一個平台是「要重新連結」）時，任務管理頁顯示「立即同步外部平台」按鈕，沒有未連結提示 |
| AC29 | 訪客打開任務管理頁時，顯示任務列表的登入提示卡，不呼叫需要登入的 API |
| AC30 | 已登入時，`/schedule` 顯示排程建議卡片 |
| AC31 | 在 `/schedule` 按「產生排程建議」（或「重新產生」），進入 `/schedule/wizard` |
| AC32 | 在排程精靈按「完成」，產生排程建議後回到 `/schedule`，排程建議卡片顯示這次的結果 |
| AC33 | 在排程精靈按「取消」，回到 `/schedule` |
| AC34 | 在排程精靈沒有可排程的任務或任務載入失敗時，按「回首頁」，回到 `/` |
| AC35 | 訪客打開 `/schedule` 時，顯示排程建議的登入提示卡 |
| AC36 | 排程精靈現有的步驟與檢查（包括 Google 日曆已刪除事件的步驟）行為不變：現有的 `tests/pages/schedule.test.ts` 除了 AC32、AC33 的網址以外不改斷言仍全部通過 |
| AC37 | 分析頁的內容不變：現有的 `tests/pages/productivity.test.ts` 不改斷言仍全部通過 |
| AC38 | `/tasks`、`/schedule`、`/productivity` 沒有「返回主頁」連結；`/github`、`/jira`、`/moodle` 仍有 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中 | 沿用各卡片現有的載入狀態；首頁沿用「Clerk 初始化完成前不畫卡片」；任務管理頁的帳號資料載入由 AC25 涵蓋 |
| 空資料 | 任務管理頁由 AC21 涵蓋；排程建議卡片沿用現有的空狀態 |
| 失敗 | 讀任務、同步失敗沿用現有的錯誤提示（`useSchedulableTasks`、`usePlatformItems` 的 toast），這次不改 |
| 資料處理與一致性、同時操作 | 只改畫面與導覽，不改任何寫入資料的請求 |
| 安全性 | 不新增輸入、不改登入驗證；訪客不呼叫需要登入的 API 由 AC7、AC29 守住 |

## 實作計畫

1. **把任務編輯視窗從 `TaskForm.vue` 拆出來**：新增 `frontend/components/tasks/TaskEditModal.vue`，搬入 `TaskForm.vue` 的 `UModal` 與表單，以及表單用到的處理函式。這個元件在已登入時掛載後讀取 `all_tasks`（`fetchTasks`）。放在 `AppHeader.vue` 裡，讓每一個有標題列的頁面都有這個視窗（需求 4、9）。`TaskForm.vue` 只留列表。
   - 為什麼放在 `AppHeader`：視窗跟著開啟它的按鈕放；所有頁面都放了標題列，之後新增沒有標題列的頁面時，也不會多掛一個視窗。
   - 讀 `all_tasks` 的責任跟著視窗搬，今日卡片的「編輯」才不會依賴頁面上有沒有任務列表。
2. **標題列**：`AppHeader.vue` 左側加上 4 個連結，用 Nuxt UI 的 `UNavigationMenu`（或 `NuxtLink` 加 `aria-current`），依目前路由標示所在頁面；`/schedule/wizard` 算「排程」。拿掉「工作效率」圖示按鈕。
3. **首頁**：`Dashboard.vue` 左欄只留 `TodayTasks`，拿掉 `TaskForm`、`ScheduleSuggestion`、3 個平台卡片、對應的訪客提示卡、「立即同步外部平台」按鈕，以及只為它們用到的 `usePlatformItems` 呼叫。訪客的左欄改成今日卡片的登入提示卡。
4. **任務管理頁**：改寫 `TaskForm.vue` 的列表成 6 欄的表格（用 Nuxt UI `UTable` 或現有的列樣式加上欄位，實作者依可讀性決定，但每一列都要有 AC9 的 6 個值）。拿掉 `limit` prop 與「查看全部」連結（首頁不再用）。
   - 「已逾期」：把 `utils/todayTasks.ts` 的 `isOverdue` export 出來，任務管理頁與今日卡片共用，判斷才會一致。
   - 完成狀態用 `utils/labels.ts` 既有的 `taskStatusLabels`，把 `To Do` 的「待辦」改成「未開始」（目前程式沒有用到這組對照，只有 `tests/utils/labels.test.ts:14` 要跟著改）；排程狀態的文字也放在 `utils/labels.ts`。
   - 來源標籤用 `utils/labels.ts` 現有的 `sourceLabel`。
   - 「立即同步外部平台」從 `Dashboard.vue` 搬到 `TaskForm.vue` 卡片標題的右側，沿用 `usePlatformItems` 的 `syncNow` 與 `Promise.allSettled`，完成後呼叫 `fetchSchedulableTasks()`。
   - 按鈕與未連結提示（需求 23）：`TaskForm.vue` 掛載後呼叫 `useLinkedAccount` 的 `fetchKeys`，依結果判斷；「有金鑰」與「要重新連結」的判斷沿用 `usePlatformItems` 與 `/productivity` 的寫法（`k.value || k.needsReauth`）。提示的樣式照 `GoogleCalendarEmbed.vue` 未連接的提示。
5. **排程**：
   - 把現在的 `pages/schedule.vue` 搬到 `pages/schedule/wizard.vue`，完成與取消的 `router.push('/')` 改成 `router.push('/schedule')`。「回首頁」按鈕（現在呼叫 `cancel`）改成呼叫另一個回 `/` 的函式。
   - 新增 `pages/schedule/index.vue`：標題列＋排程建議卡片；訪客顯示 `LoginRequiredCard`。
   - `ScheduleSuggestion.vue` 的 `router.push('/schedule')` 改成 `/schedule/wizard`；`ScheduleSuggestion.vue` 註解「導回這裡」與 `composables/useSchedule.ts:9` 註解「導回首頁」改成回到排程頁。
6. **其他頁面**：`pages/tasks.vue`、`pages/productivity.vue` 拿掉「返回主頁」連結。
7. **文件**：`docs/glossary.md` 照 `issue-178-nav-pages-glossary.md` 更新「今日卡片」並新增術語。`docs/architecture.md` 有提到前端頁面或首頁卡片的地方，照新的頁面分工更新（沒有提到就不改）。
8. **測試**：
   - 改寫既有的 `tests/components/AppHeader.test.ts`（AC1–AC4）。
   - 改寫 `tests/components/Dashboard.test.ts` 的版面測試（AC5–AC7），`Dashboard.test.ts:274`、`:296` 跟著平台卡片刪除；`:284`（立即同步）刪除，由 `Dashboard.sync.test.ts:85` 改寫的測試涵蓋 AC23、AC24。
   - `tests/components/Dashboard.sync.test.ts:85` 改寫成任務管理頁的立即同步測試（AC23）；`:112` 測首頁 GitHub 卡片，跟著卡片移除。
   - `tests/components/TaskForm.test.ts`、`TaskForm.actions.test.ts` 中屬於編輯視窗的測試搬到 `TaskEditModal` 的測試檔，斷言不改；列表的測試補 AC9–AC28。
   - `tests/pages/schedule.test.ts` 改成測 `pages/schedule/wizard.vue`，只改網址相關的斷言（AC32、AC33、AC36）；新增 `/schedule` 頁的測試（AC30、AC35）。
   - `tests/components/ScheduleSuggestion.test.ts` 的 `/schedule` 改成 `/schedule/wizard`（AC31）。
   - `tests/e2e/dashboard.e2e.ts` 的訪客版面測試照新版面改（AC7）。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | `AppHeader.test.ts`（既有檔案）：掛載標題列，找 4 個連結 | 文字與 `href` 依序是首頁 `/`、任務管理 `/tasks`、排程 `/schedule`、分析 `/productivity` |
| AC2 | `AppHeader.test.ts`：路由分別設成 5 個網址 | 只有對應的連結有 `aria-current="page"`；`/schedule/wizard` 標在「排程」 |
| AC3 | `AppHeader.test.ts` | 找不到 `aria-label="工作效率"` 的按鈕 |
| AC4 | `AppHeader.test.ts`：已登入，按新增任務按鈕 | `TaskEditModal` 的視窗打開（`showEditModal` 為 true 且視窗內容出現）；不依賴頁面上有沒有 `TaskForm` |
| AC5 | `Dashboard.test.ts`：已登入 | 只找到 `TodayTasks`、`GoogleCalendarEmbed`、`News`、`Leetcode`；找不到 `TaskForm`、`ScheduleSuggestion`、3 個平台卡片 |
| AC6 | `Dashboard.test.ts` | 找不到 `data-testid="dashboard-sync-now"` |
| AC7 | `Dashboard.test.ts`：訪客；`dashboard.e2e.ts` 訪客版面（改等「登入後即可查看今天的任務」） | 2 張登入提示卡（「今日」、Google 行事曆）＋ News、Leetcode；沒有呼叫需要登入的 API |
| AC8 | `TaskEditModal` 或 `TodayTasks` 的測試：已登入，視窗掛載後按今日卡片手動任務的「編輯」 | `all_tasks` 已讀取，表單帶入那筆任務的名稱 |
| AC9 | `TaskForm.test.ts`：一筆手動任務 | 那一列有名稱、截止日、優先級、完成狀態、排程狀態、排程時間 |
| AC10 | `TaskForm.test.ts`：一筆主任務、一筆沒有優先級也沒有截止日的手動任務 | 兩筆的優先級欄是「—」；第二筆的截止日欄是「無期限」 |
| AC11 | `TaskForm.test.ts`：3 筆任務 status 分別是 `To Do`、`In Progress`、`Done` | 依序顯示「未開始」「進行中」「已完成」 |
| AC12 | `TaskForm.test.ts`：一筆有 `calendar_event_id`、一筆沒有 | 依序顯示「已排程」「未排程」 |
| AC13 | `TaskForm.test.ts`：一筆有時段、一筆已排程但沒有時段、一筆未排程 | 第一筆顯示時段的開始與結束時間，第二、三筆顯示「—」 |
| AC14 | `TaskForm.test.ts`：一筆主任務 | 排程狀態與排程時間都是「—」 |
| AC15 | `todayTasks` 的 `isOverdue` 單元測試＋`TaskForm.test.ts`：固定現在時間，一筆未完成、截止日是昨天的任務，以及一筆未完成、截止日是昨天的主任務 | 兩筆名稱旁都有「已逾期」 |
| AC16 | 同上：一筆未完成、`scheduled_end` 是一小時前、截止日是明天 | 名稱旁有「已逾期」 |
| AC17 | 同上：一筆 `Done`、截止日是昨天 | 沒有「已逾期」 |
| AC18 | `TaskForm.test.ts`：手動、GitHub、Jira、Moodle 各一筆 | 外部任務依序有「GitHub」「Jira」「Moodle」標籤，手動任務沒有來源標籤 |
| AC19 | `TaskForm.test.ts`、`TaskForm.actions.test.ts` 現有的展開、編輯按鈕、標記完成、開啟原網頁測試保留（只改找元素的方式以配合表格）；測 Modal 與 `fetchTasks` 的測試（`TaskForm.test.ts:170`、`:350`、`TaskForm.actions.test.ts:128-205`）搬到 `TaskEditModal` 的測試檔，斷言不改；`TaskForm.actions.test.ts:113` 拆成兩半：「使用者出現才讀 `all_tasks`」搬到 `TaskEditModal`，「使用者出現才讀任務列表」留在 `TaskForm`；`:252` 拆成兩半：按列表的「編輯」呼叫 `startEditTask` 留在 `TaskForm`，視窗帶入資料搬到 `TaskEditModal`；測 `limit` 與「查看全部」的 `:188`、`:201`、`:315` 刪除 | 保留與搬移的測試都通過 |
| AC20 | `TaskForm.test.ts:282`（既有） | 斷言不改仍通過 |
| AC21 | `TaskForm.test.ts`：沒有任務 | 顯示新的說明文字 |
| AC22 | `TaskForm.test.ts`：一筆主任務＋2 個階段，按「展開階段」 | 2 個階段出現在主任務下面，各有 6 個欄位 |
| AC23 | 由 `Dashboard.sync.test.ts:85` 改寫成任務管理頁的測試（接真的 `usePlatformItems`）：帳號資料 3 個平台都有金鑰，按「立即同步外部平台」，Jira 的同步失敗 | GitHub、Jira、Moodle 的同步各呼叫一次；GitHub、Moodle 的同步仍完成；只跳一則 Jira 的錯誤訊息 |
| AC24 | 同上 | 同步結束後 `fetchSchedulableTasks` 再被呼叫一次 |
| AC25 | `TaskForm.test.ts`：帳號資料的請求還沒回來 | 找不到同步按鈕，也找不到未連結提示 |
| AC26 | `TaskForm.test.ts`：帳號資料的請求失敗 | 有同步按鈕，沒有未連結提示 |
| AC27 | `TaskForm.test.ts`：帳號資料 3 個平台都沒有金鑰，另有一筆手動任務 | 沒有同步按鈕；任務列表最上方有未連結提示；手動任務那一列在提示下面 |
| AC28 | `TaskForm.test.ts`：分兩個案例，(a) 只有 GitHub 有金鑰，(b) 只有 Moodle 是 `needs_reauth` | 兩個案例都有同步按鈕，沒有未連結提示 |
| AC29 | `tests/pages/tasks.test.ts`（新增）：訪客 | 顯示「任務列表」登入提示卡，沒有掛載 `TaskForm`、沒有呼叫需要登入的 API |
| AC30 | `tests/pages/schedule-index.test.ts`（新增）：已登入 | 掛載 `ScheduleSuggestion` |
| AC31 | `ScheduleSuggestion.test.ts` 現有兩個導向測試 | `router.push` 收到 `/schedule/wizard` |
| AC32 | `schedule.test.ts`（改測 `schedule/wizard.vue`）現有的完成測試 | 先呼叫 `fetchScheduleSuggestion`，再 `router.push('/schedule')` |
| AC33 | 同上的取消測試 | `router.push('/schedule')` |
| AC34 | `schedule.test.ts:237-249`、`:277-291`（既有） | 仍斷言 `router.push('/')`，不改 |
| AC35 | `schedule-index.test.ts`：訪客 | 顯示排程建議的登入提示卡，沒有掛載 `ScheduleSuggestion` |
| AC36 | `schedule.test.ts` 其他測試 | 除了網址斷言，其他斷言不改仍通過 |
| AC37 | `productivity.test.ts` | 斷言不改仍通過 |
| AC38 | 手動：依序打開 `/tasks`、`/schedule`、`/productivity`、`/github`、`/jira`、`/moodle` | 前 3 頁沒有「返回主頁」，後 3 頁有 |
| 全部 | 手動：已登入，逐一點過標題列 4 個連結，在每一頁按新增任務按鈕 | 每頁內容符合需求，新增任務視窗都能打開 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
