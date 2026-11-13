# API 錯誤回應第二階段：狀態碼依 error_code 查對照表

- 狀態：已核准
- 等級：高風險（改本系統登入失敗的回應與 Clerk 驗證流程、外部平台同步的錯誤回應、前後端 API 契約）
- issue：#82
- PR：#86

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/82

[ADR 0011](../decisions/0011-api-error-status-codes.md) 定下錯誤回應的設計：狀態碼表示類別，`error_code` 表示原因。[docs/specs/issue-62-status-codes.md](issue-62-status-codes.md) 分三階段修改；第一階段（[docs/specs/issue-77-error-codes.md](issue-77-error-codes.md)，PR #79）依原因加了 `error_code`，前端改成依 `error_code` 判斷，但狀態碼維持舊值（ADR 0011「過渡期間」）。這是第二階段：狀態碼照對照表。

目前同一個 `error_code` 搭配不同的狀態碼，例如 `UPSTREAM_RATE_LIMITED` 是 400、401、403 或 502，`INVALID_REQUEST` 是 400、404 或 500，`REAUTH_REQUIRED` 是 401 或 500；外部服務限流、逾時與 Redis 故障被算成 4xx、502 或 500，監控分不出「該修程式」和「等對方恢復」。

### 目前的做法

- **狀態碼的來源**：`backend/core/errors.py` 每個 `AppError` 子類別有過渡期間的預設狀態碼，丟的時候可以另外指定 `status_code`；`backend/core/exception_handlers.py:26-27` 照實回傳。明確指定和對照表不同狀態碼的地方：`backend/platforms/router.py:64`、`:79`、`:89`；`backend/platforms/jira.py:176`；`backend/platforms/moodle.py:234`；`backend/platforms/http_errors.py:96`；`backend/services/google_calendar.py:48`；`backend/routers/pr_review_webhook.py:60`、`:186`、`:189`；`backend/crud/schedulable_items.py:37`；`backend/crud/user.py:34`；`backend/crud/linked_account.py:78`。
- **router 的 `HTTPException`**（第三階段才改成 `AppError`）：`exception_handlers.py:31-47` 依狀態碼補 `error_code`，狀態碼照原樣回傳。
- **Redis 故障**：`exception_handlers.py:72-75` 回 500 `SERVICE_UNAVAILABLE`；資料庫連不上回 503（`:62-64`）。
- **本系統登入**：`ClerkHTTPBearer(auto_error=True)`（`backend/core/security.py:20`）在 token 缺少、scheme 錯誤或解不開時都丟 403；`_decode_token` 用 `except Exception` 吞掉所有例外，包括抓 JWKS 失敗。PyJWT 2.14.0 的 `PyJWKClient.fetch_data` 只把 `URLError`、`TimeoutError` 包成 `PyJWKClientConnectionError`（`jwt/jwks_client.py:164-169`）；讀回應時的斷線、回應不是 JSON、JWKS 沒有 key 會丟其他例外（需求 3 列出實測結果）。
- **外部限流的 `Retry-After`**：目前不轉送。GitHub 判斷限流時讀得到 `retry-after` header（`backend/platforms/http_errors.py:22-23`）。
- **確認排程的 `failed`**：`FailedConfirmation` 只有 `task_id`、`title`、`reason`（`backend/schemas/schedule.py:33-37`）。寫入前檢查不通過的原因在 `backend/services/scheduler.py:368-380`；寫入 Google 失敗一律「寫入 Google Calendar 失敗，請稍後再試」（`backend/services/google_calendar.py:170-177`）。前端把 `failed` 的原因列在 toast（`frontend/composables/useSchedule.ts:86-89`）。
- **排程的外部 id 不存在**：`PUT /schedule/reorder`、`PATCH /schedule/tasks/fields`、`/done` 遇到外部來源不存在或不屬於自己的 id 時靜默回 200（`backend/crud/schedulable_items.py:32-48` 的 `_external_id`、`_update_external`，`:147-152` 的 `set_done` 外部分支）；手動任務不存在時，reorder 回 400（`backend/crud/manual_task.py:353-356`，issue-62 列為可接受的既有設計），fields、done 回 404。
- **前端**：判斷都看 `error_code`；只有沒有 `error_code` 的回應依狀態碼退回（`frontend/utils/errorMessages.ts`；`frontend/composables/useUserSync.ts:14-26`）。
- **文件**：`docs/api.md:3` 寫「沒帶會被擋下（403）」；「錯誤回應」一節寫明過渡期間狀態碼維持舊值；各 endpoint 的說明欄記錄舊狀態碼。
- **request 識別資訊**：後端沒有 request ID 機制；Cloud Run 會在每個請求帶 `X-Cloud-Trace-Context` header。

## 需求

