# API 錯誤回應第一階段：依原因加 error_code、前端改看 error_code

- 狀態：已核准
- 等級：高風險（改錯誤回應會不會帶出憑證（422 的 `input`）、外部平台同步的錯誤分類與 `X-Auth-Error`、憑證無法解密時的處理；前後端的 API 契約一起改）
- issue：#77
- PR：#（待開）

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/77

[ADR 0011](../decisions/0011-api-error-status-codes.md) 定下錯誤回應的設計：狀態碼表示類別，`error_code` 表示原因，前端依 `error_code` 判斷畫面。[docs/specs/issue-62-status-codes.md](issue-62-status-codes.md) 盤點了全站的狀態碼，分三階段修改；這是第一階段：依實際原因加 `error_code`，前端改看 `error_code`，狀態碼先不變（例外見需求 6）。

使用者現在會遇到：

- 已連接 Google，Google 回 403（例如限流）時，產生排程建議、看行事曆清單的畫面顯示「尚未連接」（#59）。原因是 `backend/services/google_calendar.py:34-40` 把 5xx、429 以外的 4xx 一律轉成 400，而前端把所有 400 當成未連結（`frontend/utils/errorMessages.ts:32-34`，用在 `composables/useSchedule.ts:51`、`composables/useGoogleCalendar.ts:81`）。換新 token 後拿不到 access token 也回 400（`backend/services/google_oauth.py:82`）。
- GitHub 用 403 回報限流、Moodle 的 SSO 故障時，被要求重新連結帳號：`backend/platforms/github.py:20`、`backend/platforms/jira.py:18` 把 400、401、403、404 都當成不可重試的憑證失效；Moodle 登入後 4 秒網址不是 `/my/` 就算帳密錯（`backend/platforms/moodle.py:51-55`）。
- 連結帳號時 token 錯、平台暫時故障、Jira 網域錯都只顯示「儲存失敗」（`frontend/composables/useLinkedAccount.ts:219-227`）。
- Google OAuth 授權時，Google 暫時故障也回「授權碼無效或已過期」（`backend/routers/google_calendar.py:46-48`）；前端只顯示固定的「連接 Google Calendar 失敗」（`frontend/composables/useGoogleOAuthCallback.ts:60-66`），使用者分不出原因。
- 只要一個外部平台帳號的憑證解不開，帳號設定頁的整個清單就 500（`backend/crud/linked_account.py:21`、`:55`；`backend/core/crypto.py:26-27`）。
- 連結帳號時少送一個欄位，FastAPI 預設的 422 回應會在 `input` 帶回整個 request body，包括 apiKey、password（`backend/main.py:52-59` 沒有自訂 handler），前端還會 `console.error` 出來（`useLinkedAccount.ts:220`）。

### 目前的錯誤處理

- `AppError` 由 `backend/core/exception_handlers.py:25-38` 依類別轉成狀態碼，回應只有 `detail`；資料庫錯誤（`:41-48`）與未處理的例外（`:56-82`）也只有 `detail`。只有限流回 `error_code: "RATE_LIMITED"`（`backend/core/rate_limit.py:39-44`）。
- router 直接丟的 `HTTPException`、未知路由的 404、405 由 Starlette 預設處理，沒有 `error_code`（`backend/main.py:54-59` 只註冊了限流、資料庫錯誤與 `AppError` 的 handler）。
- 外部平台抓項目：`NonRetryableError` 同時決定三件事：不重試（`backend/platforms/sync.py:45-52`，最多試 2 次）、有舊資料時的 `X-Auth-Error`（`:77`、`backend/platforms/router.py:68-69`）、沒有舊資料時回 401（`backend/platforms/router.py:56-58`）。`UpstreamError` 會重試，沒有舊資料時回 502（`:59-61`）。
- 前端：`frontend/utils/errorMessages.ts` 除了限流只看狀態碼（`isNotLinkedError` 400、`isAuthError` 401、`isAlreadyLinkedError`／`isSuggestionExpiredError` 409）；`frontend/composables/useUserSync.ts:14-17` 依狀態碼顯示登入失敗與資料庫錯誤的文字。帳號列表的型別 `frontend/types/linkedAccount.ts` 對應 `backend/schemas/linked_account.py` 的 `LinkedAccountOut`，在 `frontend/components/header/AccountSettings.vue` 顯示。

## 需求

