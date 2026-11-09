# 全站 API 狀態碼盤點與設計原則

- 狀態：已核准
- 等級：標準（這次不改程式碼，產出盤點、ADR 與分階段計畫；ADR 是之後所有 API 的狀態碼規則，屬於「改定義規則的文件裡的規則」。實際修改在後續各階段的 issue 另外判斷等級）
- issue：#62
- PR：#（待開）

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/62

狀態碼是各功能各自決定的，前端只靠狀態碼判斷畫面，結果顯示錯的畫面；外部服務的暫時失敗也可能被當成程式錯誤。例如使用者已經連接 Google，Google 回 403 時畫面卻顯示「尚未連接」（#59）。

### 目前的錯誤處理架構

- services、crud、platforms 丟 `backend/core/errors.py` 的 `AppError`，由 `backend/core/exception_handlers.py:25` 的 `_STATUS_BY_ERROR` 轉成狀態碼：`InvalidRequestError` 400、`ReauthRequiredError` 401、`AccessDeniedError` 403、`NotFoundError` 404、`ConflictError` 409、`ConfigurationError` 500、`ExternalServiceError` 502。資料庫連不上 503，其他資料庫錯誤與未預期的例外 500（`exception_handlers.py:41-48`、`:56-82`）。
- router 另外直接丟 `HTTPException`，自己決定狀態碼：`routers/user.py`、`routers/linked_account.py:49`、`routers/google_calendar.py:45-55`、`routers/schedule.py:116`、`:155`、`routers/pr_review_webhook.py:56-62`、`platforms/router.py:40-64`。
- 沒帶或無效的 Clerk JWT 由 `ClerkHTTPBearer(auto_error=True)` 回 403（`core/security.py:20`），`docs/api.md:3` 也寫 403。
- 只有限流有機器可讀的 `error_code`（`core/rate_limit.py:41-44` 的 `RATE_LIMITED`）。其他錯誤回應只有 `detail`；422 的 `detail` 是陣列。
- `httpx` 的逾時是 `RequestError` 的子類別，所有外部服務的逾時和連不上一起歸成 502。

### 前端怎麼判斷

`frontend/utils/errorMessages.ts` 除了限流以外只看狀態碼：

| 函式 | 判斷 | 用在 |
|---|---|---|
| `isNotLinkedError` | 400 → 尚未連結（不顯示錯誤） | `composables/useGoogleCalendar.ts:81`、`composables/useSchedule.ts:51` |
| `isAuthError` | 401 → 第三方憑證失效，請重新連結 | `useGoogleCalendar.ts:83`、`useSchedule.ts:56`、`usePlatformItems.ts:87`、`useTaskForm.ts:178` |
| `isAlreadyLinkedError` | 409 → 已綁定過 | `useLinkedAccount.ts:222` |
| `isSuggestionExpiredError` | 409 → 排程建議已過期 | `useSchedule.ts:108` |
| `getFriendlyErrorTitle` | 429 或 `RATE_LIMITED` → 請求太頻繁 | 各 composable |

`composables/useUserSync.ts:14-17` 另外依狀態碼顯示文字：401 或 403 是登入驗證失敗，503 是資料庫暫時不能用；`:77` 把註冊時的 409 當成已註冊。

### 全站盤點

所有需要登入的 endpoint 另外可能回：403（沒帶或無效的 JWT；抓 Clerk JWKS 失敗也是 403，見 P13）、422（schema 驗證失敗，回應帶 `input`，見 P14）、500（未預期的例外；Redis 故障也是 500，見 P18）、503（資料庫連不上）；有限流的回 429。下表只列各 endpoint 自己的情況。「建議」欄依 ADR 0011 的對照表；問題編號見下一節。