1. **狀態碼依 `error_code` 查對照表**：
   - 新增後端的對照表（`error_code` → 狀態碼），內容和 ADR 0011 的對照表相同，是程式裡唯一決定錯誤狀態碼的地方。
   - `AppError` 不再有 `status_code`：拿掉建構參數與各子類別的 `default_status_code`；子類別只保留預設的 `error_code`。丟例外的地方只決定 `error_code`。
   - 所有錯誤 handler（`AppError`、`HTTPException`、422、429、資料庫、Redis、未處理的例外）都用對照表決定狀態碼。`HTTPException` 先照目前依狀態碼補 `error_code`（`exception_handlers.py:31-40`），再依 `error_code` 查表；原本的 header 照樣保留。
   - webhook 沒設定簽章密鑰時用 `INVALID_WEBHOOK_SIGNATURE`，對照表的值就是 401，符合 ADR 0011「例外」；程式註解寫明這一點。ADR 0011 要求的 error log：兩個 webhook 的密鑰（`CLERK_WEBHOOK_SIGNING_SECRET`、`GITHUB_WEBHOOK_SECRET`）在啟動時就讀得到，所以沒設定時在啟動時記一次 error log；請求時不再重複記 error（避免每個請求都記一筆）。log 只寫哪一個設定缺少，不含密鑰值、簽章與請求內容。
2. **對照表沒有的 `error_code`**：對外一律回 500、`error_code` 是 `INTERNAL_ERROR`、`detail` 是固定的「伺服器發生未預期的錯誤，請稍後再試」，不回傳原始的 `error_code` 與 `detail`。log 記 error，內容包括原始的 `error_code`、例外（含 stack trace）、HTTP 方法與路徑，以及 request 識別資訊（`X-Cloud-Trace-Context` header，有的話）。
3. **本系統登入失敗**：驗證分成兩步。兩步的界線看「呼叫的是哪一個步驟」，不看例外類別（同一個 `PyJWKClientError` 在兩步都可能出現）；每一步只接自己預期的例外，不用一個大範圍的 `except Exception` 包住整個流程：
   1. **取得 signing keys**（向 Clerk 抓 JWKS 與解析回應，包括 `kid` 找不到時的重新抓取）。PyJWT 2.14.0 實際丟出的例外（實測）：
      - 504 `UPSTREAM_TIMEOUT`：例外鏈（`__cause__`、`__context__`，或 `URLError.reason`）裡有 `TimeoutError`。實際有兩種形式：連線時逾時是 `PyJWKClientConnectionError` → `URLError(reason=TimeoutError)`（`TimeoutError` 在 `URLError` 的 `__context__` 與 `reason`）；讀回應時逾時是 `PyJWKClientConnectionError` → `TimeoutError`。
      - 502 `UPSTREAM_ERROR`：其他的 `PyJWKClientConnectionError`（連線被拒、HTTP 錯誤狀態碼）；原樣丟出的 `http.client.HTTPException`（例如 `RemoteDisconnected`、`IncompleteRead`）與 `OSError`；回應不是 JSON 的 `ValueError`（`json.JSONDecodeError`）；`PyJWKSetError`（沒有 `keys`、`keys` 是空的、key 都不能用）；這一步丟的 `PyJWKClientError`（JSON 不是 object、沒有 signing key）。
   2. **驗證 token**（在第 1 步成功之後）：
      - 401 `UNAUTHENTICATED`：沒帶 token、scheme 不是 Bearer；解析 header 失敗（`get_unverified_header` 只丟 `InvalidTokenError` 系列，實測）；比對 `kid` 找不到；`jwt.decode` 的簽章無效、過期、claims 不符（`PyJWTError` 系列）。
      - `kid` 找不到時，PyJWKClient 只有在離上次成功抓取超過 `cooldown_duration`（預設 30 秒，`ClerkHTTPBearer` 沒有改）時才重新抓一次：重新抓這一步失敗算第 1 步的錯誤（502／504）；不能重新抓（cooldown 內）或重新抓之後仍找不到是 401。`kid` 找不到不一定是 Clerk 故障，也可能是 token 用了不存在的金鑰。
   - 兩步以外的非預期例外（程式本身的 bug）不轉成 401 或 502，照未處理的例外回 500 `INTERNAL_ERROR` 並記 log。
   - 做法：包裝 `ClerkHTTPBearer`（子類別覆寫解碼）。不能只把 `get_signing_key_from_jwt` 拆成兩個呼叫：抓 JWKS、比對 `kid`、cooldown 判斷與重新抓取都在 `PyJWKClient.get_signing_key` 裡（`jwt/jwks_client.py:246-267`），而「`kid` 找不到」和「重新抓之後 JWKS 格式錯」丟的是同一個 `PyJWKClientError`。子類別照下面的順序自己呼叫，每一步只接自己預期的例外：
     1. `jwt.get_unverified_header` 解析 header：失敗回 401（先於抓 keys，所以 Clerk 故障時格式錯誤的 token 仍是 401）。
     2. `get_signing_keys()` 取得 keys：第 1 步的錯誤（502／504）。另外，只在這一個呼叫的範圍內，把 `AttributeError`、`TypeError` 也歸成 502 `UPSTREAM_ERROR`：JWKS 的 `keys` 裡有元素不是 object（例如 `{"keys": ["x"]}`）時，PyJWT 會丟 `AttributeError`（`jwt/api_jwk.py:150-157`）。只包這一個呼叫，不擴大到整個驗證流程；log 記錄例外與 stack trace。步驟 4 的 `get_signing_keys(refresh=True)` 同樣處理。
     3. `match_kid` 比對 `kid`。
     4. 找不到時，照 `PyJWKClient` 原本的 cooldown 條件（`jwk_set_cache`、`_last_successful_fetch`、`cooldown_duration`，`jwt/jwks_client.py:251-259`）並在 `_client_lock` 內，才用 `get_signing_keys(refresh=True)` 重新抓：第 1 步的錯誤（502／504）；成功時照原本的方式更新 `_last_successful_fetch`。必須保留 cooldown 與 lock：否則任何人帶隨便的 `kid` 打 API，每個請求都會向 Clerk 抓一次 JWKS，而且是會卡住 event loop 的同步請求。cooldown 的起點是「上次**成功**抓取的時間」（`_last_successful_fetch`，只在抓取成功時更新，`jwt/jwks_client.py:177`、`:259`；「成功」指 HTTP 回應與 JSON 解析成功，JSON 格式正確但 JWKS 結構錯誤時起點仍會更新）：上次成功抓取後 30 秒內，帶任意 `kid` 的請求不會重新抓；Clerk 故障、而且距離上次成功抓取已超過 30 秒時，重新抓會失敗、起點不會更新，所以之後每個帶未知 `kid` 的請求都會再抓一次。另外 JWKS 快取（300 秒）過期後，Clerk 仍故障時，每個請求都要重新抓。兩者都是 library 既有的行為，目前的程式也一樣（見「不做」與規格審查紀錄的「已接受的風險」）。覆寫 `_decode_token` 時保留參數名稱 `token`（`__call__` 用關鍵字呼叫）。
     5. 仍找不到：401。
     6. `jwt.decode`（JWKS 的 key、`RS256`、issuer 與期限驗證，參數和 library 原本相同）：失敗回 401。
     `detail` 是固定的文字，不帶例外內容；第 1 步的錯誤記 log。沒帶 token、scheme 不是 Bearer 在 `ClerkHTTPBearer.__call__` 解碼之前就擋下（403 `HTTPException`），照 handler 補成 `UNAUTHENTICATED` 再查表成 401。
   - 子類別依賴 `fastapi-clerk-auth` 與 PyJWT 的私有成員（`ClerkHTTPBearer._decode_token`、`PyJWKClient._last_successful_fetch`、`_client_lock`），所以 `backend/requirements.txt` 鎖定 `PyJWT==2.14.0`、`fastapi-clerk-auth==0.0.9`；升級這兩個套件時要重新確認這一節的例外形式與私有成員。