1. **回應格式**：本後端產生的錯誤回應都是 `{"detail", "error_code"}`，`error_code` 依 ADR 0011 對照表的**原因**決定；狀態碼維持目前的值（ADR 0011「過渡期間」）。涵蓋 `AppError`、router 的 `HTTPException`、422、429、500、503、未知路由的 404 與不支援的方法 405。
2. **`AppError` 帶 `error_code`**：每個子類別有預設的 `error_code` 與預設的狀態碼（預設狀態碼就是目前 `_STATUS_BY_ERROR` 的值），丟的時候可以分別另外指定 `error_code` 與狀態碼（例如 `ExternalServiceError` 預設 `UPSTREAM_ERROR`／502，逾時指定 `UPSTREAM_TIMEOUT`）。只指定 `error_code` 時狀態碼不變；要讓某個原因維持目前、但和類別預設不同的狀態碼（例如 PATCH 解密失敗帶 `REAUTH_REQUIRED` 但維持 500），就明確指定狀態碼。handler 一律用「建構時指定的值，沒有就用類別預設」。`detail` 只能是固定的文字或使用者自己送出、非機密的值（例如平台名稱、缺少的欄位名稱、時區），不能用例外訊息（`str(exc)`）或第三方回應的內容組成：`NonRetryableError`、`UpstreamError` 的訊息帶有使用者名稱與第三方回應原文（`backend/platforms/moodle.py:55`、`:178`；`backend/platforms/github.py:56`），只能記在 log。router 裡需要專屬 `error_code` 的錯誤這一階段改丟 `AppError`：排程建議過期（`SUGGESTION_EXPIRED`）、使用者已註冊（`ALREADY_EXISTS`）、webhook 簽章錯誤（`INVALID_WEBHOOK_SIGNATURE`）、OAuth 換 token（需求 4）、外部平台抓項目（`NOT_LINKED`、`REAUTH_REQUIRED` 等，需求 5）。其他 `HTTPException` 不改，由新的 handler 依狀態碼補預設的 `error_code`（400 `INVALID_REQUEST`、401 `UNAUTHENTICATED`、404 `NOT_FOUND`、405 `METHOD_NOT_ALLOWED`、409 `ALREADY_EXISTS`、500 `INTERNAL_ERROR`、502 `UPSTREAM_ERROR`）；Clerk 驗證 library 回的 403 補 `UNAUTHENTICATED`（ADR 0011「過渡期間」的例外：分不出抓 JWKS 失敗與 token 無效）。沒列到的狀態碼：4xx 給 `INVALID_REQUEST`，5xx 給 `INTERNAL_ERROR`。handler 保留 `HTTPException` 原本的 header（例如 405 的 `Allow`、401 的 `WWW-Authenticate`），`detail` 照原樣回傳：目前所有 `HTTPException` 的 `detail` 都是固定的文字（`backend/routers/*.py`、`backend/platforms/router.py` 的 `*_detail`、`fastapi_clerk_auth` 的 "Forbidden"），handler 不另外加入例外內容。`AccessDeniedError` 的預設 `error_code` 是 `INVALID_CREDENTIALS`、預設狀態碼維持 403：它只用在連結 GitHub、Jira 時驗證 token 的非 200 回應（`backend/platforms/github.py:102`、`backend/platforms/jira.py:109`），表示外部平台拒絕這次驗證用的 token，不是 Google 專用；這兩處的情況仍依需求 4 明確指定 `error_code`，預設值用在之後新的使用情況。
3. **422**：回應帶 `error_code: "VALIDATION_ERROR"`，`detail` 是驗證錯誤的清單，每一項不帶 `input` 與 `ctx`。
4. **依原因分類**（狀態碼維持目前的值）：

   | 情況 | `error_code` |
   |---|---|
   | Google 403，reason 是 `rateLimitExceeded`、`userRateLimitExceeded`、`quotaExceeded`、`dailyLimitExceeded`；Google 429（包括換新 token 時） | `UPSTREAM_RATE_LIMITED` |
   | Google 403，reason 是 `insufficientPermissions`、`forbidden`；換新 token 後仍 401；尚未連接卻需要刪事件（任務帶著行事曆事件，代表使用者連接過；用 `NOT_LINKED` 的話前端不顯示錯誤，刪除會悄悄失敗） | `REAUTH_REQUIRED` |
   | Google 尚未連接 | `NOT_LINKED` |
   | Google 400 | `INTERNAL_ERROR` |
   | Google 5xx、其他無法判斷原因的 4xx、換 token 後沒有 access token、連不上 | `UPSTREAM_ERROR` |
   | 換新 token 後再抓行事曆清單遇到 401 以外的 4xx | 依上面 Google 的列給 `error_code`，狀態碼維持 500（`backend/services/google_calendar.py:53-54`） |
   | Google 逾時 | `UPSTREAM_TIMEOUT` |
   | 沒有 primary calendar | `NO_PRIMARY_CALENDAR` |
   | Google OAuth client 設定錯誤（`invalid_client`） | `INTERNAL_ERROR`（狀態碼維持：換新 token 時 500，OAuth 回呼時 400） |
   | Google OAuth 換 token：`invalid_grant` | `INVALID_AUTHORIZATION_CODE`（狀態碼維持 400） |
   | Google OAuth 換 token：`invalid_request`、`unauthorized_client`、`redirect_uri_mismatch`（我方設定錯誤） | `INTERNAL_ERROR`（狀態碼維持 400） |
   | Google OAuth 換 token：其他錯誤碼、5xx、429、拿不到 access token、連不上、逾時 | 依上面 Google 的列（其他錯誤碼 `UPSTREAM_ERROR`）；狀態碼維持：Google 回錯誤與拿不到 access token 400，連不上與逾時 502（`backend/routers/google_calendar.py:43-55`） |
   | 連結或更新帳號時，GitHub、Jira 回 401；Moodle 帳密錯（需求 5 的判斷）；包括只改 Jira 網域或 Moodle 帳號、用已存的憑證驗證 | `INVALID_CREDENTIALS`（狀態碼維持 401） |
   | 連結或更新 Jira 時，網域回 404 | `INVALID_PLATFORM_DOMAIN`（狀態碼維持 403） |
   | 連結或更新 Jira 時，DNS 找不到網域：`httpx.ConnectError` 的例外鏈（`__cause__`／`__context__`）裡有 `socket.gaierror` | `INVALID_PLATFORM_DOMAIN`（狀態碼維持 502）；其他連線錯誤照下一列 |
   | 連結或更新帳號時，GitHub、Jira 回 5xx | `UPSTREAM_ERROR`（狀態碼維持 403） |
   | 連結或更新帳號時，GitHub、Jira 回 429，或回 403 而且有限流特徵（照需求 5 的 GitHub 限流判斷） | `UPSTREAM_RATE_LIMITED`（狀態碼維持 403） |
   | 連結或更新帳號時，GitHub、Jira 連不上（DNS 找不到 Jira 網域除外）／逾時 | `UPSTREAM_ERROR`／`UPSTREAM_TIMEOUT`（狀態碼維持 502） |
   | 連結或更新 Moodle 時，Selenium `TimeoutException`／其他 WebDriver 錯誤 | `UPSTREAM_TIMEOUT`／`UPSTREAM_ERROR`（狀態碼維持 502，`backend/platforms/moodle.py:187-189`） |
   | 連結或更新帳號時，GitHub、Jira 回 400 | `INTERNAL_ERROR`（狀態碼維持 403） |
   | 連結或更新帳號時，GitHub、Jira 回沒有限流特徵的 403 | `INVALID_CREDENTIALS`，`detail` 寫 token 權限不足、請換有權限的 token（狀態碼維持 403） |
   | 連結或更新帳號時，GitHub、Jira 回其他 4xx（例如 GitHub 404）或 3xx | `UPSTREAM_ERROR`（狀態碼維持 403） |
   | 連結或更新 Moodle 時登入後導向別處（不是 `/my/`，也不是登入頁） | `UPSTREAM_ERROR`（狀態碼維持 401） |
   | 連結或更新帳號時，對方回應無法解析（例如不是 JSON） | `UPSTREAM_ERROR`（狀態碼維持 500） |
   | 更新使用者或帳號時沒有可更新的欄位 | `INVALID_REQUEST`（狀態碼維持 404；帳號 PATCH 要分得出「沒有欄位」與「帳號不存在」） |
   | 已連結帳號的憑證無法解密（外部平台抓項目、PATCH 用已存的憑證驗證、Google）：只有 `decrypt_secret` 丟的 `ValueError` 算，其他例外（例如伺服器沒設加密金鑰）照未處理的例外 | `REAUTH_REQUIRED`；記 warning，不刪已存的憑證；狀態碼維持目前的值（抓項目 500、PATCH 500、Google 401） |
   | Redis 讀寫刪失敗（`backend/core/cache.py:27`、`:43`、`:48-52`）、限流計數的 Redis 失敗 | `SERVICE_UNAVAILABLE`（狀態碼維持 500） |
   | GitHub webhook 貼 PR 留言時連不上 GitHub（`backend/routers/pr_review_webhook.py:160-166`） | `UPSTREAM_ERROR`，逾時 `UPSTREAM_TIMEOUT`（狀態碼維持 500） |
   | 排程的外部來源 id 格式錯誤（`backend/crud/schedulable_items.py:30-38`、`:140-144`） | `INVALID_REQUEST`（狀態碼維持 500） |
   | GitHub webhook 的 payload 不是 JSON 或缺欄位（`backend/routers/pr_review_webhook.py:75`、`:81-84`） | `INVALID_REQUEST`（狀態碼維持 500） |
   | 新增子任務時 Idempotency-Key 用在別的請求／同一個請求還在處理中 | `IDEMPOTENCY_KEY_REUSED`／`REQUEST_IN_PROGRESS` |
   | 其他 `AppError`、資料庫與未處理的例外 | 照 ADR 0011 對照表（例如 `InvalidRequestError` 預設 `INVALID_REQUEST`、資料庫連不上 `SERVICE_UNAVAILABLE`、未處理的例外 `INTERNAL_ERROR`） |

   Google 與 GitHub 回報限流、權限的 reason、header 與訊息依官方文件，實作時用測試固定下來。

   **`detail`**：每一列的 `detail` 都和該列的 `error_code` 一致；不是 `REAUTH_REQUIRED`、`INVALID_CREDENTIALS` 的列，`detail` 不出現「授權已失效」「帳號或密碼錯誤」「token 無效」「權限不足」之類的說法（例如 OAuth 時 Google 暫時故障不再說「授權碼無效」，GitHub 限流不再說「授權已失效」）。這次改到的 `detail` 一併改成中文。`detail` 都是固定的文字，不帶第三方回應的原文。