| Endpoint | 目前的狀態碼與觸發情境 | 前端怎麼處理 | 建議 | 問題 |
|---|---|---|---|---|
| `GET /users/me` | 404 使用者不存在（`routers/user.py:41`） | `useUserSync` 進入註冊流程 | 404 `NOT_FOUND` | — |
| `POST /users/` | 409 已註冊（`routers/user.py:54`、`crud/user.py:13`） | `useUserSync.ts:77` 當成功 | 409 `ALREADY_EXISTS` | — |
| `PUT /users/me` | 404 使用者不存在，**或沒有要改的欄位**（`crud/user.py:32-33`、`:38-39`） | 顯示錯誤 | 沒有要改的欄位 400 `INVALID_REQUEST` | P9 |
| `DELETE /users/me` | 404 使用者不存在（`routers/user.py:75`） | 顯示錯誤 | 404 `NOT_FOUND` | — |
| `POST /users/webhook/clerk` | 401 簽章錯誤或沒設定密鑰（`routers/user.py:23-32`）；400 payload 不是 JSON 或缺 id（`:98`、`:101`、`:112`） | 無（Clerk 呼叫） | 401 `INVALID_WEBHOOK_SIGNATURE`（沒設定密鑰是例外，見 ADR）；400 `INVALID_REQUEST` | — |
| `GET /users/me/linked-accounts/` | **任何一個帳號的憑證解不開，整個清單 500**（`crud/linked_account.py:21`、`:55`；`core/crypto.py:26-27` 丟 `ValueError`） | 顯示錯誤 | 200，解不開的帳號不顯示憑證並標示要重新連結 | P7 |
| `POST /users/me/linked-accounts/` | 400 不支援的平台、缺欄位（`crud/linked_account.py:35-39`）；409 已綁定（`:48`）；驗證憑證時：GitHub、Jira 回 401 → 401（`platforms/github.py:100`、`platforms/jira.py:107`），**其他非 200（含 5xx、429、Jira 網域回 404）→ 403**（`github.py:102`、`jira.py:109`），連不上或逾時 → 502（`github.py:94-97`、`jira.py:101-104`）；Moodle 登入後網址不是 `/my/` 就當成帳密錯 → 401（`platforms/moodle.py:53-55`、`:186`），WebDriver 錯誤 → 502（`:189`） | 409 顯示已綁定，其他一律顯示「儲存失敗」，不顯示 `detail`（`useLinkedAccount.ts:219-227`） | 憑證被拒 400 `INVALID_CREDENTIALS`；Jira 網域錯 400 `INVALID_PLATFORM_DOMAIN`；對方 5xx 502、逾時 504、限流 503 | P5、P6、P16 |
| `PATCH /users/me/linked-accounts/{platform}` | 404 帳號不存在，**或沒有可更新的欄位**（`routers/linked_account.py:49`、`crud/linked_account.py:64-66`）；改到憑證時同 POST 的驗證；只改 Jira 網域或 Moodle 帳號時用已存的憑證驗證，**解不開回 500**（`platforms/jira.py:161-167`、`platforms/moodle.py:200-206`） | 同 POST | 沒有可更新的欄位 400 `INVALID_REQUEST`；驗證被拒一律 400 `INVALID_CREDENTIALS`；解不開 409 `REAUTH_REQUIRED` | P5、P6、P7、P9 |
| `DELETE /users/me/linked-accounts/{platform}` | 404 帳號不存在（`crud/linked_account.py:84`） | 顯示錯誤 | 404 `NOT_FOUND` | — |
| `GET /github/issues`、`/jira/issues`、`/moodle/assignments` | 400 未連結（`platforms/router.py:40`、`:48`）；**500 憑證解密失敗**（`:46`）；**GitHub、Jira 回 400、401、403、404 一律當成憑證失效**（`platforms/github.py:20`、`:55-58`；`platforms/jira.py:18`、`:56-60`），沒有舊資料時 401（`platforms/router.py:58`），有舊資料時 200 加 `X-Auth-Error`（`:68-69`）；GitHub 用 403 回報的限流也算在內；外部服務失敗 502（`:61`）；其他例外 500（`:64`）；**Moodle 登入後網址不是 `/my/` 一律當成憑證失效**（`platforms/moodle.py:51-55`、`:71-72`），沒有舊資料 401、有舊資料 `X-Auth-Error`；Moodle 的快取讀寫遇到 Redis 故障 500（`core/cache.py:27`、`:43`） | `usePlatformItems.ts:87` 401 顯示要重新連結 | 未連結 409 `NOT_LINKED`；解密失敗、真的憑證失效 409 `REAUTH_REQUIRED`；限流 503；Jira 404 409 `REAUTH_REQUIRED`（網域可能已失效）；逾時 504；`X-Auth-Error` 只在真的憑證失效時設定；有舊資料時的 header 設計維持 | P2、P7、P15、P16、P18 |
| `POST /manual-tasks/` | 400 業務規則（`routers/manual_task.py:70`）；重送同一個 Idempotency-Key 回第一次建立的任務，不回 409（`routers/manual_task.py:117-120`、`crud/manual_task.py:294-299`）。AI 推估失敗時用預設值，不回錯誤（`services/task_inference.py:52`、`:100`） | 顯示 `detail` | 400 `INVALID_REQUEST` | — |
| `POST /manual-tasks/{id}/subtasks` | 400 業務規則（`routers/manual_task.py:179-193`）；404 主任務不存在或不是自己的（`crud/manual_task.py:322`）；409 Idempotency-Key 用在別的請求（`routers/manual_task.py:220`）或處理中（`:225`） | 顯示 `detail` | 400 `INVALID_REQUEST`；409 `IDEMPOTENCY_KEY_REUSED`／`REQUEST_IN_PROGRESS` | — |
| `GET /manual-tasks/me` | 無（沒有任務回空陣列，`routers/manual_task.py:229-235`） | — | — | — |
| `GET /manual-tasks/{id}` | 404 不存在或不是自己的（`crud/manual_task.py:322`、`:334`） | 顯示錯誤 | 404 `NOT_FOUND` | — |
| `PUT /manual-tasks/{id}` | 400 業務規則、沒有可更新的欄位（`crud/manual_task.py:428`）；404（`:431`） | 顯示 `detail` | 400 `INVALID_REQUEST`；404 `NOT_FOUND` | — |
| `DELETE /manual-tasks/{id}` | 400 刪最後一個子任務（`crud/manual_task.py:276`）；404；刪 Google 事件前取 token 與 primary calendar 時同 `POST /schedule/suggest`（`services/google_calendar.py:232` 呼叫 `:95-102`、`:60-86`）；刪事件時：沒連接或授權失效 401（`:231`）、Google 5xx、429 或連不上 502（`:213-215`、`:249-251`），其他 Google 4xx 400（`:216`） | `useTaskForm.ts:178` 401 顯示要重新連結 | 401 改 409 `REAUTH_REQUIRED`；Google 回應依 P1、P3、P4 的轉換 | P1、P2、P3、P4、P7 |
| `GET /schedule/tasks` | 無 | — | — | — |
| `PUT /schedule/reorder` | 手動任務：400 包含不屬於自己或不存在的 id（`crud/manual_task.py:353-356`，兩者訊息相同）、違反優先序（`:374`）；外部來源：不存在或不屬於自己時**靜默回 200**，id 格式錯誤（例如 `github:abc`）**500**（`crud/schedulable_items.py:30-38`） | 顯示 `detail` | 手動任務維持 400 `INVALID_REQUEST`；外部 id 格式錯 400 `INVALID_REQUEST`、不存在 404 `NOT_FOUND` | P19 |
| `PATCH /schedule/tasks/fields`、`/done` | 400 業務規則（`crud/schedulable_items.py:112`、`:131`）；手動任務 404（`crud/manual_task.py:322`）；外部來源不存在**靜默回 200**、id 格式錯誤 **500**（`crud/schedulable_items.py:140-144`） | 顯示 `detail` | 400 `INVALID_REQUEST`；404 `NOT_FOUND` | P19 |
| `POST /schedule/suggest` | Google：未連接 400（`services/google_calendar.py:72`）、授權失效 401、**第一次抓取的其他 4xx 400**（`:34-40`、`:81`）、**換新 token 後的其他 4xx 500**（`:51-54`）、5xx／429／連不上 502、**換新 token 後拿不到 access token 400**（`services/google_oauth.py:82`）、**沒有 primary calendar 404**（`google_calendar.py:100`）、OAuth client 設定錯誤 500（`google_oauth.py:74`）；計算失敗 500（`routers/schedule.py:116`）；存快照時 Redis 故障 500 | `useSchedule.ts:51` **所有 400 都當成尚未連結**、`:56` 401 要重新連結 | 未連接 409 `NOT_LINKED`；授權失效 409 `REAUTH_REQUIRED`；其他依 P1、P3、P4 | P1、P2、P3、P4、P18 |
| `POST /schedule/confirm` | 409 快照過期（`routers/schedule.py:155`）；Google 同 suggest；**逐筆寫入 Google 的錯誤（含授權失效）都列進 `failed`，原因一律「請稍後再試」**（`services/google_calendar.py:160-168`） | `useSchedule.ts:108` 409 要重新產生 | 409 `SUGGESTION_EXPIRED`；Google 同 suggest；`failed` 的原因帶 `error_code` | P1、P2、P3、P4、P18、P20 |
| `GET /analytics/productivity` | 400 時區不合法（`routers/analytics.py:22`） | 顯示錯誤 | 400 `INVALID_REQUEST` | — |
| `POST /oauth/callback` | 連不上 Google 502（`routers/google_calendar.py:45`）；**Google 回任何錯誤（含 5xx、429）都回 400「授權碼無效或已過期」**（`:46-48`）；拿不到 access token 400（`:55`） | 顯示錯誤 | `invalid_grant` 400 `INVALID_AUTHORIZATION_CODE`；5xx 502、限流 503、逾時 504；拿不到 access token 502 | P3、P8 |
| `GET /oauth/status` | 無 | — | — | — |
| `GET /oauth/calendars` | Google 同 suggest | `useGoogleCalendar.ts:81` 400 當成未連結、`:83` 401 要重新連結 | 同 suggest | P1、P2、P3、P4 |
| `POST /webhook` | 401 簽章錯誤或沒設定密鑰（`routers/pr_review_webhook.py:56-62`）；429；**payload 不是 JSON（`:75`）或缺欄位（`:81-84`）500**；**貼 PR 留言時連不上 GitHub 500**（`:160-166`）。Gemini 失敗只記 log，回 200（`:127`） | 無（GitHub 呼叫） | 401 `INVALID_WEBHOOK_SIGNATURE`（沒設定密鑰是例外）；payload 錯 400 `INVALID_REQUEST`；連不上 502 `UPSTREAM_ERROR`、逾時 504 `UPSTREAM_TIMEOUT` | P17 |
| `GET /health` | 無 | — | — | — |
| 全部（登入） | 沒帶或無效的 JWT 403（`core/security.py:20`）；**抓 Clerk JWKS 連不上或逾時也是 403**（`fastapi_clerk_auth` 的 `_decode_token` 用 `except Exception` 吞掉例外） | `useUserSync.ts:16` 401、403 都當成登入失敗 | JWT 問題 401 `UNAUTHENTICATED`；JWKS 失敗 502 `UPSTREAM_ERROR`／504 `UPSTREAM_TIMEOUT` | P10、P13 |
| 全部 | 錯誤回應只有 `detail`，沒有 `error_code`（429 除外）；422 沒有 `error_code`，**`input` 帶回送出的 body**（缺欄位時是整個 body，包括 apiKey、password；`main.py:54-59` 沒有自訂 422 handler）；有限流的 endpoint 遇到 Redis 故障（`core/rate_limit.py:25-36`，推論） | 依狀態碼判斷 | 所有錯誤回應加 `error_code`；422 拿掉 `input`、`ctx`；Redis 故障 503 `SERVICE_UNAVAILABLE` | P11、P14、P18 |