4. **外部限流帶 `Retry-After`**：`UPSTREAM_RATE_LIMITED` 的回應，在外部服務的回應帶 `Retry-After` header、而且值是非負整數秒數時，原樣放進我方回應的 `Retry-After`。不從 `x-ratelimit-reset` 或其他 header 換算；沒帶或不是秒數就不帶。涵蓋 GitHub、Jira 抓項目與連結帳號，以及 Google（包括換 token 時）。
5. **確認排程的 `failed`**：`FailedConfirmation` 加 `error_code`（字串或 `null`），`frontend/types/` 同步。
   - 寫入 Google 失敗：依原因給 `error_code`（分類照第一階段 Google 的規則，`docs/specs/issue-77-error-codes.md` 需求 4），`reason` 是和原因一致的固定文字。Google 回 401 是 `REAUTH_REQUIRED`（寫入迴圈開始前剛驗證或換過 token，所以不再換新）；400 是 `INTERNAL_ERROR`；限流、逾時、5xx 與連不上照第一階段（`UPSTREAM_RATE_LIMITED`、`UPSTREAM_TIMEOUT`、`UPSTREAM_ERROR`）。
   - 寫入前檢查不通過與「前一個階段寫入失敗」：`error_code` 是 `null`，`reason` 不變。
   - 前端：`failed` 裡有任何一筆是 `REAUTH_REQUIRED` 時，除了原本列出失敗項目的 toast，另外顯示「重新連接 Google Calendar」的提示（沿用 `useGoogleCalendarAuth` 的 `reauthToast`）。
