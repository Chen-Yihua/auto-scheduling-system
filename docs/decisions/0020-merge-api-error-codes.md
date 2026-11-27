# 0020. 對外 error_code 只分會改變處理方式的原因，外部服務錯誤用共用規則轉換

- 狀態：已採用
- 日期：2026-11-27

## 背景

[ADR 0011](0011-api-error-status-codes.md) 讓每種錯誤原因都有自己的 `error_code`，對照表累積到 23 個。實際使用後發現兩個問題：

- 有一些 `error_code` 的處理方式和另一個完全相同，前端也沒有分開判斷。例如外部服務限流（`UPSTREAM_RATE_LIMITED`）和本系統限流（`RATE_LIMITED`）在前端顯示同一段訊息；Jira 網域不存在（`INVALID_PLATFORM_DOMAIN`）和憑證錯誤（`INVALID_CREDENTIALS`）都是請使用者修正表單。
- GitHub、Jira 與 Google 的錯誤各自寫了一套轉換：限流、憑證被拒、我方送錯請求、其他錯誤的判斷順序在三個地方重複，例外類別也和 `error_code` 對不上（例如用 `ReauthRequiredError` 帶 `INVALID_CREDENTIALS`）。

## 決定

### 對外的 error_code

- 只有呼叫者的處理方式不同時，才分成不同的 `error_code`。處理方式相同的原因用同一個 `error_code`，原因的細節寫在 `detail` 與 log。
- 下面的 `error_code` 合併：

| 拿掉的 error_code | 改用 | 理由 |
|---|---|---|
| `INVALID_PLATFORM_DOMAIN` | 400 `INVALID_CREDENTIALS` | 都是請使用者修正連結表單 |
| `INVALID_AUTHORIZATION_CODE` | 400 `INVALID_REQUEST` | 使用者重新連接 Google 即可，前端只顯示 `detail` |
| `INVALID_WEBHOOK_SIGNATURE`、`INVALID_SCHEDULER_TOKEN` | 401 `UNAUTHENTICATED` | 都是呼叫者的身分驗證失敗；呼叫者是外部服務，不依 `error_code` 分開處理 |
| `NO_PRIMARY_CALENDAR` | 502 `UPSTREAM_ERROR` | Google 的回應缺少必要內容，已經是 `UPSTREAM_ERROR` 的定義 |
| `UPSTREAM_RATE_LIMITED` | 429 `RATE_LIMITED` | 呼叫者的處理都是等一段時間再試；對方給的 `Retry-After` 照樣帶上 |

- 下面的 `error_code` 處理方式不同，保留：
  - `UPSTREAM_TIMEOUT` 與 `UPSTREAM_ERROR`：前端會自動重送逾時，不重送 `UPSTREAM_ERROR`。
  - `REQUEST_IN_PROGRESS` 與 `IDEMPOTENCY_KEY_REUSED`：前者稍後重試會成功，後者重試也不會成功。
  - `METHOD_NOT_ALLOWED`：HTTP 標準的 405。

### 外部服務錯誤的轉換

外部服務的錯誤回應一律用 `core/errors.py` 的 `upstream_error_code` 決定 `error_code`。各平台只判斷兩件事：是不是限流、是不是憑證被拒。判斷方式各平台不同，例如 GitHub 看 `x-ratelimit-remaining`，Google 看 `error.errors[].reason`。

依序判斷，符合一條就停止：

1. 限流：`RATE_LIMITED`。
2. 憑證被拒，而且是已存的憑證：`REAUTH_REQUIRED`。
3. 憑證被拒，而且是連結帳號時送出的憑證：`INVALID_CREDENTIALS`。
4. 對方回 400（我方送錯請求）：`INTERNAL_ERROR`。
5. 其他：`UPSTREAM_ERROR`。

連不上或逾時用 `request_error_code`：逾時是 `UPSTREAM_TIMEOUT`，其他是 `UPSTREAM_ERROR`。給使用者看的說明用 `upstream_detail`，只有憑證被拒的說明由各平台自己寫。