### 問題清單

依 ADR 0011「過渡期間」：每一項的 `error_code` 部分在第一階段依實際原因給，狀態碼部分在第二階段改。

| # | 問題 | 依據 | 分類 | 影響範圍 | 階段 |
|---|---|---|---|---|---|
| P1 | Google 回 4xx（例如用 403 回報的限流、權限不足）：第一次抓取一律轉成 400，前端顯示「尚未連接」；換新 token 後轉成 500 | `services/google_calendar.py:34-40`、`:51-54`；`frontend/composables/useSchedule.ts:51`、`useGoogleCalendar.ts:81` | Bug（#59） | 後端、前端、`docs/api.md`、測試 | 一（`error_code`）、二（狀態碼） |
| P2 | 「尚未連結」用 400、「第三方憑證失效」用 401，前端只靠狀態碼判斷；400 還有其他原因，會被誤判成尚未連結 | `platforms/router.py:40-58`、`services/google_calendar.py:72`、`frontend/utils/errorMessages.ts:27-34` | Bug（誤判）／技術債（狀態碼語意） | 後端、前端、`docs/api.md`、測試 | 一（`error_code`、前端改判斷）、二（改成 409） |
| P3 | 外部服務逾時與連不上一起歸成 502，限流也歸成 502 | `services/google_calendar.py:38`、`:84`；`platforms/router.py:61`；`routers/google_calendar.py:45` | 技術債 | 後端、`docs/api.md`、測試 | 一（`error_code`）、二（狀態碼） |
| P4 | 換新 Google token 後拿不到 access token 回 400（會被前端當成尚未連結）；沒有 primary calendar 回 404 | `services/google_oauth.py:82`、`services/google_calendar.py:100` | Bug（400）／技術債（404） | 後端、前端、測試 | 一（`error_code`）、二（狀態碼） |
| P5 | 連結或更新帳號時，GitHub、Jira 的非 200 回應（含 5xx、429、Jira 網域錯誤）一律回 403「token 無效或沒有權限」，憑證錯誤回 401；前端一律顯示「儲存失敗」，使用者分不出是輸入錯誤還是平台暫時故障 | `platforms/github.py:100-102`、`platforms/jira.py:107-109`、`frontend/composables/useLinkedAccount.ts:219-227` | Bug | 後端、前端、測試 | 一（`error_code`、前端顯示原因）、二（狀態碼） |
| P6 | Jira 網域不存在時（DNS 失敗）回 502「無法連線至 Jira」，使用者看不出是網域打錯 | `platforms/jira.py:101-104` | 技術債 | 後端、測試 | 一（`error_code`）、二（狀態碼） |
| P7 | 憑證解密失敗：外部平台抓項目、PATCH 用已存的憑證驗證時回 500，帳號列表整個 500；Google 卻歸成要重新連結 | `platforms/router.py:43-46`；`crud/linked_account.py:21`、`:55`；`platforms/jira.py:164`；`platforms/moodle.py:203`；`services/google_calendar.py:67-70` | 技術債（抓項目、PATCH）／Bug（列表打不開） | 後端、前端（`LinkedAccountOut` 型別）、測試 | 一（`error_code`；列表 500 改 200 並標示，是「狀態碼不變」的例外）、二（狀態碼） |
| P8 | Google OAuth 換 token 時，Google 的 5xx、429 也回 400「授權碼無效或已過期」 | `routers/google_calendar.py:46-48` | Bug | 後端、測試 | 一（`error_code`、`detail`）、二（狀態碼） |
| P9 | 沒有要改的欄位回 404，和「資料不存在」混在一起 | `crud/user.py:32-33`、`crud/linked_account.py:64-66`、`routers/linked_account.py:49` | 技術債 | 後端、`docs/api.md`、測試 | 一（`error_code`）、二（狀態碼） |
| P10 | 沒帶或無效的 Clerk JWT 回 403，照 HTTP 語意應是 401 | `core/security.py:20`、`docs/api.md:3` | 技術債 | 後端、前端（`useUserSync`）、`docs/api.md`、測試 | 一（`error_code`）、二（狀態碼） |
| P11 | 錯誤回應沒有 `error_code`（429 除外），前端只能靠狀態碼與畫面位置判斷；409 同時代表已綁定與建議過期；未知路由的 404、405 也沒有 | `core/exception_handlers.py:36-38`、`frontend/utils/errorMessages.ts:37-44` | 技術債 | 後端、前端、`docs/api.md`、測試 | 一 |
| P12 | router 直接丟 `HTTPException`，狀態碼散在各 router，不經過 `exception_handlers` | 「目前的錯誤處理架構」列的 router | 技術債 | 後端、測試 | 三 |
| P13 | 抓 Clerk JWKS 連不上或逾時，和 token 無效一樣回 403；照 ADR 改成 401 後，Clerk 故障會變成要使用者重新登入 | `core/security.py:20`；`fastapi_clerk_auth` 的 `_decode_token` | 技術債 | 後端、測試 | 二（要包裝或替換 library 的驗證；在那之前 JWKS 失敗也帶 `UNAUTHENTICATED`） |
| P14 | 422 回應的 `input` 原樣帶回送出的 body，連結帳號時會帶回明文的 apiKey、password；前端 `console.error` 也會記下來 | `backend/main.py:54-59`、`backend/schemas/linked_account.py:4-10`、`frontend/composables/useLinkedAccount.ts:220` | Bug（安全） | 後端、測試 | 一 |
| P15 | GitHub、Jira 抓項目時 400、401、403、404 一律當成憑證失效，GitHub 被限流時使用者會被要求重新連結；`X-Auth-Error` 也跟著設錯（Jira 回 404 時維持 `REAUTH_REQUIRED`，`detail` 改成網域可能已失效） | `platforms/github.py:20`、`:55-58`；`platforms/jira.py:18`、`:56-60`；`platforms/sync.py:45-52`；`platforms/router.py:56-58`、`:68-69` | Bug（和 #59 同類） | 後端、前端、測試 | 一（`error_code`、`X-Auth-Error`）、二（狀態碼） |
| P16 | Moodle 只要登入後網址不是 `/my/` 就當成帳密錯（推斷），SSO 故障或導向超過 4 秒也算；連結帳號與抓作業共用這個判斷，抓作業時使用者會被要求重新連結 | `platforms/moodle.py:51-55`、`:71-72`；`platforms/router.py:56-58`、`:68-69` | Bug | 後端、測試 | 一（只有明確的帳密錯誤才算憑證被拒：連結時 `INVALID_CREDENTIALS`、抓作業時 `REAUTH_REQUIRED` 並設 `X-Auth-Error`；其他 `UPSTREAM_ERROR`、不設 `X-Auth-Error`）、二（狀態碼） |
| P17 | GitHub webhook 的 payload 不是 JSON 或缺欄位回 500（Clerk webhook 是 400）；貼 PR 留言時連不上 GitHub 回 500 | `routers/pr_review_webhook.py:75`、`:81-84`、`:160-166` | 技術債 | 後端、測試 | 一（`error_code`）、二（狀態碼） |
| P18 | Redis 故障時快取讀寫的例外沒人接，回 500 | `core/cache.py:27`、`:43`；`core/rate_limit.py:25-36`（限流計數，推論） | 技術債 | 後端、測試 | 一（`error_code`）、二（狀態碼） |
| P19 | 排程的外部來源 id 格式錯誤回 500，不存在或不屬於自己時靜默回 200 | `crud/schedulable_items.py:30-38`、`:140-144` | 技術債 | 後端、前端、測試 | 一（格式錯誤的 `error_code`）、二（狀態碼；不存在回 404：成功回應帶不了 `error_code`） |
| P20 | 確認排程時逐筆寫入的錯誤原因一律「請稍後再試」，授權失效也不提示重新連結 | `services/google_calendar.py:160-168` | 技術債 | 後端、前端、`frontend/types/`、測試 | 二（`failed` 的項目加 `error_code`） |