5. **外部平台抓項目**：把「是否重試」「沒有舊資料時的狀態碼」「`X-Auth-Error` 與 `error_code`」分開判斷；重試與狀態碼維持目前的行為：

   | 平台回應 | 重試 | 沒有舊資料時的狀態碼 | `error_code` | 有舊資料時的 `X-Auth-Error` |
   |---|---|---|---|---|
   | GitHub 403，而且 `x-ratelimit-remaining` 是 `0`、帶 `retry-after`，或錯誤訊息含 secondary rate limit（訊息只用來分類，不放進回應） | 不重試 | 401 | `UPSTREAM_RATE_LIMITED` | 不設 |
   | GitHub、Jira 429 | 重試 | 502 | `UPSTREAM_RATE_LIMITED` | 不設 |
   | GitHub、Jira 401；沒有限流特徵的 403 | 不重試 | 401 | `REAUTH_REQUIRED` | 設 |
   | Jira 404 | 不重試 | 401 | `REAUTH_REQUIRED`，`detail` 寫「Jira 網域可能已失效，請到設定確認或重新連結」 | 設 |
   | GitHub、Jira 400 | 不重試 | 401 | `INTERNAL_ERROR` | 不設 |
   | GitHub 404 | 不重試 | 401 | `UPSTREAM_ERROR` | 不設 |
   | Moodle 送出登入後網址仍停在登入頁（只比對 host `i.nccu.edu.tw` 與 path `/Login.aspx`，忽略 query） | 不重試 | 401 | `REAUTH_REQUIRED` | 設 |
   | Moodle 登入後導向別的網址（不是 `/my/`，也不是登入頁） | 不重試 | 401 | `UPSTREAM_ERROR` | 不設 |
   | Moodle 的 Selenium `TimeoutException`（等不到頁面元素、載入逾時） | 重試 | 502 | `UPSTREAM_TIMEOUT` | 不設 |
   | Moodle 其他 WebDriver 錯誤 | 重試 | 502 | `UPSTREAM_ERROR` | 不設 |
   | 尚未連結 | — | 400 | `NOT_LINKED` | — |
   | 憑證無法解密 | — | 500 | `REAUTH_REQUIRED` | — |
   | 5xx、連不上 | 重試 | 502 | `UPSTREAM_ERROR`（逾時 `UPSTREAM_TIMEOUT`） | 不設 |
   | GitHub、Jira 回其他 4xx（400、401、403、404、429 以外）或 3xx | 重試 | 502 | `UPSTREAM_ERROR` | 不設 |
   | 回應無法解析（不是 JSON、少欄位） | 重試 | 500 | `UPSTREAM_ERROR` | 不設 |
   | 同步途中資料庫出錯 | — | 500 | 連不上 `SERVICE_UNAVAILABLE`，其他 `INTERNAL_ERROR` | — |

   「重試」「沒有舊資料時的狀態碼」兩欄都是目前的行為（`platforms/github.py:20`、`:55-58`；`platforms/jira.py:18`、`:56-60`；`platforms/moodle.py:51-55`、`:176-178`；`platforms/sync.py:45-52`）；這一階段只改 `error_code` 與 `X-Auth-Error`。
