# 後端 API 一覽

「登入」欄為 ✅ 的 endpoint 需要帶 Clerk JWT（`Authorization: Bearer <token>`），沒帶會被擋下（403）。request / response 的欄位定義見 `backend/schemas/` 或後端的 `/docs`。

## 使用者

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| GET | `/users/me` | ✅ | — | `UserOut` | 目前登入的使用者 |
| POST | `/users/` | ✅ | `UserCreate` | `UserOut`（201） | 註冊目前登入的使用者，已註冊回 409 |
| PUT | `/users/me` | ✅ | `UserUpdate` | — | 更新使用者資料 |
| DELETE | `/users/me` | ✅ | — | — | 刪除使用者 |
| POST | `/users/webhook/clerk` | Svix 簽章 | Clerk 事件 | — | Clerk 使用者事件同步 |

## 外部平台帳號

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| GET | `/users/me/linked-accounts/` | ✅ | — | `list[LinkedAccountOut]` | 憑證一律遮蔽 |
| POST | `/users/me/linked-accounts/` | ✅ | `LinkedAccountCreate` | `LinkedAccountOut`（201） | 儲存前實際驗證憑證；限流 10/分 |
| PATCH | `/users/me/linked-accounts/{platform}` | ✅ | `LinkedAccountUpdate` | — | 改到憑證時重新驗證；限流 10/分 |
| DELETE | `/users/me/linked-accounts/{platform}` | ✅ | — | — | |

## 外部平台項目

每次呼叫都即時向平台同步；失敗時退回上次的資料，回應 header 帶 `X-Data-Stale`、`X-Auth-Error`、`X-Synced-At`。

| 方法 | 路徑 | 登入 | Response | 限流 |
|---|---|---|---|---|
| GET | `/github/issues` | ✅ | `list[GitHubIssue]` | 10/分 |
| GET | `/jira/issues` | ✅ | `list[JiraIssue]` | 30/分 |
| GET | `/moodle/assignments` | ✅ | `list[MoodleAssignment]` | 5/分（另有結果快取） |

## 手動任務

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| POST | `/manual-tasks/` | ✅ | `ManualTaskInput`，header `Idempotency-Key`（選填） | `ManualTaskOut`（201） | priority / duration 未填時由 AI 推估；限流 20/分 |
| GET | `/manual-tasks/me` | ✅ | — | `list[ManualTaskOut]` | 沒有任務回空陣列 |
| GET | `/manual-tasks/{task_id}` | ✅ | — | `ManualTaskOut` | 只能查自己的 |
| PUT | `/manual-tasks/{task_id}` | ✅ | `ManualTaskUpdate` | `ManualTaskOut` | 部分更新，沒帶的欄位保留原值 |
| DELETE | `/manual-tasks/{task_id}` | ✅ | — | — | |

## 排程

`task_id` 一律是帶來源前綴的組合 id（例如 `github:42`）。

| 方法 | 路徑 | 登入 | Request | Response | 說明 |
|---|---|---|---|---|---|
| GET | `/schedule/tasks` | ✅ | — | `list[SchedulableTaskOut]` | 手動任務和外部平台項目的統一清單 |
| PUT | `/schedule/reorder` | ✅ | `ScheduleReorderInput` | `list[SchedulableTaskOut]` | 拖拉排序的結果 |
| PATCH | `/schedule/tasks/fields` | ✅ | `ScheduleTaskFieldsUpdate` | — | 截止日期、所需時長 |
| PATCH | `/schedule/tasks/done` | ✅ | `ScheduleTaskDoneUpdate` | — | 標記完成或取消完成 |
| POST | `/schedule/suggest` | ✅ | `SchedulePreferences` | `ScheduleSuggestion` | 產生建議並存成快照，不寫入行事曆 |
| POST | `/schedule/confirm` | ✅ | — | `ScheduleConfirmResult` | 把快照寫入 Google Calendar；快照過期回 409 |

## Google Calendar

| 方法 | 路徑 | 登入 | Request | 說明 |
|---|---|---|---|---|
| POST | `/oauth/callback` | ✅ | `OAuthCallbackPayload` | 用授權碼換 token |
| GET | `/oauth/status` | ✅ | — | 是否已連接 |
| GET | `/oauth/calendars` | ✅ | — | 使用者的行事曆清單 |

## 其他

| 方法 | 路徑 | 登入 | 說明 |
|---|---|---|---|
| POST | `/webhook` | GitHub 簽章 | PR 摘要機器人；限流 30/分 |
| GET | `/health` | — | 健康檢查 |

## 前端 server route

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/api/leetcode` | 代理 LeetCode 每日一題，不需登入 |