可接受的既有設計：

| 項目 | 理由 |
|---|---|
| 外部平台同步失敗但有舊資料時回 200，用 `X-Data-Stale`、`X-Auth-Error` 表達 | 使用者仍然看得到資料，畫面另外提示資料過期或要重新連結；改成錯誤狀態碼會讓舊資料顯示不出來（`X-Auth-Error` 的值依 P15 修正） |
| `PUT /schedule/reorder` 有不屬於自己的手動任務 id 時回 400，不是 404 | 批次操作中部分 id 不合法，屬於請求內容錯誤；不屬於自己與不存在用同一個訊息，不透露資料是否存在 |
| 確認排程時單筆寫入失敗不擋住整批，列在 `failed` | 其他項目照常寫入，使用者看得到哪些失敗（原因的改善見 P20） |
| webhook 沒設定簽章密鑰時回 401 | 回 500 會讓外部呼叫者知道伺服器漏了設定；記 error log 由監控發現（ADR 0011「例外」） |
| AI 推估、Gemini 摘要失敗時用預設值或只記 log，不回錯誤 | 推估與摘要是附加功能，失敗不該擋住建立任務與 webhook 的主流程 |
| 查別人的任務與查不存在的任務都回 404「Task not found」 | 符合「不透露資源是否存在」（ADR 0011） |