6. **帳號列表**：任何一個帳號的憑證解不開時，`GET /users/me/linked-accounts/` 照常回 200。`LinkedAccountOut` 加布林欄位 `needs_reauth`（解得開的帳號是 `false`）；解不開的帳號 `needs_reauth: true`，不回傳憑證欄位（`apiKey`、`password`）；記 warning，不刪憑證。這是這一階段唯一改狀態碼的地方（ADR 0011「過渡期間」的例外）。`frontend/types/linkedAccount.ts` 同步加欄位；前端把 `needs_reauth` 的帳號當成已連結：`AccountSettings.vue` 的帳號卡片顯示「憑證無法讀取，請重新連結」與刪除按鈕；儲存時走 PATCH（不是 POST），並要求填完整的憑證（GitHub 的 apiKey；Jira 的 apiKey；Moodle 的帳號與密碼），PATCH 有帶新憑證時不會解舊的密文，後端不用改；外部平台頁顯示要重新連結，不顯示「尚未綁定」。
7. **前端**：錯誤判斷都看 `error_code`：
   - `NOT_LINKED`：只在有「尚未連接」狀態的畫面設定那個狀態（排程建議頁、Google 行事曆卡片、外部平台列表的「尚未綁定」）；其他畫面（例如確認排程）當成一般錯誤，照下面「其他 `error_code`」顯示。
   - Google 行事曆卡片（`useGoogleCalendar`、`GoogleCalendarEmbed.vue`）：
     - 只有 `NOT_LINKED` 才設成未連接。
     - `REAUTH_REQUIRED`（權限不足、換新 token 後仍 401）：照目前顯示「授權已失效」並提示重新連結；帳號設定照目前把 `isConnected` 設成 false，但按鈕文字在 `needsReconnect` 時顯示「重新連接 Google Calendar」，不顯示「連接 Google Calendar」（`AccountSettings.vue:200` 目前只看 `isConnected`；「重新連接」沿用同一個按鈕已有的文字）。
     - 其他錯誤（限流、其他 4xx、5xx）：帳號設定維持「已連接」，跳 toast；這次之前在同一個頁面曾載入成功的行事曆清單就保留並照常嵌入；從沒載入成功過，卡片顯示「Google 行事曆暫時無法載入，請稍後再試」。
   - 前置檢查失敗（`useGoogleCalendar` 的 `/oauth/status`、`usePlatformItems` 讀帳號列表）：不覆寫畫面，維持**最近一次已知的結果**（目前 `useGoogleCalendar.ts:45-50`、`usePlatformItems.ts:61-67` 會直接設成未連結）：
     - 最近一次是載入成功：照常顯示（行事曆照常嵌入、外部平台列表照常顯示），帳號設定維持「已連接」。
     - 最近一次是尚未連接、授權已失效（`REAUTH_REQUIRED`）或憑證無法讀取（`needs_reauth`）：維持那個畫面。
     - 目前沒有已知的結果：行事曆卡片顯示「Google 行事曆暫時無法載入，請稍後再試」，外部平台列表顯示「暫時無法載入，請稍後再試」；帳號設定不顯示「已連接」標記，按鈕維持「連接 Google Calendar」，不改其他畫面的狀態。
     - 前置檢查失敗本身不會讓畫面變成「尚未連接」「尚未綁定」。
     - 已知的結果只存在前端記憶體、只屬於目前登入的 Clerk 使用者：重新整理頁面、登出或換成另一個使用者時清除，新的使用者第一次取得結果前視為沒有已知結果，不顯示前一個使用者的清單。
   - `REAUTH_REQUIRED`：提示重新連結（目前 `isAuthError` 的行為）。
   - `SUGGESTION_EXPIRED`：請使用者重新產生建議。
   - `ALREADY_EXISTS`：連結帳號時顯示已綁定；註冊時當成已註冊（`useUserSync.ts:77`）。
   - `RATE_LIMITED`、`UPSTREAM_RATE_LIMITED`：顯示「請求太頻繁，請稍後再試」。
   - 其他 `error_code`：顯示畫面原本的錯誤標題與說明，後端的 `detail` 附加在說明後面（不取代）；連結帳號失敗、Google OAuth 回呼失敗（`useGoogleOAuthCallback.ts`）也顯示 `detail`。例外：任務精靈（`useScheduleWizard.ts:110-111`、`:157-158`）與任務表單（`useTaskForm.ts:167-174`）維持目前以 `detail` 取代預設說明的行為。
   - 沒有 `error_code` 的回應（Cloud Run、網路錯誤）：429 當成限流，其他顯示通用錯誤。
   - `useUserSync` 的文字改成依 `UNAUTHENTICATED`（登入驗證失敗）、`SERVICE_UNAVAILABLE`（資料庫暫時無法使用）判斷；沒有 `error_code` 時照目前依狀態碼（上一點通用退回的例外）。
   - `console.error` 只記 status 與 `error_code`，不印整個錯誤物件：錯誤物件帶著送出的 request body 與 Authorization header（`useLinkedAccount.ts:220` 等）。
8. **文件**：`docs/api.md` 開頭加一段說明錯誤回應的格式（`detail`、`error_code`，對照表見 ADR 0011），各 endpoint 的狀態碼不改；`backend/README.md`「錯誤處理」加上「丟例外前照 ADR 0011 選 `error_code`」並指向 ADR 0011。
9. PR 描述要 `Closes #77` 與 `Closes #59`，並寫明 #59 建議的驗收條件中「Google 用 403 回報限流時回 502」被 ADR 0011 取代：限流歸 503 `UPSTREAM_RATE_LIMITED`，狀態碼在第二階段改，這個 PR 帶 `UPSTREAM_RATE_LIMITED`、狀態碼維持 400。

## 不做