6. **排程的外部 id 不存在**（只套用在 `PUT /schedule/reorder`、`PATCH /schedule/tasks/fields`、`/done`）：
   - `PATCH /schedule/tasks/fields`、`/done`：外部來源的 id 不存在或不屬於自己時回 404 `NOT_FOUND`，和手動任務不存在時的訊息相同。`PATCH /schedule/tasks/fields` 沒帶任何要更新的欄位時（body 只有 `task_id`），也先檢查 id（前綴、格式、是否存在）再回 200；手動任務不存在時同樣回 404（原本 `backend/routers/schedule.py:63-65` 在沒有欄位時直接回 200、不檢查 id）。
   - `PUT /schedule/reorder`：一次送來整份清單的新順序。**所有會回 400 的檢查都在寫入任何項目之前完成**：id 不存在或不屬於自己（外部與手動）、外部 id 格式錯誤、來源前綴不認得、主任務不能排序、階段之間的優先序不合規則（`backend/crud/manual_task.py:358`、`:370-374`）。全部合法才寫入；任何一項不合法時整批回 400 `INVALID_REQUEST`、**什麼都不寫**。id 不存在時訊息和手動任務相同（「包含不屬於你的任務 id」），列出的是使用者送出的組合 id，不透露資料是否存在。目前是一筆一筆寫入、寫到一半才發現手動 id 不存在而回 400（`backend/crud/schedulable_items.py:96-111` 的寫入先於 `backend/crud/manual_task.py:351-356` 的檢查），一併改成先檢查。
   - 來源前綴不認得（例如 `foo:1`，或沒有冒號）是組合 id 格式錯誤：三個 endpoint 都回 400 `INVALID_REQUEST`（目前靜默回 200，`backend/crud/schedulable_items.py:42-44`、`:147-149`）。
   - 確認排程把事件 id 寫回外部項目時（`set_calendar_event_id_for_composite`，共用 `_update_external`）維持目前的行為：找不到也不丟錯。否則 Google 事件已經建立，整次確認卻失敗，Google 上會留下沒記錄的事件。
7. **前端的重送規則**：前端呼叫本後端的請求，改用下面的規則，取代 ofetch 預設的自動重送（GET 遇到 408、409、425、429、500、502、503、504 重送 1 次，只看狀態碼）；非本後端的請求維持 ofetch 的預設。原則是系統的暫時性錯誤要重送，重送多少次都不會成功的永久性錯誤不重送，並有硬性上限、遵守限流：

   | 項目 | 規則 |
   |---|---|
   | 上限 | 每次呼叫總共最多 3 次（第 1 次加上最多 2 次重送） |
   | 適用範圍 | 瀏覽器端的 `$fetch`（包括 `$fetch.raw`）呼叫**本後端**的請求。是不是本後端：把請求的 URL 用 `new URL(request, location.href)` 解析，和 `new URL(apiBaseUrl)` 比較，`origin` 相同、而且 path 等於 `apiBaseUrl` 的 path 或在它之下（以 `/` 為界，不是字串前綴）才算。比較前先把 base path 正規化成以 `/` 結尾（`/` 維持 `/`，`/api` 變成 `/api/`）；請求的 path 等於去掉結尾 `/` 的 base path，或以正規化後的 base path 開頭，才算本後端。目前開發與正式環境的 `apiBaseUrl` 都只有 origin（`frontend/nuxt.config.ts:16`），path 是 `/`，所以同一個 origin 的請求都算本後端；不用 `startsWith(apiBaseUrl)`，避免 `https://api.example.com.evil.com` 這類網址被誤判。相對網址（例如 `/api/leetcode`）解析後是前端自己的 origin，不算本後端 |
   | 非本後端的請求 | 不套用這張表，維持 ofetch 原本的預設（GET 遇到 408、409、425、429、500、502、503、504 或沒有回應時重送 1 次）：自訂 hook 對非本後端的請求不改動 `context.options`。例如 Hacker News（`frontend/components/dashboard/News.vue`）、`/api/leetcode` |
   | 原生 `fetch` | `useUserSync`（`frontend/composables/useUserSync.ts:68`、`:83`）用原生 `fetch`，維持目前不重送 |
   | 可以重送的請求 | GET，以及帶 `Idempotency-Key` 的 POST（重送不會重複建立）；其他 POST、PUT、PATCH、DELETE 不重送 |
   | 暫時性錯誤（重送） | 沒有收到回應（網路中斷、逾時）；沒有 `error_code` 的 502、503、504（Cloud Run 冷啟動或過載）；`SERVICE_UNAVAILABLE`；`UPSTREAM_TIMEOUT` |
   | 永久性錯誤（不重送） | 所有 4xx；`INTERNAL_ERROR`；`UPSTREAM_ERROR`（同一個 code 涵蓋外部 5xx 與無法判斷原因的 4xx，前端分不出來；外部的暫時性錯誤由後端 `sync.py` 重試，前端再重送會變成倍數） |
   | 限流（不重送） | `RATE_LIMITED`、`UPSTREAM_RATE_LIMITED`、沒有 `error_code` 的 429；畫面照舊顯示「請求太頻繁，請稍後再試」 |
   | 其他情況（不重送） | 本後端的回應中，上面沒有列出的情況，例如沒有 `error_code` 的 500、501 |
   | 間隔 | 第 1 次重送前等 0.5 秒，第 2 次等 1 秒；回應帶 `Retry-After` 時取兩者中較長的 |

   - **`Retry-After` 的完整流程**：後端照需求 4 把外部回應的 `Retry-After` 放進我方的錯誤回應 → 後端 CORS 設定 `expose_headers` 加上 `Retry-After`（`backend/main.py:55-61` 目前沒有設定 `expose_headers`；前後端不同來源時，`Retry-After` 不在瀏覽器允許前端讀取的安全清單內，不加就讀不到）→ 前端在重送判斷裡用 `response.headers.get('Retry-After')` 讀取。因為限流不重送，而本後端只在 `UPSTREAM_RATE_LIMITED` 帶 `Retry-After`，目前沒有會用到這段讀取的情況，保留給之後帶 `Retry-After` 的暫時性錯誤；讀不到或不是秒數時照固定的間隔。
   - **讀不到狀態碼的回應**：上面的表以前端讀得到狀態碼為前提。前後端不同來源時，Cloud Run 平台自己回的回應（例如它的 429、沒有 `error_code` 的 500）不經過後端的 `CORSMiddleware`，沒有 `Access-Control-Allow-Origin`，瀏覽器只給前端網路錯誤，前端分不出它和「沒有收到回應」，所以照暫時性錯誤重送；上限、間隔與可以重送的方法仍然適用。這是已知限制，這次不處理。
   - 後端呼叫外部平台的重試（`backend/platforms/sync.py` 最多 2 次）不變。
   - 非同步工作的重送上限是 5 次：目前系統沒有非同步工作，這次不實作，寫進 `backend/README.md`「錯誤處理」當作之後新增非同步工作時的規則。