## 需求

1. **ADR 0011**：新增 `docs/decisions/0011-api-error-status-codes.md`（內容照 scratchpad 的 ADR 草稿），`docs/decisions/README.md` 清單加一列。
2. **盤點**：這份規格的「背景」就是盤點與問題清單，記錄的是核准當時的系統狀態，PR 合併後不隨程式更新。
3. **分階段計畫**：每一項的 `error_code` 部分都在第一階段依實際原因給，狀態碼部分在第二階段改（ADR 0011「過渡期間」）。

   | 階段 | 範圍 | 處理的問題 |
   |---|---|---|
   | 一 | 後端所有錯誤回應（包括未知路由的 404、405）依實際原因加 `error_code`，狀態碼一律不變；422 拿掉 `input`、`ctx`；帳號列表遇到解不開的帳號照常回 200 並標示要重新連結（`LinkedAccountOut` 加欄位、`frontend/types/` 同步）；外部平台的 `X-Auth-Error` 只在真的憑證失效時設定；Bug 類問題的 `detail` 文字和 `error_code` 的原因一致；前端的錯誤判斷全部改成看 `error_code`，沒有 `error_code` 的回應退回依狀態碼（429 當成限流，其他顯示通用錯誤），連結帳號失敗時顯示 `detail`；`backend/README.md`「錯誤處理」加上指向 ADR 0011 | P1–P11、P14–P19 的 `error_code` 部分（P19 只有格式錯誤）；P11、P14 全部；P7 的帳號列表 |
   | 二 | 照 ADR 0011 改狀態碼，同步更新 `docs/api.md` 與 integration 測試；Clerk JWKS 失敗與 token 無效分開（包裝或替換 library 的驗證）；確認排程的 `failed` 項目加 `error_code`（`frontend/types/` 同步） | P1–P10、P15–P19 的狀態碼部分（含 P19 的不存在回 404）；P13、P20 |
   | 三 | router 裡的 `HTTPException` 改成丟 `AppError`，統一由 `exception_handlers` 轉換 | P12 |

   - 第一階段向下相容：狀態碼不變，前端先改看 `error_code`，第二階段改狀態碼時前端不受影響。例外有兩個：
     - 帳號列表遇到解不開的帳號從 500 改成 200：這是使用者會遇到的 Bug，從錯誤改成成功，前端本來就當成功處理。
     - P13：區分 JWKS 失敗要包裝 library，放在第二階段，在那之前 JWKS 失敗也帶 `UNAUTHENTICATED`。
   - 每個階段的 issue 照 `docs/issues.md` 的格式寫，附上這份規格的問題編號與 ADR 0011；每個階段的實作都要有 integration 測試斷言實際的狀態碼與 `error_code`。
   - 每個階段的等級在該 issue 的 `/issue` 流程另外判斷。