- 不改狀態碼（帳號列表除外）：過渡期間 `error_code` 和狀態碼不完全符合 ADR 0011 對照表，第二階段依對照表統一。第二階段要處理的事項：改狀態碼、轉送 `Retry-After`、區分 Clerk JWKS 失敗、確認排程 `failed` 項目加 `error_code`、排程外部 id 不存在回 404（以下各點）。
- 不改重試次數與哪些錯誤重試。
- 不把所有 router 的 `HTTPException` 改成 `AppError`：只改需求 2 列的，其餘在第三階段。
- 不區分抓 Clerk JWKS 失敗與 token 無效：在第二階段。
- 不改確認排程的 `failed` 項目格式（第二階段加 `error_code`）。
- 不改排程外部 id 不存在時靜默回 200 的行為（第二階段）。
- 不轉送外部服務的 `Retry-After`（ADR 0011 對照表 `UPSTREAM_RATE_LIMITED`）：第二階段改成 503 時一起做。
- 不處理共用資料庫時不同環境可能互相覆寫憑證的問題（假設 4，觸發條件待確認，#78）。
- 不持久化 Google 行事曆清單：「保留上次清單」只限前端目前頁面執行期間的狀態，重新整理頁面後不保留；不新增 localStorage、sessionStorage 或後端持久化。

## 假設

1. （有依據、待測試驗證；以 AC1、AC5、AC6 的測試固定判斷規則）Google 與 GitHub 回報限流的方式依官方文件：Google Calendar API 用 403 或 429 加 reason `rateLimitExceeded`、`userRateLimitExceeded`，用量上限是 `quotaExceeded`（`dailyLimitExceeded` 是舊文件的 reason，現行文件查不到，保險起見一併算限流）；GitHub 主要限流帶 `x-ratelimit-remaining: 0`，secondary rate limit 回 403 或 429，錯誤訊息寫明是 secondary rate limit，可能帶 `retry-after`，也可能兩個 header 都沒有。
2. （有依據、待測試驗證；以 AC7 的 `test_moodle_platform.py` 固定判斷規則，實際的學校頁面行為上線後才能驗證）國立政治大學 SSO 帳密錯誤時，送出後網址停在 `i.nccu.edu.tw/Login.aspx`；導向別處或逾時不是帳密錯誤。之後發現誤判，再改成讀登入頁的錯誤訊息。
3. Cloud Run 自己回的回應與網路錯誤沒有 `error_code`（ADR 0011）。
4. **待確認的風險：共用資料庫時重新連結可能覆寫另一個環境的憑證**。觸發條件還沒以實際環境設定確認，所以這一項**不是**已接受的風險，也不是安全或正確的設計；這是這次開發之前就有的問題，追蹤在 #78。
   - 觸發條件：(a) 正式與開發環境共用同一個資料庫，(b) 各自用不同的 Fernet 金鑰（`backend/core/crypto.py`），(c) 同一個人在兩個環境是同一個 Clerk 使用者 id，而且都連結了同一個平台（帳號 id 是 `<clerk_id>_<platform>`，`backend/crud/linked_account.py:29`）。(a)、(b) 依程式註解（`backend/services/google_calendar.py:68`）；(c) **待確認**：開發者表示兩個環境用同一個 Clerk instance，但還沒以實際環境設定（兩邊的 `CLERK_ISSUER`）確認，確認列在 #78。
   - 條件成立時的影響：在其中一個環境連結或更新帳號（包括照這個 PR 新增的「憑證無法讀取，請重新連結」提示操作），會用那個環境的金鑰覆寫密文（`backend/crud/linked_account.py:77`），另一個環境的那個帳號之後變成 `needs_reauth`。只影響同時在兩個環境使用的帳號，不會讓別人讀到憑證。
   - 這個 PR 不做：不分環境儲存憑證、不改提示文字、不阻擋覆寫。確認條件之後，在 #78 決定接受或修正。

## 驗收條件