8. **文件**：`docs/api.md` 開頭的「沒帶會被擋下」改成 401；「錯誤回應」一節拿掉過渡期間的說明，改成狀態碼照 ADR 0011 的對照表；各 endpoint 說明欄的狀態碼改成新的值。`backend/README.md`「錯誤處理」寫明丟例外時只選 `error_code`，狀態碼由對照表決定，並寫上重送原則（需求 7：暫時性錯誤才重送、同步呼叫上限 3 次、非同步工作上限 5 次、遵守限流）；`:70` 的「由全域 handler 回 503 或 500」照 Redis 改成 503 一起更新。
9. PR 描述要 `Closes #82`。

## 不做

- 不把 router 的 `HTTPException` 改成 `AppError`：第三階段（這個 PR 合併後才開 issue）。
- 不新增 request ID 機制：只記 Cloud Run 已經帶的 `X-Cloud-Trace-Context`。
- 不改後端呼叫外部平台的重試行為（`backend/platforms/sync.py` 維持最多 2 次）與哪些錯誤算可重試；前端的重送規則照需求 7 改。
- 不改 ADR 0011：對照表與分類原則不變；「過渡期間」一節是當時的紀錄，照 `docs/decisions/README.md` 不改寫。
- 不處理 `PyJWKClient` 的同步請求會卡住 event loop 的問題（和狀態碼無關）。

## 假設

1. 前端所有錯誤判斷都依 `error_code`，只有沒有 `error_code` 的回應依狀態碼退回（第一階段 AC12）；所以本後端產生的錯誤回應改狀態碼，不改變畫面。例外是 `error_code` 本身改變的情況：AC4 的 JWKS 失敗、AC7、AC8。
2. 外部服務的 `Retry-After` 秒數依各自的官方文件（GitHub REST API「Rate limits」、Google Calendar「Handle API errors」）；HTTP 日期格式的 `Retry-After` 不轉送。
3. `fastapi-clerk-auth` 0.0.9 與 PyJWT 2.14.0 的私有成員與例外形式如需求 3 所述（實測）；升級時要重新確認。

## 驗收條件