4. **開 issue 的時機與 #59**：這個 PR 合併後，主 session 只開第一階段的 issue。第一階段的 issue 與 PR 寫明：
   - PR 要 `Closes #59`：#59 的使用者問題（已連接卻顯示「尚未連接」）靠 `error_code` 在第一階段修正。
   - #59 建議的驗收條件中「Google 用 403 回報限流時回 502」被 ADR 0011 取代：限流歸 503 `UPSTREAM_RATE_LIMITED`，狀態碼在第二階段改。

   第二、三階段的 issue 在前一階段的 PR 合併後才開，內容依當時的程式碼重寫，不照抄這份規格。

## 不做

- 不改程式碼、測試、前端與 `docs/api.md`：都在後續各階段處理。`docs/api.md` 在改程式前繼續記錄目前的行為。
- 這個 PR 不開後續 issue（需求 4）。
- 不改外部平台同步失敗時退回舊資料的設計。

## 假設

1. 盤點以核准當時 `main` 的程式碼為準；之後各階段開 issue 時，以當時的程式碼重新確認。
2. Cloud Run 自己回的回應（429、5xx、504）與網路錯誤不經過後端，沒有 `error_code`；前端依狀態碼退回處理（ADR 0011「回應格式」）。

## 驗收條件

| # | 條件 | 類型 |
|---|---|---|
| AC1 | `docs/decisions/0011-api-error-status-codes.md` 存在，內容和核准的 ADR 草稿相同：回應格式（含 422 不帶輸入值、沒有 `error_code` 時的退回處理）、分類原則（含憑證被拒、無法解密與安全的兩點）、對照表、例外（webhook 沒設定密鑰）、過渡期間、放棄的做法、影響；`docs/decisions/README.md` 清單有 0011 | 不變條件 |
| AC2 | 對照表的每個 `error_code` 都有狀態碼與觸發情境；「問題清單」與「盤點」的「建議」欄用到的 `error_code` 都在對照表裡 | 不變條件 |
| AC3 | 規格的盤點涵蓋 `docs/api.md` 列出的每個後端 endpoint（前端 server route 除外），每列寫出目前的狀態碼與觸發情境（附 `檔案:行號`）、前端怎麼處理、建議 | 不變條件 |
| AC4 | 問題清單每一項都有依據（`檔案:行號`）、分類（Bug／技術債）、影響範圍與階段；可接受的既有設計各寫理由 | 不變條件 |
| AC5 | 分階段計畫的每個問題編號都屬於某個階段；第一階段除了帳號列表（500 改 200）以外不改任何狀態碼；問題清單的「階段」欄和需求 3 的表一致；需求 4 寫明第一階段 `Closes #59` 與 #59 中被 ADR 0011 取代的驗收條件 | 不變條件 |
| AC6 | 這個 PR 只新增或修改規格、ADR、ADR 清單與審查紀錄，沒有改程式碼、測試、前端與 `docs/api.md` | 不變條件 |
| AC7 | 規格、ADR、PR 描述與 commit 訊息沒有憑證、token 或第三方回應原文的範例值 | 不變條件 |
| AC8 | PR 描述有 `Closes #62` | 使用者行為 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限 | 這個 PR 只新增文件，沒有改到任何行為；這些情境的狀態碼在盤點裡逐一列出，由後續各階段處理 |
| 資料處理、併發 | 不碰資料 |
| 安全性 | 不改行為；ADR 的安全原則（不透露資源是否存在、不帶出憑證與第三方原文）由 AC1 確認寫進 ADR，AC7 確認文件本身沒有敏感內容 |