| # | 條件 | 類型 |
|---|---|---|
| AC1 | 已連接 Google 時：(1) Google 回限流（403 限流 reason 或 429）、其他 4xx 或 5xx：排程建議頁與 Google 行事曆卡片不顯示「尚未連接」，帳號設定維持「已連接」；最近一次已知的結果是載入成功時照常嵌入，沒有已知結果時卡片顯示「Google 行事曆暫時無法載入，請稍後再試」；限流時顯示「請求太頻繁，請稍後再試」。(2) 權限不足或換新 token 後仍 401（`REAUTH_REQUIRED`）：卡片顯示「授權已失效」並提示重新連結，帳號設定的按鈕是「重新連接 Google Calendar」，不顯示「尚未連接」（#59） | 使用者行為 |
| AC2 | 本後端產生的每個錯誤回應都有 `error_code`，值依需求 4、5 與 ADR 0011 對照表的原因；未知路由 404 是 `NOT_FOUND`、不支援的方法 405 是 `METHOD_NOT_ALLOWED`；沒帶或無效的 JWT（403）是 `UNAUTHENTICATED` | 不變條件 |
| AC3 | 除了帳號列表，每個 endpoint 在每種錯誤情況回的狀態碼和改之前相同 | 不變條件 |
| AC4 | 422 回應帶 `VALIDATION_ERROR`，`detail` 的每一項沒有 `input`、`ctx`；連結帳號時少送欄位，回應裡沒有送出的 apiKey、password | 不變條件 |
| AC5 | 抓 GitHub 項目時 GitHub 用 403 回報限流：沒有舊資料時狀態碼仍是 401、`error_code` 是 `UPSTREAM_RATE_LIMITED`，畫面不要求重新連結；有舊資料時不設 `X-Auth-Error`；兩種情況都不重試 | 使用者行為 |
| AC6 | 外部平台抓項目時，需求 5 表上每一列的重試、狀態碼、`error_code`、`X-Auth-Error` 都和表相同 | 不變條件 |
| AC7 | Moodle 抓作業時：登入後導向別的網址（不是登入頁）是 `UPSTREAM_ERROR`、Selenium 逾時是 `UPSTREAM_TIMEOUT`，都不設 `X-Auth-Error`，畫面不要求重新連結；只有送出後停在登入頁（host 與 path 相同，忽略 query）才是 `REAUTH_REQUIRED` | 使用者行為 |
| AC8 | 連結或更新帳號時，token 錯或權限不足（401、沒有限流特徵的 403：`INVALID_CREDENTIALS`）、Jira 網域錯（`INVALID_PLATFORM_DOMAIN`）、我方送錯請求（400：`INTERNAL_ERROR`）、平台暫時故障或其他 4xx、3xx（`UPSTREAM_*`）的 `error_code` 不同，狀態碼和改之前相同，畫面顯示對應的 `detail`；只改 Jira 網域或 Moodle 帳號、用已存的憑證驗證被拒時也是 `INVALID_CREDENTIALS` | 使用者行為 |
| AC9 | 有一個帳號的憑證解不開時，帳號列表回 200：那個帳號 `needs_reauth: true`、沒有 `apiKey`／`password`，卡片顯示「憑證無法讀取，請重新連結」與刪除按鈕，外部平台頁不顯示「尚未綁定」；使用者填完整的新憑證儲存後（PATCH）成功，之後 `needs_reauth: false`；其他帳號照常顯示、`needs_reauth: false` | 使用者行為 |
| AC10 | 憑證無法解密時（帳號列表、外部平台抓項目、PATCH、Google）記 warning、不刪已存的憑證；抓項目與 PATCH 時 `error_code` 是 `REAUTH_REQUIRED` | 不變條件 |
| AC11 | Google OAuth 換 token：`invalid_grant` 是 `INVALID_AUTHORIZATION_CODE`，`detail` 是授權碼無效；Google 5xx、429 是 `UPSTREAM_ERROR`／`UPSTREAM_RATE_LIMITED`，`detail` 不說授權碼無效；OAuth 回呼畫面的錯誤訊息顯示後端的 `detail` | 使用者行為 |
| AC12 | 前端依需求 7 判斷：`NOT_LINKED` 在有「尚未連接」狀態的畫面設定該狀態、在其他畫面（例如確認排程）顯示錯誤；`REAUTH_REQUIRED` 提示重新連結；`SUGGESTION_EXPIRED` 請重新產生；`ALREADY_EXISTS` 顯示已綁定或當成已註冊；兩種限流顯示稍後再試；其他顯示原本的標題與說明並附加 `detail`；沒有 `error_code` 時 429 顯示限流、其他顯示通用錯誤（`useUserSync` 例外：照目前依狀態碼） | 使用者行為 |
| AC13 | 錯誤回應不帶憑證、token 與第三方回應的原文：改過的 `detail` 都是固定的文字；新增的 422 handler 不把 request body 寫進 log | 不變條件 |
| AC14 | `docs/api.md` 開頭有錯誤回應格式的說明並指向 ADR 0011，各 endpoint 的狀態碼沒改；`backend/README.md`「錯誤處理」指向 ADR 0011 | 不變條件 |
| AC15 | PR 描述有 `Closes #77`、`Closes #59`，並寫明 #59 中被 ADR 0011 取代的驗收條件 | 使用者行為 |
| AC16 | 需求 4、5 每一列的 `detail` 都和該列的 `error_code` 一致；不是 `REAUTH_REQUIRED`、`INVALID_CREDENTIALS` 的列，`detail` 不出現「授權已失效」「帳號或密碼錯誤」「token 無效」「權限不足」；連結時沒有限流特徵的 403 的 `detail` 說明 token 權限不足；改到的 `detail` 是中文 | 使用者行為 |
| AC17 | 前端的 `console.error` 不印出錯誤物件，只記 status 與 `error_code`；連結帳號失敗時 console 裡沒有送出的 apiKey、password 與 JWT | 不變條件 |
| AC18 | 只有 `decrypt_secret` 的 `ValueError` 會變成 `REAUTH_REQUIRED` 或 `needs_reauth`；伺服器沒設加密金鑰等其他例外回 500 `INTERNAL_ERROR`，帳號不被標成要重新連結 | 不變條件 |
| AC19 | 新的 `HTTPException` handler 保留原本的 header（405 的 `Allow`、401 的 `WWW-Authenticate`）與原本的 `detail`；沒列到的 4xx 是 `INVALID_REQUEST`、5xx 是 `INTERNAL_ERROR` | 不變條件 |
| AC20 | `/oauth/status` 或帳號列表失敗時，畫面維持最近一次已知的結果：(1) 最近一次是載入成功，行事曆照常嵌入、外部平台列表照常顯示，帳號設定維持「已連接」；(2) 最近一次是尚未連接、授權已失效或憑證無法讀取，維持那個畫面；(3) 沒有已知結果，行事曆卡片與外部平台列表顯示「暫時無法載入，請稍後再試」，帳號設定不顯示「已連接」；前置檢查失敗本身不會變成「尚未連接」「尚未綁定」；重新整理、登出或換成另一個使用者後，不顯示先前的結果 | 使用者行為 |
| AC21 | `AppError` 只指定 `error_code` 時狀態碼和類別預設相同；明確指定狀態碼時用指定的值；沒有指定時用類別預設（例如 `AccessDeniedError` 是 `INVALID_CREDENTIALS`／403）；需求 4、5 每一列的狀態碼都和改之前相同（帳號列表除外） | 不變條件 |
| AC22 | 錯誤回應的 `detail` 不含例外訊息與第三方回應的內容：GitHub、Jira 回應原文、Moodle 使用者名稱只出現在 log | 不變條件 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中 | 不改載入狀態，只改錯誤時的判斷與文字 |
| 空資料 | 帳號列表沒有帳號時照舊回空陣列；外部平台沒有舊資料的情況由 AC5、AC6 涵蓋 |
| 併發 | 不改寫入流程；Idempotency 只改 `error_code`（AC2） |
| 資料處理 | 不改資料庫結構；解密失敗不刪憑證（AC10）；`needs_reauth` 是回應時算出來的，不存進資料庫 |

## 實作計畫

分支 `issue-77-error-codes`。