| # | 條件 | 類型 |
|---|---|---|
| AC1 | 每個本後端產生的錯誤回應，狀態碼都是 ADR 0011 對照表中該 `error_code` 的值；後端的對照表和 ADR 0011 的對照表一致 | 不變條件 |
| AC2 | `AppError` 與子類別沒有指定狀態碼的參數或屬性；丟例外的地方只決定 `error_code` | 不變條件 |
| AC3 | 對照表沒有的 `error_code`：回 500、`INTERNAL_ERROR`、固定的 `detail`，回應不含原始的 `error_code` 與 `detail`；log 有原始的 `error_code`、例外、方法與路徑、`X-Cloud-Trace-Context`（有的話） | 不變條件 |
| AC4 | 沒帶 JWT、scheme 不是 Bearer、token 格式錯誤、簽章無效、過期、`kid` 找不到對應的 key：401 `UNAUTHENTICATED`；抓 Clerk JWKS 連不上或連線中斷、回應不是 JSON 或沒有 key：502 `UPSTREAM_ERROR`；逾時：504 `UPSTREAM_TIMEOUT`；JWKS 的 `keys` 裡有元素不是 object，或 key 的欄位型別錯誤：502 `UPSTREAM_ERROR`；驗證流程中其他非預期的例外：500 `INTERNAL_ERROR`；`detail` 不含例外內容，log 有例外資訊 | 不變條件 |
| AC5 | 外部服務限流：503 `UPSTREAM_RATE_LIMITED`；外部回應帶秒數的 `Retry-After` 時，我方回應帶同樣的值；沒帶、或是日期格式時不帶；跨來源的回應有 `Access-Control-Expose-Headers` 包含 `Retry-After`，前端讀得到 | 不變條件 |
| AC6 | webhook 簽章錯誤與沒設定簽章密鑰：401 `INVALID_WEBHOOK_SIGNATURE`；沒設定密鑰時在啟動時記一次 error log，請求時不重複記 error；log 不含密鑰值、簽章與請求內容 | 不變條件 |
| AC7 | 確認排程時寫入 Google 失敗的 `failed` 項目帶依原因的 `error_code` 與一致的 `reason`（401 `REAUTH_REQUIRED`、400 `INTERNAL_ERROR`、限流、逾時、5xx 照第一階段）；寫入前檢查不通過的項目 `error_code` 是 `null`、`reason` 不變；有任何一筆 `REAUTH_REQUIRED` 時，畫面另外提示重新連接 Google Calendar | 使用者行為 |
| AC8 | `PATCH /schedule/tasks/fields`、`/done` 的外部 id 不存在或不屬於自己：404 `NOT_FOUND`；`fields` 沒帶任何要更新的欄位時也一樣檢查（外部與手動任務不存在 404、前綴不認得或 id 格式錯 400，id 合法才回 200）；`PUT /schedule/reorder` 回 400 的任何情況（id 不存在或不屬於自己、外部 id 格式錯、前綴不認得、主任務、階段優先序不合規則），資料庫的順序都完全沒有改變；id 不存在時是 400 `INVALID_REQUEST`、和手動任務同一個訊息；來源前綴不認得：三個 endpoint 都是 400；確認排程寫回事件 id 時外部項目不存在，確認仍成功 | 不變條件 |
| AC9 | 除了 AC4 的 JWKS 失敗（`error_code` 從 `UNAUTHENTICATED` 變成 `UPSTREAM_*`）、AC7、AC8 的情況，各畫面顯示的錯誤和改之前相同；外部平台同步的重試次數、`X-Auth-Error`、`X-Data-Stale` 和改之前相同；前端的 `$fetch` 呼叫本後端時照需求 7 重送：暫時性錯誤最多總共 3 次並照間隔等待，永久性錯誤、限流、其他沒列出的情況與不能重送的方法不重送（前端讀得到狀態碼時；讀不到時照需求 7「讀不到狀態碼的回應」）；呼叫非本後端時的重送和改之前相同（ofetch 預設）；`useUserSync` 的原生 `fetch` 維持不重送 | 使用者行為 |
| AC10 | 錯誤回應不帶憑證、token、第三方回應原文；查別人的資料和查不存在的資料回一樣的 404 與訊息 | 不變條件 |
| AC11 | `docs/api.md` 開頭寫 401、「錯誤回應」一節沒有過渡期間的說明、各 endpoint 的狀態碼是新的值；`backend/README.md`「錯誤處理」寫明只選 `error_code` | 不變條件 |
| AC12 | PR 描述有 `Closes #82` | 使用者行為 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中、空資料 | 不改成功回應與載入流程（`failed` 只加一個欄位） |
| 併發 | reorder 改成先檢查再寫入（AC8）；其他寫入流程不變 |
| 資料處理 | 不改資料庫結構；`failed` 的 `error_code` 只在回應裡 |

## 實作計畫

分支 `issue-82-status-codes-phase2`。

**後端**

- `backend/core/error_codes.py`（新增）：`error_code` → 狀態碼的對照表，註解指向 ADR 0011；查表函式在找不到時回 `None`。
- `backend/core/errors.py`：拿掉 `status_code` 參數與 `default_status_code`；`AppError` 可以帶 `headers`（用在 `Retry-After`）。
- `backend/core/exception_handlers.py`：`error_response` 改成依 `error_code` 查表決定狀態碼；查不到時照需求 2 回 500 並記 log；`HTTPException` 先依狀態碼補 `error_code` 再查表，保留 header；資料庫、Redis、422、未處理的例外都經過同一個函式。限流的 handler（`backend/core/rate_limit.py`）也改用它。
- `backend/main.py`：`CORSMiddleware` 加 `expose_headers=["Retry-After"]`（需求 7）。
- `backend/requirements.txt`：鎖定 `PyJWT==2.14.0`、`fastapi-clerk-auth==0.0.9`（需求 3）。
- `backend/core/security.py`：`ClerkHTTPBearer` 的子類別，覆寫解碼，照需求 3 分成取得 JWKS 與驗證 token 兩步，各自只接預期的例外類別。
- `backend/routers/user.py`、`backend/routers/pr_review_webhook.py`：密鑰沒設定時在模組載入（啟動）時記一次 error log（需求 1）。
- 拿掉所有 `AppError(..., status_code=...)`，包括「目前的做法」列的各處，以及值和對照表相同的 `backend/routers/pr_review_webhook.py:55`、`backend/routers/user.py:23`（pyright 會抓到漏掉的）；只留 `error_code`。
- `Retry-After`：`backend/platforms/sync.py` 的 `NonRetryableError`、`UpstreamError` 加可以帶 header 的欄位（不改重試）；`backend/platforms/http_errors.py`、`backend/platforms/router.py`、`backend/services/google_errors.py`、`backend/services/google_calendar.py`（`_google_error`、`_delete_error`）、`backend/services/google_oauth.py`、`backend/routers/google_calendar.py` 判斷限流時帶出外部回應的 `Retry-After`。
- `backend/schemas/schedule.py`、`backend/services/google_calendar.py`、`backend/services/scheduler.py`：`failed` 加 `error_code`（需求 5）。
- `backend/crud/schedulable_items.py`、`backend/crud/manual_task.py`：需求 6。reorder 先檢查所有 id 再寫入；不存在的檢查放在 reorder、fields、done 的路徑，不放進確認排程也會用到的 `_update_external`。