## 實作計畫

分支 `issue-62-status-codes`：

- `docs/specs/issue-62-status-codes.md`（照交付清單）。
- `docs/decisions/0011-api-error-status-codes.md`（照交付清單，從 ADR 草稿）、`docs/decisions/README.md` 清單加一列。
- `docs/reviews/specification/issue-62-status-codes.md`、`docs/reviews/implementation/issue-62-status-codes.md`（主 session commit）。
- PR 描述加 `Closes #62`。

為什麼這樣做：設計原則是之後所有 API 都要遵守的決定，放 ADR；盤點記錄的是當時的狀態，放規格背景（永久保存、不隨程式更新）；`docs/api.md` 記錄目前的行為，等程式改了才更新。

## 測試對應

| AC | 驗證方式 |
|---|---|
| AC1 | `diff` ADR 與核准的草稿；讀 `docs/decisions/README.md` |
| AC2 | 從盤點與問題清單抽出所有 `error_code`，逐一對照 ADR 的對照表 |
| AC3 | 對照 `docs/api.md` 的 endpoint 清單與盤點表的列 |
| AC4 | 讀問題清單與可接受的既有設計 |
| AC5 | 對照問題清單的「階段」欄與需求 3 的表 |
| AC6 | `git diff --stat origin/main...HEAD` |
| AC7 | `grep` 規格、ADR、PR 描述有沒有 token 樣式的字串 |
| AC8 | `gh api repos/{owner}/{repo}/pulls/<PR> --jq .body` |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
