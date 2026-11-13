# 系統架構

架構圖見 [architecture.drawio](architecture.drawio)。

## 組成

| 部分 | 技術 | 部署 | 職責 |
|---|---|---|---|
| 前端 | Nuxt 3、Vue 3、Nuxt UI | Vercel | 畫面；每個資料來源一個 composable 負責抓資料與錯誤處理 |
| 前端 server route | Nitro（`frontend/server/api/`） | Vercel | 代理 LeetCode GraphQL：瀏覽器直接呼叫會被 CORS 擋下 |
| 後端 | FastAPI | Docker → Google Cloud Run | 任務、外部平台同步、排程、帳號連結 |
| 資料庫 | MongoDB | — | 持久化資料 |
| 快取 | Redis（選用） | — | 限流計數、短期快取、排程建議的快照（30 分鐘）；未設定 `REDIS_URL` 時改用記憶體，多個 instance 之間不共用 |
| 身分驗證 | Clerk | — | 前端登入；後端以 JWKS 驗證每個請求的 JWT |

| 定時觸發 | GitHub Actions（`.github/workflows/scheduled-sync.yml`） | — | 每天台灣時間 12:00 呼叫後端 `POST /internal/scheduled-sync`，同步所有外部平台帳號（[ADR 0013](decisions/0013-scheduled-sync-trigger.md)） |

Hacker News 不經過後端，由瀏覽器直接呼叫公開 API。

## 後端分層

```
routers/     HTTP 進出：驗證登入、組回應；各層都丟 core/errors.py 的例外，不用 HTTPException
   │
   ├── crud/        讀寫 MongoDB
   ├── services/    商業邏輯（排程計算、AI 推估、Google Calendar、工作效率統計）
   └── platforms/   外部平台 adapter（GitHub、Jira、Moodle），由 PLATFORMS 註冊表統一產生路由
   │
core/        共用：資料庫連線（讀出的 datetime 一律帶 UTC 時區）、加密、限流、快取、錯誤型別與全域例外處理
schemas/     Pydantic 模型：API 的 request / response 格式
```

crud、services、platforms 丟 `core/errors.py` 的例外，由 `core/exception_handlers.py` 轉成狀態碼；資料庫錯誤和未預期的例外由全域 handler 回 503 / 500。

## MongoDB collections

| collection | 內容 | 主鍵 |
|---|---|---|
| `users` | 使用者（由 Clerk webhook 與 `POST /users/` 建立） | Clerk user id |
| `linkedAccounts` | 外部平台帳號，憑證加密儲存；另存最近一次的同步結果（成功時間、失敗的 `error_code`）、同步用的寫入鎖與開始時間，以及每次連結產生的 `link_id` | `{clerk_id}_{platform}` |
| `manual_tasks` | 手動建立的任務；主任務（`is_parent`，階段順序存在 `subtask_ids`，見 ADR 0004）和子任務（`parent_id`）也存在這裡 | uuid |
| `github_issues`、`jira_issues`、`moodle_assignments` | 外部平台項目的同步快取，加上使用者設定的排程欄位 | `(user_id, id)` |
| `googleCalendarTokens` | Google OAuth token | Clerk user id |

## 主要資料流

**外部平台同步**：GitHub Actions 每天台灣時間 12:00 呼叫一次定時同步，依序處理所有帳號；使用者按「立即同步」、連結帳號或更新憑證時也會同步。打開頁面只讀資料庫，不向平台抓資料。同步共用 `platforms/account_sync.py`：抓到的資料 upsert 進對應的 collection，平台上已不存在的項目會刪除，並在 `linkedAccounts` 記下同步結果。抓取失敗時不動項目，只記下失敗的原因；立即同步失敗時退回資料庫的舊資料，並以 `X-Data-Stale` / `X-Auth-Error` header 告訴前端。同一個帳號同時有兩次同步時，以比較晚開始抓資料的那次為準：寫入前先拿 `linkedAccounts` 上的鎖，再比對開始時間。同步只 `$set` 平台回傳的欄位，所以使用者設定的排程欄位（priority、duration、done、completed_at 等）不會被覆蓋。

**可排程項目**：`crud/schedulable_items.py` 把手動任務和三個平台的項目統一成同一種格式，id 加上來源前綴（例如 `github:42`）。排程精靈、標記完成和工作效率統計都用這份清單。

**排程建議與確認**：`POST /schedule/suggest` 以 Google Calendar 空檔扣掉不工作時段後計算建議，並把結果存成快照（存在快取，不存 MongoDB）；`POST /schedule/confirm` 只寫入快照內容，不重新計算，同一份快照只能確認一次。

**AI**：Gemini 用於推估任務的優先度與所需時間（建立任務時未填才呼叫，有限流），以及 GitHub PR 摘要機器人（`POST /webhook`，結果貼到 Discord，供本專案自己的開發流程使用）。