**前端**

- `frontend/types/schedule.ts`：`failed` 加 `error_code`。
- `frontend/composables/useSchedule.ts`：有 `REAUTH_REQUIRED` 時另外顯示 `reauthToast`。
- `frontend/utils/fetchRetry.ts`（新增）：兩個純函式，vitest 直接測。`isBackendRequest(url, apiBaseUrl, currentHref)`：照需求 7「適用範圍」解析 URL、比較 origin 與 path。`decideRetry(...)`：依方法、是否帶 `Idempotency-Key`、狀態碼、`error_code`、`Retry-After`、第幾次，決定要不要重送與等多久。
- `frontend/plugins/*.client.ts`（新增）：用 `$fetch.create(...)` 換掉瀏覽器端的 `globalThis.$fetch`，`create` 的預設值不設 `retry`、`retryStatusCodes`、`retryDelay`（非本後端的請求才會維持 ofetch 原本的預設）；hook 先用 `isBackendRequest` 判斷，不是本後端就直接 return、不改 `context.options`。ofetch 的 hook 不能回傳新的回應，要在 `onRequestError`／`onResponseError` 裡依 `fetchRetry.ts` 的判斷設定 `context.options` 的 `retry`、`retryStatusCodes`、`retryDelay`（ofetch 在 `onError` 讀這三個值），已試的次數記在 `context.options` 的自訂欄位（重送時整個物件會被複製）；`error_code` 從 `context.response._data` 讀（非 JSON 的回應 `_data` 是字串，讀不到 `error_code`，當成沒有 `error_code`），`Retry-After` 從 `context.response.headers` 讀。沒有收到回應時 ofetch 以 500 判斷要不要重送，所以 `retryStatusCodes` 用 `[context.response?.status ?? 500]`；不重送時設 `retry: false`。使用者自己取消的請求（AbortError）ofetch 本來就不重送。`app.config` 不會被 ofetch 讀取，不能用；不加 `.client` 會連 Nitro 伺服器端的 `$fetch` 一起改。

**文件**：`docs/api.md`、`backend/README.md`（需求 8）。

**測試**：既有 integration 測試裡斷言舊狀態碼的地方改成新的值（不改 `error_code` 的斷言）；新增需求 1–6 的測試。

**放棄的做法**

- **各例外類別與丟例外的地方繼續指定狀態碼**：同一個 `error_code` 容易又被配上不同的狀態碼，對照表不是唯一的來源（開發者決定）。
- **對照表沒有的 `error_code` 原樣回傳、狀態碼給 500**：會把內部的原因名稱與文字暴露給呼叫者。
- **把取得 JWKS 這一步的所有例外都當成 Clerk 故障**：`kid` 找不到不一定是 Clerk 故障，程式本身的 bug 也會被誤判成 502。
- **自己寫 JWT 驗證取代 `fastapi_clerk_auth`**：要自己維護 JWKS 快取、簽章與期限驗證；包裝子類別只改例外處理，驗證邏輯沿用 library。
- **從 `x-ratelimit-reset` 換算 `Retry-After`**：要依賴伺服器時鐘，換算錯了反而誤導呼叫者。
- **reorder 的外部 id 不存在回 404**：同一支 API 遇到不存在的手動任務回 400，兩種來源的行為會不一致。

## 測試對應