**後端**

- `backend/core/errors.py`：`AppError` 加 `error_code` 與狀態碼（類別預設，建構時可分別指定）；各子類別的預設 `error_code` 照 ADR 0011 對照表（`AccessDeniedError` 是 `INVALID_CREDENTIALS`）、預設狀態碼照目前 `_STATUS_BY_ERROR`。
- `backend/core/exception_handlers.py`：`app_error_handler` 回 `error_code`；資料庫與未處理的例外帶 `SERVICE_UNAVAILABLE`、`INTERNAL_ERROR`；新增 `HTTPException`（Starlette）handler 依狀態碼補預設 `error_code`（含未知路由 404、405 與 Clerk 的 403）；新增 `RequestValidationError` handler，拿掉每一項的 `input`、`ctx`，不記 request body。`backend/main.py` 註冊。
- `backend/services/google_calendar.py`、`backend/services/google_oauth.py`、`backend/routers/google_calendar.py`：依需求 4 分類 Google 的錯誤（讀回應的 `error.errors[].reason`），狀態碼維持目前的值。
- `backend/platforms/github.py`、`jira.py`、`moodle.py`、`sync.py`、`router.py`：依需求 5 分開「重試」與「`X-Auth-Error`／`error_code`」。做法是讓平台丟出的例外帶上 `error_code` 與「是否算憑證失效」，`sync_platform_items` 的重試仍只看「是否可重試」，`auth_error` 改看「是否算憑證失效」；router 沒有舊資料時的狀態碼照目前依例外類別決定。連結帳號的驗證（`fetch_*_userinfo`、Moodle `_verify`）依需求 4。
- `backend/crud/linked_account.py`、`backend/schemas/linked_account.py`：列表遇到解不開的帳號標 `needs_reauth`；PATCH 用已存的憑證解不開時回 `REAUTH_REQUIRED`，狀態碼維持 500（不能直接丟 `ReauthRequiredError`：它會轉成 401）。凡是 `error_code` 和目前狀態碼對應的 `AppError` 類別不同的情況，都要能指定狀態碼，或用狀態碼相同的類別帶上 `error_code`。
- `backend/crud/user.py`、`backend/crud/linked_account.py`、`backend/routers/linked_account.py`：沒有可更新的欄位帶 `INVALID_REQUEST`，狀態碼維持 404。
- `backend/core/cache.py`、`backend/crud/schedulable_items.py`、`backend/routers/pr_review_webhook.py`、`backend/routers/schedule.py`、`backend/routers/user.py`、`backend/routers/manual_task.py`：需求 2、4 列的錯誤改丟帶 `error_code` 的 `AppError`，狀態碼維持目前的值（例如 Redis 失敗仍回 500，帶 `SERVICE_UNAVAILABLE`）。

**前端**

- `frontend/utils/errorMessages.ts`：新增讀 `error_code` 的函式；`isNotLinkedError`、`isAuthError`、`isAlreadyLinkedError`、`isSuggestionExpiredError`、`getFriendlyErrorTitle` 改依 `error_code`，沒有 `error_code` 時依需求 7 退回。
- `useSchedule.ts`、`useGoogleCalendar.ts`、`usePlatformItems.ts`、`useTaskForm.ts`、`useLinkedAccount.ts`、`useUserSync.ts`：依需求 7；連結帳號失敗時顯示 `detail`。
- `frontend/types/linkedAccount.ts`、`frontend/components/header/AccountSettings.vue`、`useLinkedAccount.ts`：`needs_reauth` 當成已連結、儲存走 PATCH；`usePlatformItems.ts`：`needs_reauth` 時不顯示「尚未綁定」。
- `useGoogleCalendar.ts`、`GoogleCalendarEmbed.vue`、`Dashboard.vue`（目前用 `:connect="isConnected"` 決定是否嵌入，要多傳卡片狀態；`frontend/tests/components/Dashboard.test.ts` 的 mock 同步）：卡片狀態只依 `NOT_LINKED`、`REAUTH_REQUIRED` 改變；其他錯誤保留上次載入成功的清單，從沒成功過顯示「Google 行事曆暫時無法載入，請稍後再試」；`/oauth/status` 失敗不設成未連接，照需求 7 維持最近一次已知的結果；已知的結果只存在 composable 的記憶體（不新增持久化），記下所屬的 Clerk 使用者 id，登出或換使用者時清除；`AccountSettings.vue` 的按鈕在 `needsReconnect` 時顯示「重新連接 Google Calendar」，從沒成功取得狀態時不顯示「已連接」標記。
- `usePlatformItems.ts`、`GithubIssuesList.vue`、`JiraIssuesList.vue`、`MoodleAssignmentsList.vue`：讀帳號列表失敗時不設 `notLinked`，照需求 7 維持最近一次已知的結果；登出或換使用者時清除。
- `useGoogleOAuthCallback.ts`：失敗時顯示 `detail`。`useScheduleWizard.ts`、`useTaskForm.ts` 維持以 `detail` 取代預設說明。
- 各 composable 的 `console.error`：只記 status 與 `error_code`。

**文件**：`docs/api.md`、`backend/README.md`（需求 8）。

**測試**：integration 測試斷言每種情況的狀態碼與 `error_code`（需求 4、5 每一列）；unit 測試分類函式；前端 vitest 測 `errorMessages.ts` 與受影響的 composable。

**放棄的做法**

- **router 的 `HTTPException` 用 `detail={...}` 帶 `error_code`**：第三階段改成 `AppError` 時要全部再改一次。
- **第三階段併進來，所有 `HTTPException` 都改成 `AppError`**：範圍變大，和這一階段的行為改變混在一起，審查與回滾都難。
- **外部平台把限流、SSO 故障改丟 `UpstreamError`**：沒有舊資料時會從 401 變 502，也會開始重試，違反「狀態碼不變」與「重試不變」。
- **帳號列表沿用 `status` 欄位回 `"reauth_required"`**：`status` 是連結時存進資料庫的值，混進算出來的狀態，讀的人會以為資料庫裡就是這個值。
- **Google、GitHub 的 403 一律算限流**：權限不足時會被當成「稍後再試」，使用者一直等。
- **Moodle 讀登入頁的錯誤訊息元素**：比較準，但要先實際登入確認學校頁面的元素，目前沒有依據。

