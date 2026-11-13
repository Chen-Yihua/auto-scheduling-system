# 後端 API 一覽

「登入」欄為 ✅ 的 endpoint 需要帶 Clerk JWT（`Authorization: Bearer <token>`），沒帶或驗證失敗回 401 `UNAUTHENTICATED`（向 Clerk 取得驗證用的公鑰失敗時是 502 `UPSTREAM_ERROR` 或 504 `UPSTREAM_TIMEOUT`）。request / response 的欄位定義見 `backend/schemas/` 或後端的 `/docs`。

## 錯誤回應

本後端產生的錯誤回應都是 `{"detail": <給人看的訊息>, "error_code": <原因>}`：狀態碼表示類別，`error_code` 表示具體原因，前端依 `error_code` 判斷畫面，`detail` 只用來顯示。422 的 `detail` 是驗證錯誤的清單，不帶輸入值。狀態碼一律照 [ADR 0011](decisions/0011-api-error-status-codes.md) 的對照表，由 `error_code` 決定；對照表沒有的 `error_code` 一律回 500 `INTERNAL_ERROR`。外部服務限流（503 `UPSTREAM_RATE_LIMITED`）時，對方回應帶秒數的 `Retry-After` 會一併帶上（跨來源也讀得到）。Cloud Run 自己回的回應與網路錯誤沒有 `error_code`。

## 使用者

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| GET | `/users/me` | ✅ | — | `UserOut` | 目前登入的使用者 |
| POST | `/users/` | ✅ | `UserCreate` | `UserOut`（201） | 註冊目前登入的使用者，已註冊回 409 `ALREADY_EXISTS` |
| PUT | `/users/me` | ✅ | `UserUpdate` | — | 更新使用者資料；沒有可更新的欄位回 400 |
| DELETE | `/users/me` | ✅ | — | — | 刪除使用者 |
| POST | `/users/webhook/clerk` | Svix 簽章 | Clerk 事件 | — | Clerk 使用者事件同步；簽章錯誤或伺服器沒設定密鑰回 401 |

## 外部平台帳號

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| GET | `/users/me/linked-accounts/` | ✅ | — | `list[LinkedAccountOut]` | 憑證一律遮蔽；`last_synced_at` 是最近一次成功同步的時間，沒有同步紀錄時是 `null` |
| POST | `/users/me/linked-accounts/` | ✅ | `LinkedAccountCreate` | `LinkedAccountOut`（201） | 儲存前實際驗證憑證，平台拒絕憑證回 400 `INVALID_CREDENTIALS`；成功後馬上同步該平台一次，同步失敗仍回 201；限流 10/分 |
| PATCH | `/users/me/linked-accounts/{platform}` | ✅ | `LinkedAccountUpdate` | — | 改到憑證時重新驗證，驗證成功後馬上同步該平台一次，同步失敗仍回成功；沒有可更新的欄位回 400；限流 10/分 |
| DELETE | `/users/me/linked-accounts/{platform}` | ✅ | — | — | |

## 外部平台項目

外部平台每天台灣時間 12:00 定時同步一次（見下方「內部」）。

- `GET` 只讀資料庫，不向平台抓資料。header `X-Synced-At` 是最近一次成功同步的時間（沒有同步紀錄時不帶）；最近一次同步因憑證失效失敗時帶 `X-Auth-Error: true`。尚未連結回 409 `NOT_LINKED`。
- `POST`（立即同步）一律即時向平台抓資料、寫進資料庫，回傳最新的項目。失敗時有舊資料就退回舊資料並帶 `X-Data-Stale: true`（憑證失效另外帶 `X-Auth-Error: true`）；沒有舊資料時照失敗的原因回錯誤，例如尚未連結 409 `NOT_LINKED`、憑證失效或無法解密 409 `REAUTH_REQUIRED`、平台故障 502、限流 503、逾時 504。等不到寫入鎖（同一個帳號的另一次同步正在寫入）時同樣退回舊資料，沒有舊資料回 503 `SERVICE_UNAVAILABLE`。被比較晚開始的同步取代時，回資料庫目前的項目。
- 這三個 header 跨來源也讀得到。

| 方法 | 路徑 | 登入 | Response | 限流 |
|---|---|---|---|---|
| GET | `/github/issues` | ✅ | `list[GitHubIssue]` | — |
| GET | `/jira/issues` | ✅ | `list[JiraIssue]` | — |
| GET | `/moodle/assignments` | ✅ | `list[MoodleAssignment]` | — |
| POST | `/github/sync` | ✅ | `list[GitHubIssue]` | 10/分 |
| POST | `/jira/sync` | ✅ | `list[JiraIssue]` | 30/分 |
| POST | `/moodle/sync` | ✅ | `list[MoodleAssignment]` | 5/分 |

