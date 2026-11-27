# E2E 補上任務管理與排程流程

- 狀態：已核准
- 等級：高風險（後端新增 `GOOGLE_API_BASE_URL`，決定 Google OAuth 的 refresh token 與 client secret 送到哪裡：改變「憑證只送到 Google」這項保證的條件）
- 規格審查：有（高風險一定做；這份內容在拆開前已和 [e2e-playwright](e2e-playwright.md) 一起審過 3 輪）
- 前提：[e2e-playwright](e2e-playwright.md) 與 [e2e-local-run](e2e-local-run.md) 的 PR 合併後才開始實作
- PR：[#192](https://github.com/Chen-Yihua/auto-scheduling-system/pull/192)

## 簡短說明
在 [e2e-playwright](e2e-playwright.md) 搭好的 E2E 環境上，補上兩條使用者流程：任務管理頁的新增、修改、刪除，以及排程頁的排程建議。排程要用到 Google 日曆，所以後端新增一個只給 E2E 用的環境變數，讓 E2E 把 Google 的請求導向假的伺服器。

## 背景
任務管理與排程是這個系統的核心流程，目前沒有 E2E。

- 排程建議 `POST /schedule/suggest` 先用 calendarList 找主要行事曆，再向 Google FreeBusy API 查空檔（`backend/routers/schedule.py:109-114`、`backend/services/google_calendar.py:101-120`）；有前一階段事件時另外讀取事件。排程頁打開時呼叫 `fetchGoogleCalendars`，後端會真的打 calendarList（`frontend/pages/schedule.vue:47-51`）。沒連 Google 日曆就排不出結果。
- 後端呼叫 Google 的網址寫死在 `backend/services/google_calendar_client.py`（calendarList、FreeBusy、事件的新增、讀取、刪除，`:9`、`:20`、`:36`、`:50`、`:59`）、`backend/services/google_oauth.py:19` 與 `backend/routers/google_calendar.py:51`（`https://oauth2.googleapis.com/token`）。後端沒有修改事件的呼叫。
- Google 日曆的 token 存在 MongoDB，以 Clerk 使用者 id 為 key，用 `SECRET_ENCRYPTION_KEY` 加密（`backend/crud/google_tokens.py:8-17`）。沒有給 `MONGO_URI`、`MONGO_DB` 時，後端的程式預設連開發用的資料庫（`backend/core/database.py:7-8`）。
- 新增任務時，只有缺優先度或時長才呼叫 Gemini 推斷（單一任務 `backend/routers/manual_task.py:146-156`）；回應的 `inferred_fields` 列出推斷出來的欄位。
- 排程頁同時讀排程偏好，`users` 文件還沒建立時後端回 404（`backend/crud/user.py:42-57`、`frontend/composables/useScheduleWizard.ts:104-130`）；[e2e-playwright](e2e-playwright.md) 的 setup project 會先建立。
- 排程頁的步驟精靈載入使用者全部可排程的任務，確認排序時送出全部任務的 id，後端遇到不認得的 id 回錯誤（`frontend/composables/useScheduleWizard.ts:145-157`、`:185-200`、`backend/crud/schedulable_items.py:150`）。所以同一個使用者的另一個測試同時新增或刪除任務，排程測試會失敗。

新增的環境變數 `GOOGLE_API_BASE_URL` 只給 E2E 用：沒設定時後端照舊連真的 Google，正式環境不設定，所以 Cloud Run 不加這個變數。這種「沒設定就連真的服務，測試時才指向假的伺服器」的變數是常見做法，例如 Google Cloud 的 `STORAGE_EMULATOR_HOST`。這個值在正式環境被設錯時，refresh token 與 client secret 會送到錯的地方；只有能改 Cloud Run 設定的人能設定它。

## 需求

### 假的 Google 日曆
1. 後端新增環境變數 `GOOGLE_API_BASE_URL`：有設定時，後端所有呼叫 Google 日曆 API 與 Google OAuth token endpoint 的請求都改送到這個網址；沒設定時照舊送到真的 Google。
2. E2E 啟動一個假的 Google 日曆伺服器（port 和開發環境不同），回應後端用到的 calendarList、FreeBusy、事件的新增、讀取、刪除、OAuth token refresh；FreeBusy 回應未來 7 天沒有忙碌時段；假伺服器記錄收到的請求。
3. setup project 在測試使用者底下放一筆假的 Google 日曆連線資料，讓排程頁與後端都認為測試使用者已連接 Google 日曆。
4. 寫入假連線資料的程式只連 `auto_scheduling_e2e`。

### 新增的使用者流程
5. 登入後的測試依序執行，不同時執行：它們共用同一個 Clerk 測試使用者。
6. 流程 a：使用者登入後，在任務管理頁新增一個任務，任務管理頁的清單出現這個任務。
7. 流程 a（續）：使用者修改這個任務，任務管理頁的清單顯示修改後的內容。
8. 流程 a（續）：使用者刪除這個任務，任務管理頁的清單不再出現這個任務。
9. 流程 a 建立任務時自己填優先度與時長，不靠 Gemini 推斷。
10. 流程 b：使用者登入後，在排程頁照步驟確認任務的截止日期與時長，排程頁顯示排程建議裡「這個任務排在什麼時間」。

## 不做
- 不處理：在排程頁按確認，把排程寫進 Google 日曆。開發者說的是「排出結果」，寫進日曆是另一個步驟，之後要的話另外加。
- 不處理：呼叫真的 Gemini。要花錢，回傳結果也不固定，測試會時好時壞。
- 不處理：用真的 Google 測試帳號。OAuth app 在測試模式時 refresh token 7 天就失效，CI 會定期壞掉。
- 不處理：在 Cloud Run 設定 `GOOGLE_API_BASE_URL`。正式環境不設定，沒設定時連真的 Google。
- 不處理：外部平台（GitHub、Jira、Moodle）與 Google 日曆的授權流程。要走真的第三方登入，不穩定。

## 假設
1. 流程 b 要用到的任務，由測試直接呼叫後端 API 建立，不經過任務管理頁的畫面：任務管理頁的畫面已經由流程 a 驗證，直接用 API 建立比較快也比較穩，一般 E2E 也這樣準備資料。
2. 每個測試建立的任務名稱帶有這次執行獨有的字串，用來在清單裡找到自己的任務。

## 驗收條件

| # | 需求 | 條件 |
|---|---|---|
| AC1 | 1 | 後端設定 `GOOGLE_API_BASE_URL=http://localhost:<port>` 時，calendarList、FreeBusy、事件的新增、讀取、刪除、OAuth token refresh 的請求都送到 `http://localhost:<port>`，路徑與沒設定時相同 |
| AC2 | 1 | 後端沒設定 `GOOGLE_API_BASE_URL` 時，上面這些請求照舊送到 `https://www.googleapis.com` 與 `https://oauth2.googleapis.com` |
| AC3 | 2、3 | 登入的測試使用者打開排程頁：排程頁不顯示「Google Calendar 未連接或授權已失效」 |
| AC4 | 4 | 不變條件（資料）：執行 E2E 後，開發用資料庫的 Google 日曆連線資料（`googleCalendarTokens`）沒有變 |
| AC5 | 5 | 登入後的測試一次只執行一個；流程 b 開始時，測試使用者只有流程 b 建立的那一個未排程任務 |
| AC6 | 6 | 流程 a：使用者在任務管理頁按「新增任務」，填名稱、優先度、時長後送出，任務管理頁的清單出現這個名稱的任務 |
| AC7 | 7 | 流程 a：使用者編輯 AC6 的任務，把名稱改掉後儲存，清單顯示新名稱，不再顯示舊名稱；重新載入後仍然顯示新名稱 |
| AC8 | 8 | 流程 a：使用者刪除這個任務，清單不再出現這個任務；重新載入後仍然不出現 |
| AC9 | 9 | 流程 a 建立任務時，後端回應的 `inferred_fields` 是空陣列 |
| AC10 | 10 | 流程 b：使用者打開排程頁，照「拖拉排序優先權」→「確認截止日期與時長」→「查看排程建議」的步驟走完，「查看排程建議」畫面顯示這個任務的名稱與排定的時間 |
| AC11 | 10 | 流程 b 執行期間，畫面沒有出現「讀不到上次的排程偏好，請重新填寫」與「排程偏好沒有存成功，下次要重新填」 |
| AC12 | 10 | 流程 b：從流程 b 開始到 AC10 結束，假的 Google 日曆伺服器沒有收到新增事件的請求（沒有寫進日曆） |

## 實作計畫

### 1. 後端：Google API 網址可以設定（需求 1）
- 新增一個讀 `GOOGLE_API_BASE_URL` 的地方（例如 `backend/services/google_api_urls.py`），提供 Calendar API 與 OAuth token endpoint 的網址；沒設定時回傳真的 Google 網址。
- `backend/services/google_calendar_client.py`、`backend/services/google_oauth.py`、`backend/routers/google_calendar.py` 改用這個地方的網址。
- 為什麼這樣做：只換呼叫外部服務的那一層，後端的排程計算、token 解密與更新都照真的跑。

### 2. 假的 Google 日曆伺服器（需求 2）
- `frontend/tests/e2e/support/fakeGoogle.ts`（或同等位置）：用 Node 內建 `http` 起一個伺服器，回應 calendarList（一個 `primary: true` 的行事曆）、FreeBusy（未來 7 天沒有忙碌時段）、OAuth token（固定的假 access token）、事件的新增、讀取、刪除；記錄收到的請求，提供一個只給測試用的路徑讓測試讀回（AC12）。
- `playwright.config.ts` 的 `webServer` 在後端之前啟動它，後端的環境變數加上 `GOOGLE_API_BASE_URL`。
- 它的輸出和另外 3 個伺服器相同（[e2e-local-run](e2e-local-run.md)）：本機存成 `e2e-logs/google.log`，每次覆寫，指令以非 0 結束時才印出；CI 不存檔、不印。
- 這個檔案不呼叫 `console.*`（[e2e-playwright](e2e-playwright.md) AC15）。

### 3. 假的 Google 連線資料（需求 3、4）
- 在 setup project 登入後，從瀏覽器的 `window.Clerk.user.id` 取得測試使用者的 Clerk id。
- 執行一支 Python 腳本（例如 `backend/scripts/e2e_seed_google_token.py`），用 `backend/crud/google_tokens.py` 的 `save_google_calendar_token` 寫入假的連線資料，不在 Node 重寫加密。
- E2E 的 `SECRET_ENCRYPTION_KEY` 改成寫在 `frontend/tests/e2e/support/e2eConfig.ts` 的固定測試用金鑰，不再每次執行產生：沿用伺服器時（[e2e-local-run](e2e-local-run.md)），另一次執行的 setup 才會和後端用同一把金鑰。它只加密 E2E 資料庫裡的假 token，不是機密。
- 腳本拿到的 `MONGO_URI`、`MONGO_DB`、`SECRET_ENCRYPTION_KEY` 和 E2E 後端相同，由 setup project 明確傳入，不依賴 `backend/core/database.py:7-8` 的預設值；腳本先確認 `MONGO_DB` 是 `auto_scheduling_e2e`，不是就結束、不寫入。
- CI 上這個子行程的 stdout、stderr 設成 `ignore`，失敗時只丟出「寫入假的 Google 連線資料失敗（結束碼 N）」。

### 4. E2E 測試
- `playwright.config.ts`：`workers: 1`、`fullyParallel: false`（需求 5）。
- `frontend/tests/e2e/tasks.signed-in.spec.ts`：流程 a。
- `frontend/tests/e2e/schedule.signed-in.spec.ts`：流程 b。開始前用 API 刪掉測試使用者所有任務，再建立一個帶截止日期、優先度、時長的任務（AC5）。

### 5. 完成前檢查
1. 後端的 unit 測試涵蓋 AC1、AC2 的每個網址。
2. `backend/.env.example` 列出 `GOOGLE_API_BASE_URL`，註解寫明只給 E2E 用、正式環境不設定。
3. Cloud Run 不加 `GOOGLE_API_BASE_URL`（例外於 CLAUDE.md「新增後端的環境變數要在 Cloud Run 加上」：開發者決定，理由見背景）；PR 描述寫明。
4. `docs/architecture.md`、`docs/api.md` 不用改：沒有新增服務、collection 或 endpoint。

### 考慮過、沒選的做法
- 用 `page.route` 在瀏覽器攔截排程 API：後端的排程完全沒跑到，和元件測試重疊。
- 用真的 Google 測試帳號：見「不做」。
- 讓測試平行執行、每個測試用不同的 Clerk 使用者：要多開幾個 Clerk 測試帳號與 secret，這次只有 4 個測試，依序執行就夠了。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1、AC2 | 後端 unit 測試（例如 `backend/tests/unit/test_google_api_urls.py`）：設定與不設定環境變數時，各個網址的完整字串 | 有設定時是 `http://localhost:<port>/calendar/v3/...` 與 `http://localhost:<port>/token`；沒設定時是真的 Google 網址 |
| AC3 | `schedule.signed-in.spec.ts` | 排程頁不出現「Google Calendar 未連接或授權已失效」 |
| AC4 | 手動：執行前後各查一次開發用資料庫 `googleCalendarTokens` 的文件；腳本的 unit 測試：`MONGO_DB` 不是 `auto_scheduling_e2e` 時 | 文件沒有變；腳本結束、沒有寫入 |
| AC5 | 讀 `playwright.config.ts` 的 `workers`；`schedule.signed-in.spec.ts` 開始時斷言任務清單 | `workers: 1`；只有一個任務 |
| AC6～AC8 | `tasks.signed-in.spec.ts` | 通過 |
| AC9 | `tasks.signed-in.spec.ts`：讀建立任務的回應 | `inferred_fields` 是 `[]` |
| AC10 | `schedule.signed-in.spec.ts` | 「查看排程建議」畫面出現任務名稱與時間 |
| AC11 | `schedule.signed-in.spec.ts`：每一步斷言沒有這兩段提示文字 | 通過 |
| AC12 | `schedule.signed-in.spec.ts`：讀假 Google 伺服器記錄的請求，只看流程 b 開始之後的（UI 模式開著時假伺服器會被沿用，記錄留著前幾次執行的請求） | 沒有新增事件的請求 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-27 | 前提加上 e2e-local-run；`SECRET_ENCRYPTION_KEY` 改成固定的測試用金鑰（實作計畫第 3 節）；假 Google 伺服器的輸出改成和另外 3 個伺服器相同（實作計畫第 2 節）；AC12 只看流程 b 開始之後的請求 | e2e-local-run 合併後可以沿用伺服器：每次執行產生的金鑰會和沿用的後端不同（開發者選固定金鑰，Q27 A）；伺服器輸出的做法已改（Q28 A）；沿用的假伺服器記錄留著前幾次的請求。檢查過其他 AC、假設與測試對應不用改 | 開發者 |

## 請你決定
無