| AC | 測試 |
|---|---|
| AC1 | unit：對照表和 ADR 0011 對照表的每一列相同（測試裡列出預期的對照）；integration：`test_error_codes_api.py`、`test_error_responses_api.py` 每種 `error_code` 的狀態碼 |
| AC2 | pyright：`AppError(..., status_code=...)` 不再能寫；unit：`test_exception_handlers.py` 的子類別預設 |
| AC3 | unit：handler 收到對照表沒有的 `error_code`，回應是 500 `INTERNAL_ERROR` 與固定 `detail`，log 有原始 `error_code` 與 trace header |
| AC4 | unit：`test_security.py` 用實際的例外形式模擬：沒帶、scheme 錯、token 格式錯、簽章無效、過期；`kid` 找不到（cooldown 內不重新抓，401）與 cooldown 過後重新抓失敗（502／504）；連線時逾時（`URLError(reason=TimeoutError)`，`TimeoutError` 在 `__context__`）、讀回應時逾時（`PyJWKClientConnectionError` → `TimeoutError`）、連線被拒、HTTP 503、`RemoteDisconnected`、`IncompleteRead`、`JSONDecodeError`、`PyJWKSetError`、`keys` 元素不是 object（`AttributeError`，502）、key 的 `n`／`e` 不是字串（`TypeError`，502）；在 `get_signing_keys()` 以外丟的 `AttributeError`（非預期例外）回 500；上次成功抓取後 30 秒內帶任意 `kid` 的 token 不會再抓 JWKS（Clerk 正常、剛抓取成功的情況）；至少一條用真的 `PyJWKClient`、只模擬 `urllib` 這一層（`urllib.request.build_opener` 或 `OpenerDirector.open`，`fetch_data` 不用 `urlopen`，只 patch `urlopen` 會真的連到 Clerk），不整個 mock 掉 `jwks_client`；每個測試自己建立子類別的 instance，不共用模組層級的 `clerk_auth`（JWKS 快取與 `_last_successful_fetch` 會在測試之間互相影響）；測試用的 RSA 金鑰以 `cryptography` 產生 |
| AC5 | integration：`test_github_api.py`、`test_jira_api.py`、`test_linked_account_api.py`、`test_google_calendar_api.py` 的限流情況，帶與不帶 `Retry-After`、日期格式；`test_cors.py` 帶 `Origin` 的請求，回應的 `Access-Control-Expose-Headers` 包含 `Retry-After`；vitest：`fetchRetry.test.ts` 從回應讀 `Retry-After` 決定間隔 |
| AC6 | integration：`test_error_codes_api.py` 的 webhook 測試；unit：`test_user_webhook.py`、`test_pr_review_webhook.py`；unit：密鑰沒設定時模組載入只記一次 error log、請求時不再記 error、log 不含密鑰值 |
| AC7 | integration：`test_schedule_api.py` 確認排程時 Google 回 401、429、逾時、5xx 與寫入前檢查不通過；vitest：`useSchedule` 有 `REAUTH_REQUIRED` 時顯示重新連接的提示 |
| AC8 | integration：`test_schedule_api.py` reorder（外部與手動不存在的 id、外部 id 格式錯、主任務、階段優先序不合規則，每種都斷言所有項目的順序沒變）、fields、done 帶不存在的外部 id 與不認得的前綴；確認排程期間外部項目被刪除，確認仍成功；`fields` 不帶欄位時的不存在的外部 id、不存在的手動任務、不認得的前綴、合法的 id |
| AC9 | vitest：既有的前端測試全部通過；`fetchRetry.test.ts` 逐列測需求 7 的表（每種暫時性、永久性、限流與其他沒列出的情況；GET、帶與不帶 `Idempotency-Key` 的 POST、PUT；第 3 次後不再重送；間隔與 `Retry-After`）；`isBackendRequest` 測：`apiBaseUrl` 沒有 path（`http://localhost:8000`，實際的設定形式）時 `http://localhost:8000/schedule/tasks` 是本後端、`apiBaseUrl` 結尾帶 `/`、base 是 `/api` 時 `/api` 與 `/api/x` 算而 `/api2/x` 不算、`apiBaseUrl` 的字串前綴相同但 origin 不同（例如 `https://api.example.com.evil.com`）、userinfo 形式（`https://api.example.com@evil.com`）、相對網址、不同 port；plugin 的串接用 `$fetch.create(defaults, { fetch: mock })` 測（`apiBaseUrl` 用沒有 path 的形式）：本後端沒有回應時會重送、跨重送總共最多 3 次、不重送的情況不再送出，以及非本後端的 GET 遇到 503 照 ofetch 預設重送 1 次；integration：外部平台同步的重試次數與 header 斷言保留 |
| AC10 | integration：既有的「不帶第三方原文」「別人的資料回 404」斷言保留並通過 |
| AC11 | 讀 `docs/api.md`、`backend/README.md` |
| AC12 | `gh api repos/{owner}/{repo}/pulls/<PR> --jq .body` |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-12 | AC8、需求 6：`PATCH /schedule/tasks/fields` 沒帶欄位時也先檢查 id；測試對應 AC6 的檔名改成實際位置、AC8 補測試 | 開發者決定沒有欄位時也檢查 id（實作審查發現原本直接回 200，手動任務不存在時會從 200 變成 404）→ 需求 6、AC8；檢查過 AC9（前端不會送出沒有欄位的請求，畫面不變）、AC10 不用改 | 開發者 |
| 2026-11-13 | 需求 7 補「讀不到狀態碼的回應」、AC9 註明以讀得到狀態碼為前提 | 開發者決定程式不改、寫明限制（實作審查 #6：跨來源時 Cloud Run 平台自己回的 429、沒有 `error_code` 的 500 沒有 CORS header，前端當成沒有收到回應而重送）→ 需求 7、AC9；檢查過 AC4、AC7、AC8、測試對應 AC9（測的是讀得到狀態碼的情況）不用改 | 開發者 |