## 手動任務

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| POST | `/manual-tasks/` | ✅ | `ManualTaskInput`，header `Idempotency-Key`（選填） | `ManualTaskWithSubtasksOut`（201） | priority / duration 未填時由 AI 推估；帶 `subtasks`（1～10 個）時建立主任務和依序編號的子任務，整批只算一次請求；限流 20/分 |
| POST | `/manual-tasks/{task_id}/subtasks` | ✅ | `SubtaskCreate`，header `Idempotency-Key`（選填） | `ManualTaskWithSubtasksOut`（201） | 在 `position`（預設最後）插入子任務；對一般任務新增時它會變成主任務；相同 `Idempotency-Key` 重送回傳第一次的結果；限流 20/分 |
| GET | `/manual-tasks/me` | ✅ | — | `list[ManualTaskOut]` | 沒有任務回空陣列；主任務和子任務各一筆，主任務的狀態與進度依子任務計算 |
| GET | `/manual-tasks/{task_id}` | ✅ | — | `ManualTaskOut` | 只能查自己的 |
| PUT | `/manual-tasks/{task_id}` | ✅ | `ManualTaskUpdate` | `ManualTaskOut` | 部分更新，沒帶的欄位保留原值；主任務只能改標題、描述、截止日；違反階段之間的優先序或截止日限制回 400 |
| DELETE | `/manual-tasks/{task_id}` | ✅ | — | — | 主任務連同子任務一起刪；主任務和子任務會先刪掉子任務在 Google Calendar 上還沒開始的事件（需要時 Google 授權失效回 409 `REAUTH_REQUIRED`、Google 暫時失敗回 502／503／504，任務都保留）；主任務只剩一個子任務時不能刪那個子任務（400） |

## 排程

`task_id` 一律是帶來源前綴的組合 id（例如 `github:42`）。

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| GET | `/schedule/tasks` | ✅ | — | `list[SchedulableTaskOut]` | 手動任務和外部平台項目的統一清單 |
| PUT | `/schedule/reorder` | ✅ | `ScheduleReorderInput` | `list[SchedulableTaskOut]` | 拖拉排序的結果；任何一項不合法時整批回 400、什麼都不寫入：id 不存在或不屬於自己、組合 id 格式錯誤或來源前綴不認得、主任務、讓後面階段的優先序高於前面階段 |
| PATCH | `/schedule/tasks/fields` | ✅ | `ScheduleTaskFieldsUpdate` | — | 截止日期、所需時長；子任務違反階段之間的截止日限制回 400；任務不存在或不屬於自己（包括外部來源）回 404；組合 id 格式錯誤或來源前綴不認得回 400；沒帶任何欄位時同樣檢查 id，合法才回 200、不寫入 |
| PATCH | `/schedule/tasks/done` | ✅ | `ScheduleTaskDoneUpdate` | — | 標記完成或取消完成；主任務回 400；任務不存在或不屬於自己（包括外部來源）回 404；組合 id 格式錯誤或來源前綴不認得回 400 |
| POST | `/schedule/suggest` | ✅ | `SchedulePreferences` | `ScheduleSuggestion` | 產生建議並存成快照，不寫入行事曆 |
| POST | `/schedule/confirm` | ✅ | — | `ScheduleConfirmResult` | 把快照寫入 Google Calendar；快照過期回 409 `SUGGESTION_EXPIRED`；`failed` 每一筆帶 `error_code`（寫入 Google 失敗的原因，寫入前檢查不通過時是 `null`） |

## 工作效率統計

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| GET | `/analytics/productivity` | ✅ | query `timezone`（IANA 時區，預設 `UTC`） | `ProductivitySummary` | 彙總可排程項目的完成狀況與週趨勢；時區不合法回 400 |

## Google Calendar

| 方法 | 路徑 | 登入 | Request | 說明 |
|---|---|---|---|---|
| POST | `/oauth/callback` | ✅ | `OAuthCallbackPayload` | 用授權碼換 token；授權碼無效回 400 `INVALID_AUTHORIZATION_CODE` |
| GET | `/oauth/status` | ✅ | — | 是否已連接 |
| GET | `/oauth/calendars` | ✅ | — | 使用者的行事曆清單；尚未連接回 409 `NOT_LINKED`，授權失效回 409 `REAUTH_REQUIRED` |

## 其他

| 方法 | 路徑 | 登入 | 說明 |
|---|---|---|---|
| POST | `/webhook` | GitHub 簽章 | PR 摘要機器人；簽章錯誤或伺服器沒設定密鑰回 401；限流 30/分 |

## 內部

| 方法 | 路徑 | 登入 | Response | 說明 |
|---|---|---|---|---|
| POST | `/internal/scheduled-sync` | 共用密鑰（`Authorization: Bearer <SCHEDULED_SYNC_SECRET>`） | `{"succeeded": n, "failed": n, "skipped": n}` | 由 GitHub Actions 每天呼叫（[ADR 0013](decisions/0013-scheduled-sync-trigger.md)），依序同步所有已連結的平台帳號；回應只帶筆數。密鑰錯誤、格式不對或伺服器沒設定密鑰回 401 `INVALID_SCHEDULER_TOKEN`；限流 5/時 |
| GET | `/health` | — | 健康檢查 |

## 前端 server route

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/api/leetcode` | 代理 LeetCode 每日一題，不需登入 |