## 測試對應

| AC | 測試 |
|---|---|
| AC1 | integration：`test_google_calendar_api.py`、`test_schedule_api.py` 模擬 Google 403 各 reason、其他 4xx、5xx，斷言狀態碼與 `error_code`；vitest：`useSchedule` 依 `error_code` 的畫面；`useGoogleCalendar` 斷言 `isConnected`、`needsReconnect` 的狀態，以及「曾載入成功後失敗時保留清單」「從沒成功過時的暫時無法載入狀態」；`AccountSettings` 在 `needsReconnect` 時的按鈕文字；元件測試：`GoogleCalendarEmbed.test.ts` 從沒載入成功時顯示暫時無法載入的文字 |
| AC2 | integration：每種 `AppError` 與 `HTTPException`、未知路由、405、沒帶 JWT 的回應都有 `error_code` |
| AC3 | integration：既有斷言狀態碼的測試全部保留並通過；新增的測試同時斷言狀態碼 |
| AC4 | integration：`test_linked_account_api.py` 少送欄位，斷言 422、`VALIDATION_ERROR`、回應裡沒有送出的值 |
| AC5、AC6 | unit：`test_platform_sync.py`、`test_github_platform.py`、`test_jira_platform.py`；integration：`test_github_api.py`、`test_jira_api.py` 依需求 5 每一列，斷言重試次數、狀態碼、`error_code`、`X-Auth-Error`；vitest：`usePlatformItems` 收到 `UPSTREAM_RATE_LIMITED` 時不要求重新連結 |
| AC7 | unit：`test_moodle_platform.py`（登入頁比對、`TimeoutException`）；integration：`test_moodle_api.py`；vitest：`usePlatformItems` 收到 `UPSTREAM_*` 時不要求重新連結 |
| AC8 | integration：`test_linked_account_api.py` 連結與 PATCH 各情況（含 GitHub、Jira 的 400、沒有限流特徵的 403、404、3xx，斷言狀態碼仍是 403）；vitest：`useLinkedAccount` 顯示 `detail`，`useTaskForm` 刪除時遇到 `REAUTH_REQUIRED` 提示重新連結；另外每種情況同時斷言狀態碼與 `error_code`：401（401）、Jira 404（403）、Jira DNS 找不到（502，用 `socket.gaierror` 造成的 `ConnectError`）與一般連不上（502）、5xx（403）、429 與 GitHub 限流 403（403）、逾時（502）、Moodle 帳密錯（401）與 WebDriver 錯誤（502） |
| AC9、AC10 | integration：`test_linked_account_api.py` 放一個解不開的帳號，再 PATCH 完整憑證後 `needs_reauth: false`；unit：解密失敗不呼叫刪除；vitest：`useLinkedAccount` 遇到 `needs_reauth` 時當成已連結、儲存走 PATCH、要求完整憑證 |
| AC11 | unit：`test_google_calendar_router.py` 各 Google 回應；vitest：`useGoogleOAuthCallback` 失敗時顯示 `detail` |
| AC12 | vitest：`errorMessages.test.ts` 依 `error_code` 與沒有 `error_code` 的退回；`useSchedule` 確認排程收到 `NOT_LINKED` 時跳錯誤；`useUserSync` 有與沒有 `error_code` 時的文字；`usePlatformItems` 收到 `NOT_LINKED` 時設成尚未綁定 |
| AC13 | unit：`test_logging.py` 或 handler 測試斷言 422 的 log 沒有 request body；integration 斷言 `detail` 沒有第三方回應原文 |
| AC14 | 讀 `docs/api.md`、`backend/README.md` |
| AC15 | `gh api repos/{owner}/{repo}/pulls/<PR> --jq .body` |
| AC16 | integration：需求 4、5 每一列斷言 `detail` |
| AC17 | vitest：`useLinkedAccount` 失敗時 `console.error` 的參數沒有 body 與 Authorization |
| AC18 | unit：`credentials_from_account` 丟 `ValueError` 與其他例外時的結果；integration：帳號列表遇到其他例外回 500 |
| AC19 | integration：405 的 `Allow` header、未列到的狀態碼；unit：handler 處理帶 `WWW-Authenticate` 的 `HTTPException`（`core/security.py` 的 401 用真實請求打不到：Clerk library 先回 403） |
| AC20 | vitest：`useGoogleCalendar` 的 `/oauth/status` 失敗、`usePlatformItems` 的帳號列表失敗時的狀態；元件測試：`GoogleCalendarEmbed.test.ts` 顯示「Google 行事曆暫時無法載入，請稍後再試」、不顯示「尚未連接」；`JiraIssuesList.test.ts`、`MoodleAssignmentsList.test.ts` 與新增的 `GithubIssuesList.test.ts` 在前置檢查失敗時顯示「暫時無法載入，請稍後再試」、不顯示「尚未綁定」；vitest：`useGoogleCalendar`、`usePlatformItems` 分別測「先成功再前置檢查失敗」（保留清單與上一次狀態）與「從沒成功過」；`AccountSettings` 從沒成功取得狀態時不顯示「已連接」；另外測「先 `REAUTH_REQUIRED`（或尚未連接、`needs_reauth`）再前置檢查失敗，維持該畫面」與「登出再以另一個使用者登入後前置檢查失敗，不顯示先前的清單」 |
| AC21 | unit：`test_exception_handlers`（新檔或既有 handler 測試）：只指定 `error_code`、指定狀態碼、類別預設三種情況，類別預設包括 `AccessDeniedError` 沒有指定時是 `INVALID_CREDENTIALS`／403；AC3 的 integration 測試 |
| AC22 | integration：GitHub 回應帶特定字串、Moodle 登入失敗時，錯誤回應的 `detail` 沒有那些內容；Jira 回應帶特定字串時同樣斷言 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