內部的判斷不改：抓資料時要不要重試（`NonRetryableError`、`UpstreamError`）、同步結果（`SyncOutcome`）、Google token 換新失敗時要不要刪 token，都照原本的規則。

### 對照表

取代 ADR 0011 的對照表；ADR 0011 的回應格式、分類原則與例外不變。

| 狀態碼 | error_code | 什麼時候 |
|---|---|---|
| 400 | `INVALID_REQUEST` | 格式正確但違反業務規則；Google OAuth 授權碼無效或已過期 |
| 400 | `INVALID_CREDENTIALS` | 連結或更新帳號時，外部平台拒絕驗證用的憑證，包括 Jira 網域不存在 |
| 401 | `UNAUTHENTICATED` | Clerk JWT 驗證失敗；webhook 簽章錯誤；定時同步的密鑰錯誤；伺服器沒設定 webhook 或定時同步的密鑰（ADR 0011「例外」） |
| 404 | `NOT_FOUND` | 本系統的資料不存在或不屬於目前的使用者；未知路由 |
| 405 | `METHOD_NOT_ALLOWED` | 路由存在但不支援這個方法 |
| 409 | `NOT_LINKED` | 需要的第三方帳號還沒連結 |
| 409 | `REAUTH_REQUIRED` | 拿已存的第三方憑證抓資料時被拒、權限不足、已存的 Jira 網域回 404，或已存的憑證無法解密 |
| 409 | `ALREADY_EXISTS` | 重複建立（使用者已註冊、平台已綁定） |
| 409 | `SUGGESTION_EXPIRED` | 排程建議的快照已過期 |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 同一個 Idempotency-Key 用在不同的請求；重試也不會成功 |
| 409 | `REQUEST_IN_PROGRESS` | 同一個請求還在處理中；稍後重試會成功 |
| 422 | `VALIDATION_ERROR` | request 不符合 schema；不回傳輸入值 |
| 429 | `RATE_LIMITED` | 本系統或外部服務限流；外部服務有給 `Retry-After` 時一併帶上 |
| 500 | `INTERNAL_ERROR` | 未預期的例外、伺服器設定錯誤，或我方送錯請求導致外部服務回 400 |
| 502 | `UPSTREAM_ERROR` | 外部服務回 5xx、回應無法解析或缺少必要內容（例如沒有主要行事曆）、無法判斷原因的 4xx，或連不上 |
| 503 | `SERVICE_UNAVAILABLE` | 本系統的依賴（資料庫、Redis）暫時不能用；同步時等不到寫入鎖 |
| 504 | `UPSTREAM_TIMEOUT` | 外部服務逾時（包括抓 Clerk JWKS） |

## 放棄的做法

- **另外建一個內部原因的列舉，再對應到對外的 error_code**：內部需要的分類（要不要重試、同步結果）已經有 `NonRetryableError`、`UpstreamError` 與 `SyncOutcome`，再加一層列舉只是多一份要同步的對照。
- **`UPSTREAM_TIMEOUT` 併進 `UPSTREAM_ERROR`**：前端會自動重送逾時，合併後要不是失去重送，就是連外部服務的 4xx 也重送。
- **外部服務限流維持 503**：前端和呼叫者的處理和本系統限流相同；監控要分辨是誰限流時看 log。

## 影響

- 前端不再判斷 `UPSTREAM_RATE_LIMITED`，限流只看 `RATE_LIMITED` 與沒有 `error_code` 的 429。
- 外部服務限流的狀態碼從 503 改成 429。
- 資料庫裡舊的同步結果（`linkedAccounts.last_sync_error_code`）可能還是 `UPSTREAM_RATE_LIMITED`：程式只用這個欄位判斷是不是 `REAUTH_REQUIRED`，所以不用轉換，下次同步就會覆蓋。
- 新增外部平台時，只寫限流與憑證被拒的判斷，`error_code` 交給 `upstream_error_code`；不為單一平台新增 `error_code`。
