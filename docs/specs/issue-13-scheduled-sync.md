# 外部平台定時同步

- 狀態：已核准
- 等級：高風險（批次解密所有使用者的憑證；改變和外部平台同步的一致性，包括定時同步與手動同步同時發生；新增定時觸發的部署方式，屬於重大架構決策，見 [ADR 0013](../decisions/0013-scheduled-sync-trigger.md)）
- issue：[#13](https://github.com/Chen-Yihua/auto-scheduling-system/issues/13)
- PR：[#97](https://github.com/Chen-Yihua/auto-scheduling-system/pull/97)

## 簡短說明

外部平台（GitHub、Jira、Moodle）改成每天台灣時間 12:00 自動同步一次。打開頁面時只讀資料庫，不再即時同步。想看最新資料時，使用者按「立即同步」按鈕。

## 背景

- 現在只要打開儀表板或平台頁面，前端就會呼叫 `GET /github/issues`、`GET /jira/issues`、`GET /moodle/assignments`。後端每次都會即時向平台抓資料，並寫進資料庫（[router.py](../../backend/platforms/router.py) 的 `get_platform_items`、[sync.py](../../backend/platforms/sync.py) 的 `sync_platform_items`）。
- 儀表板一打開，三個平台會同時同步（[Dashboard.vue:24-29](../../frontend/components/dashboard/Dashboard.vue#L24-L29)）。
- 工作效率統計只讀資料庫（[schedulable_items.py:111](../../backend/crud/schedulable_items.py#L111)）。很久沒打開平台頁面時，統計用的是舊資料，使用者也看不到資料是什麼時候同步的：統計頁沒有顯示同步時間。平台頁面只在「退回舊資料」時，才顯示上次同步時間（[StaleDataBanner.vue](../../frontend/components/platforms/StaleDataBanner.vue)）。
- Moodle 沒有 API，每次同步都要用 headless Chrome 登入 SSO 再爬網頁，大約十幾秒（[moodle.py](../../backend/platforms/moodle.py)）。結果快取 15 分鐘，快取存在記憶體裡。沒設定 Redis 時，instance 縮到 0 再啟動，快取就清空了。
- 後端部署在 Cloud Run，沒有請求時會縮到 0，所以程式內建的定時器不可靠。開發者也在控制費用：每次打開頁面都即時同步，會讓 Cloud Run 的用量跟著增加。
- 現有的同步規則：
  - 抓取失敗最多試 2 次。`NonRetryableError`（憑證失效、帶限流訊號的 403 等）不重試；429 與 5xx 是 `UpstreamError`，會重試（[http_errors.py:34-47](../../backend/platforms/http_errors.py#L34-L47)）。
  - 重試後仍失敗，就退回資料庫裡上次成功的資料。
  - 寫入時只 `$set` 平台回傳的欄位，所以使用者設定的排程欄位不會被覆蓋。
  - 平台上已不存在的項目會被刪除。
  - 同一個使用者同時同步兩次時，現在沒有規定以哪一次為準：較早開始的同步可能較晚寫入，蓋掉較新的資料。
- 開發與正式環境共用同一個資料庫（#78）。另一個環境用它自己的金鑰加密的憑證，在這個環境會解密失敗（[linked_account.py](../../backend/crud/linked_account.py) 的 `_to_public`）。
- 目前只有開發者一位使用者。
- issue 提到的 #15（部署搬到 Cloudflare）在 repo 裡不存在。

## 需求

**定時同步**

1. 每天台灣時間 12:00（Asia/Taipei）自動同步一次。所有使用者用同一個時間。
2. 定時同步由 GitHub Actions 的排程觸發，呼叫後端的新 endpoint（[ADR 0013](../decisions/0013-scheduled-sync-trigger.md)）。
3. 新 endpoint 用共用密鑰驗證，不用 Clerk 登入。
4. 後端沒設定密鑰，或密鑰是空字串時，新 endpoint 一律拒絕。
4a. 請求的格式不是 `Authorization: Bearer <值>`，或 `Bearer` 後面是空的，新 endpoint 也拒絕。
5. 定時同步處理所有已連結平台帳號的使用者，不提供關閉的設定。
6. 每個使用者的每個平台分開處理，一項失敗不影響其他項。
7. 重試沿用現有規則（見「背景」）。
8. 重試後仍然失敗時，保留資料庫裡的舊資料，等下一次排程。
9. 失敗時在 log 記下使用者 id、平台和錯誤代碼（`error_code`）。
10. log 不能出現憑證，不論明文或密文。
11. 憑證失效時，不刪除帳號連結。
12. 定時同步依序處理所有帳號，同一次定時同步裡同一時間只處理一個帳號。這條只限制定時同步內部：定時同步和按鈕同時爬 Moodle 時，可以同時開兩個瀏覽器。
13. 新 endpoint 的回應只帶各種結果的筆數，不帶使用者 id、憑證或錯誤訊息：GitHub Actions 的 log 是公開的。
13a. 回應的筆數分三種：「成功」是抓到資料，而且項目與同步結果都寫入了；「略過」是被較新的同步取代、憑證解不開、憑證資料不完整，或寫入同步結果前帳號已經不是同一次連結；「失敗」是其他情況，包括等不到寫入鎖、寫入途中鎖被別人拿走。

**打開頁面**

14. 打開儀表板或平台頁面時，不向平台抓資料，一律讀資料庫。
15. 平台頁面一律顯示上次同步時間。
16. 儀表板顯示三個平台各自的上次同步時間。
17. 工作效率統計頁顯示已連結平台各自的上次同步時間。
18. 還沒有同步紀錄時，顯示「尚未同步」。
18a. 前端和後端在不同網域時，瀏覽器也要讀得到同步時間、憑證失效與退回舊資料這三個 header。

**立即同步**

19. GitHub、Jira、Moodle 三個平台頁面各有一個「立即同步」按鈕，只同步那一頁的平台。
20. 儀表板有一個「立即同步」按鈕，一次同步三個平台。
21. 工作效率統計頁不放按鈕。
22. 按鈕一律即時抓資料，不經過快取。
23. 按鈕的次數限制沿用各平台現有的限制：GitHub 每分鐘 10 次、Jira 30 次、Moodle 5 次。
24. 按鈕同步失敗時，處理方式和現在打開頁面時同步失敗一樣：有舊資料就顯示舊資料與提示，沒有就跳錯誤訊息。
24a. 按鈕的這次同步被比較晚開始的同步取代時，回傳資料庫目前的項目與同步時間。
24b. 按鈕的這次同步等不到寫入鎖時，當成暫時性失敗：有舊資料就回舊資料與提示，沒有就回 503（`SERVICE_UNAVAILABLE`）。
24c. 按鈕的這次同步解不開憑證時，照現在的做法回「需要重新連結」的錯誤（`REAUTH_REQUIRED`）。
24d. 按鈕的這次同步遇到憑證資料不完整時，照現在的做法回「尚未連結」（`NOT_LINKED`）。
24e. 按鈕的這次同步在寫入途中發現鎖已經不是自己的（過期或被別人拿走）時，照第 24a 條回傳資料庫目前的項目與同步時間。
24f. 按鈕的這次同步途中帳號連結被刪除時，回 `NOT_LINKED`；換成另一次連結時，回傳資料庫目前的項目與同步時間。

**同步結果**

25. 系統記下每個帳號最近一次同步的結果。來源包括定時同步、按鈕，以及連結時的同步。
26. 最近一次同步因為憑證失效（`REAUTH_REQUIRED`）而失敗時，打開頁面會顯示現有的「授權已失效，請重新連結帳號」提示。
27. 最近一次同步是暫時性的失敗（平台故障、限流、逾時）時，不顯示提示。
27a. 任何來源（定時、按鈕、連結時）解不開憑證時，都不記成同步結果，也不算一次同步：開發與正式環境共用資料庫，可能是另一個環境的金鑰加密的，帳號清單已經會在解不開的環境顯示「需要重新連結」（`needs_reauth`）。

**連結帳號**

28. 連結帳號成功後，後端馬上同步該平台一次。
29. 更新憑證而且重新驗證成功後，後端馬上同步該平台一次。
30. 第 28、29 條的同步失敗時，連結或更新仍然算成功。

**同時同步**

31. 同一個帳號同時有兩次同步時，以比較晚開始抓資料的那一次為準，不論哪一次先結束。
32. 比較早開始的同步，不能蓋掉或刪除比較晚開始的同步寫入的項目。
33. 比較早開始的同步，不能蓋掉比較晚開始的同步記下的同步結果。
34. 寫入前，帳號連結已經不存在（取消連結、使用者被刪除），或已經換成另一次連結（重新連結、更新憑證），這次同步就整次放棄：不寫項目，也不寫同步結果。

## 不做

- 不清除 Artifact Registry 的舊映像檔（#96）。
- 不搬部署平台（issue 提到的 #15 不存在）。
- 不讓使用者自訂同步時間或關閉定時同步。
- 不依使用者的時區調整同步時間。
- 定時同步失敗時不另外通知使用者（例如 Email、Discord），只靠打開頁面時的提示（需求 26）。
- 不轉換既有資料：上線前同步過的帳號沒有同步紀錄，頁面會顯示「尚未同步」，直到下一次定時同步或按下按鈕。
- 不限制全域同時開幾個瀏覽器爬 Moodle（需求 12）。

## 假設

1. 目前只有一位使用者（開發者確認），所以定時同步在一次請求裡處理完所有帳號。超過 Cloud Run 單次請求的時間上限時，還沒處理到的帳號等下一次排程。
2. GitHub 排程延遲 5 到 30 分鐘可以接受（ADR 0013「影響」）。

## 驗收條件

**定時同步**

| # | 條件 |
|---|---|
| AC1 | 在 `.github/workflows/scheduled-sync.yml` 裡，排程要設定為 cron `0 4 * * *`（UTC 04:00，等於台灣時間 12:00） |
| AC2 | 在 `.github/workflows/scheduled-sync.yml` 裡，要可以手動觸發（`workflow_dispatch`） |
| AC3 | 在 workflow 執行時，要用 `Authorization: Bearer` 帶 `SCHEDULED_SYNC_SECRET` 呼叫 `${BACKEND_URL}/internal/scheduled-sync` |
| AC4 | 在後端回非 2xx 時，workflow 的呼叫步驟要失敗 |
| AC5 | 在帶正確密鑰呼叫 `POST /internal/scheduled-sync` 時，系統要同步每個使用者的每個已連結平台，並更新資料庫 |
| AC6 | 在沒帶 `Authorization`、密鑰錯誤、格式不是 `Bearer <值>`，或 `Bearer` 後面是空的時，`POST /internal/scheduled-sync` 要回 401，而且不同步任何帳號 |
| AC7 | 在後端沒設定 `SCHEDULED_SYNC_SECRET` 或值是空字串時，`POST /internal/scheduled-sync` 不論帶什麼都要回 401 |
| AC8 | 在定時同步中某個帳號失敗時（憑證失效、平台故障、未預期的例外），其他帳號仍要照常同步 |
| AC9 | 在定時同步中某個帳號重試後仍失敗時，資料庫裡這個帳號的項目要維持原樣 |
| AC10 | 在定時同步中某個帳號失敗時，log 要記下使用者 id、平台與 `error_code` |
| AC11 | 在定時同步的整個過程中，log 不能出現任何帳號的明文或密文憑證 |
| AC12 | 在定時同步遇到憑證失效時，帳號連結要保留在資料庫 |
| AC13 | 在一次定時同步處理多個帳號時，同一時間只能有一個帳號在抓資料 |
| AC14 | 在定時同步完成時，回應只能有 `succeeded`、`failed`、`skipped` 三個筆數，不能有使用者 id、憑證或錯誤訊息 |
| AC15 | 在定時同步解密某個帳號的憑證失敗時，要把這個帳號算進 `skipped`、不改它的同步結果，並繼續處理其他帳號 |

**讀取（打開頁面）**

| # | 條件 |
|---|---|
| AC16 | 在呼叫 `GET /github/issues`、`GET /jira/issues`、`GET /moodle/assignments` 時，系統要回資料庫裡的項目，不向平台抓資料 |
| AC17 | 在帳號有成功同步過時，`GET` 的回應要帶 `X-Synced-At`，值是最近一次成功同步的時間 |
| AC18 | 在帳號從來沒有成功同步過時，`GET` 的回應不能帶 `X-Synced-At` |
| AC19 | 在最近一次同步因 `REAUTH_REQUIRED` 失敗時，`GET` 的回應要帶 `X-Auth-Error: true` |
| AC20 | 在最近一次同步是暫時性失敗或成功時，`GET` 的回應不能帶 `X-Auth-Error` |
| AC21 | 在沒有連結該平台時，`GET` 要照現在的行為回 `NOT_LINKED` |
| AC22 | 在 `GET /users/me/linked-accounts/` 的回應裡，每個帳號要帶 `last_synced_at`（沒有同步紀錄時是 `null`） |
| AC23 | 在 `GET /users/me/linked-accounts/` 的回應裡，不能出現同步用的鎖與開始時間等內部欄位 |

**立即同步（後端）**

| # | 條件 |
|---|---|
| AC24 | 在呼叫 `POST /github/sync`、`POST /jira/sync`、`POST /moodle/sync` 時，系統要即時向平台抓資料、寫進資料庫，並回傳最新的項目 |
| AC25 | 在 Moodle 剛同步過（15 分鐘內）又呼叫 `POST /moodle/sync` 時，系統仍要即時抓資料 |
| AC26 | 在同一個使用者一分鐘內超過次數限制（GitHub 10 次、Jira 30 次、Moodle 5 次）時，`POST` 要回 429 |
| AC27 | 在 `POST` 抓取失敗而且有舊資料時，要回舊資料，並帶 `X-Data-Stale: true` |
| AC28 | 在 `POST` 抓取失敗而且沒有舊資料時，要回和現在 `GET` 相同的狀態碼與 `error_code` |
| AC29 | 在未登入時呼叫 `POST`，要回和其他需要登入的 endpoint 相同的 401 |

**畫面**

| # | 條件 |
|---|---|
| AC30 | 在打開儀表板或平台頁面時，前端不能呼叫 `POST /{platform}/sync` |
| AC31 | 在平台頁面按「立即同步」時，前端只呼叫那一頁平台的 `POST`，完成後更新清單與上次同步時間 |
| AC32 | 在平台頁面上，要一律顯示上次同步時間 |
| AC33 | 在沒有同步紀錄時，平台頁面要顯示「尚未同步」 |
| AC34 | 在儀表板按「立即同步」時，前端要呼叫三個平台各自的 `POST` |
| AC35 | 在儀表板的立即同步中，其中一個平台失敗時，其他平台仍要更新，並只對失敗的平台跳錯誤訊息 |
| AC36 | 在儀表板上，要顯示三個平台各自的上次同步時間 |
| AC37 | 在工作效率統計頁上，要顯示已連結平台各自的上次同步時間，沒有同步紀錄的顯示「尚未同步」 |
| AC38 | 在工作效率統計頁上，不能有立即同步按鈕 |
| AC39 | 在 `GET` 回 `X-Auth-Error: true` 時，平台清單要顯示現有的「授權已失效」提示 |

**連結帳號**

| # | 條件 |
|---|---|
| AC40 | 在連結帳號成功時，系統要同步該平台一次，資料庫要有該平台的項目 |
| AC41 | 在連結帳號後的同步失敗時，`POST /users/me/linked-accounts/` 仍要回 201，帳號要存進資料庫 |
| AC42 | 在更新憑證而且重新驗證成功時，系統要同步該平台一次 |
| AC43 | 在更新憑證後的同步成功時，之前記下的「憑證失效」結果要清掉 |
| AC44 | 在更新憑證後的同步失敗時，`PATCH` 仍要回成功 |
| AC45 | 在更新的欄位不需要重新驗證時，系統不能同步 |

**資料一致性**

| # | 條件 |
|---|---|
| AC46 | 在同一個帳號有兩次同步，而且比較早開始的那次比較晚寫入時，資料庫的項目要是比較晚開始那次的結果 |
| AC47 | 在同一個帳號有兩次同步，而且比較早開始的那次比較晚寫入時，同步結果與上次同步時間要是比較晚開始那次的 |
| AC48 | 在同一個帳號有兩次同步時，比較早開始的那次不能刪掉比較晚開始那次寫入的項目 |
| AC49 | 在同步更新既有項目時，使用者設定的排程欄位（priority、duration、done、completed_at 等）要保留 |
| AC50 | 在同步一個使用者時，其他使用者的項目與同步結果不能被改動 |
| AC51 | 在比較早開始的同步正在寫入時，比較晚開始的同步要等它寫完才開始寫入 |
| AC52 | 在比較早開始的同步寫入期間鎖已過期、被比較晚開始的同步拿走時，比較早開始的同步不能刪掉項目，也不能寫入同步結果 |
| AC53 | 在一次同步釋放鎖時，只能釋放自己拿到的鎖，不能釋放別人的鎖 |
| AC54 | 在同步寫入前帳號連結已經被刪除時，系統不能寫入任何項目，也不能寫入同步結果 |
| AC55 | 在同步寫入前帳號已經重新連結或更新過憑證時，這次同步不能寫入任何項目，也不能寫入同步結果 |

**跨網域與同步的特殊結果**

| # | 條件 |
|---|---|
| AC56 | 在帶 `Origin` 的請求呼叫平台 `GET` 與 `POST /{platform}/sync` 時，回應的 `Access-Control-Expose-Headers` 要包含 `X-Synced-At`、`X-Auth-Error`、`X-Data-Stale` |
| AC57 | 在 `POST /{platform}/sync` 的這次同步被比較晚開始的同步取代時，要回資料庫目前的項目與資料庫裡的 `X-Synced-At` |
| AC58 | 在 `POST /{platform}/sync` 等不到寫入鎖而且有舊資料時，要回舊資料，並帶 `X-Data-Stale: true` |
| AC59 | 在 `POST /{platform}/sync` 等不到寫入鎖而且沒有舊資料時，要回 503，`error_code` 是 `SERVICE_UNAVAILABLE` |
| AC60 | 在 `POST /{platform}/sync` 解不開憑證時，要回 `REAUTH_REQUIRED`，而且不改這個帳號的同步結果與 `sync_started_at` |
| AC61 | 在連結帳號後的同步解不開憑證時，不能改這個帳號的同步結果 |
| AC62 | 在 `POST /{platform}/sync` 遇到憑證資料不完整時，要回 409 `NOT_LINKED` |
| AC63 | 在 `POST /{platform}/sync` 寫入途中發現鎖已經不是自己的（過期或被別人拿走）時，要回資料庫目前的項目與資料庫裡的 `X-Synced-At` |
| AC64 | 在 `POST /{platform}/sync` 的同步途中（包括寫入項目期間）帳號連結被刪除時，要回 409 `NOT_LINKED` |
| AC65 | 在 `POST /{platform}/sync` 的同步途中帳號換成另一次連結時，要回資料庫目前的項目與資料庫裡的 `X-Synced-At` |
| AC66 | 在定時同步遇到被取代、帳號已變更、憑證資料不完整的帳號時，要算進 `skipped` |
| AC67 | 在定時同步遇到抓取失敗（包括退回舊資料）、等不到鎖、寫入途中鎖已經不是自己的帳號時，要算進 `failed` |
| AC70 | 在定時同步成功同步的帳號，要算進 `succeeded` |
| AC68 | 在比較晚開始的同步拿著鎖寫入、鎖過期後被比較早開始的同步拿到時，比較早開始的同步要回傳「被取代」，不能寫入項目或同步結果 |
| AC69 | 在同步寫入項目期間（實作計畫第 2 點第 6 步）更新憑證時，這次同步不能刪除項目，也不能寫入同步結果 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中 | 平台清單與儀表板的載入狀態沿用現有的 `loading`；同步中的按鈕停用由實作處理，不是需求能驗證的行為差異 |
| 空資料 | 平台回傳 0 筆時，沿用現有規則刪掉資料庫的舊項目；同步成功仍記下時間（AC17 涵蓋） |
| 未登入（畫面） | 頁面未登入時顯示 `LoginRequiredCard`，這次沒有改 |
| 權限（只動得到自己的資料） | `POST /{platform}/sync` 與 `GET` 都只用 Clerk token 裡的使用者 id，沒有接受使用者 id 參數；AC50 涵蓋批次同步不越界 |
| 輸入驗證、注入 | 新 endpoint 沒有 request body 或查詢參數 |

## 實作計畫

### 後端

1. **同步結果存在 `linkedAccounts`**：新增選填欄位，不新增 collection、不轉換既有資料。
   - `last_synced_at`：最近一次成功同步的時間。
   - `last_sync_error_code`：最近一次同步失敗的 `error_code`；成功時清成 `null`。
   - `sync_started_at`：最近一次寫入的那次同步是什麼時候開始抓資料的，用來判斷新舊。
   - `sync_lock_owner`、`sync_lock_until`：寫入鎖的擁有者（每次同步產生的隨機值）與到期時間。
   - `link_id`：每次連結產生的隨機值。建立連結時產生；更新憑證而且重新驗證成功時換一個新的。上線前建立的帳號沒有 `link_id`：第 1 步讀到沒有 `link_id` 時，之後的比對只對到同樣沒有 `link_id` 的帳號。
   - 刪除帳號時這些欄位一起刪除；重新連結時從頭開始。
2. **同步流程抽成一個共用函式**（放在 `platforms/`），定時同步、按鈕、連結帳號都呼叫它。回傳結果的種類：成功、失敗（有舊資料就退回）、等不到鎖、被取代、鎖被拿走、帳號已變更、憑證解不開、憑證資料不完整。步驟：
   1. 記下開始時間 `started_at`，讀帳號，記下它的 `link_id`。
   2. 解密憑證。解不開（`SecretDecryptError`）或憑證資料不完整時，直接回傳，不搶鎖、不寫任何欄位（需求 27a）。
   3. 抓資料，沿用 `sync_platform_items` 的重試規則。抓資料期間不上鎖。
   4. 搶鎖：在 `linkedAccounts` 用一次 `update_one` 條件更新。條件是 `_id` 相同、`link_id` 和第 1 步相同，而且 `sync_lock_until` 不存在或已過期。`$set` 設定 `sync_lock_owner = 這次的隨機值`、`sync_lock_until = 現在 + 5 分鐘`。
      - 沒更新到時，再讀一次帳號：帳號不存在或 `link_id` 不同，就回傳「帳號已變更」（需求 34）；只是鎖被別人拿著，就每 0.2 秒重試，最多 10 秒。
      - 等了 10 秒還拿不到鎖，就當成暫時性失敗，error code 用 `SERVICE_UNAVAILABLE`（需求 24b），不寫任何欄位。
   5. 拿到鎖之後，比對已存的 `sync_started_at`。比自己晚，就回傳「被取代」（需求 24a）。否則立刻寫入自己的 `sync_started_at`（`update_one`，條件是 `sync_lock_owner` 是自己、`link_id` 和第 1 步相同），再繼續。先寫開始時間，鎖過期時比較早開始的同步拿到鎖，才會被判定「被取代」（AC68）。這次寫入沒更新到時，照第 7 步的規則回傳「帳號已變更」或「鎖被拿走」。
   6. 抓取成功時，寫入項目（沿用 `$set` upsert）。
   7. 重讀帳號，依序確認：先確認帳號存在而且 `link_id` 和第 1 步相同，不符就回傳「帳號已變更」，不論鎖的狀態；再確認鎖還是自己的（`sync_lock_owner` 相同，而且還沒過期），不是就回傳「鎖被拿走」（過期或被別人拿走都算）。兩種都不刪項目、不寫同步結果（AC52、AC69）。
   8. 抓取成功時，刪除平台上已不存在的項目。
   9. 寫入同步結果：用 `update_one`，條件是 `sync_lock_owner` 還是自己，而且 `link_id` 和第 1 步相同。`$set` 寫入 `last_sync_error_code`，成功時另外寫 `last_synced_at`。抓取失敗時只寫同步結果，不動項目。條件不符（沒更新到）時，重讀帳號，照第 7 步的順序回傳「帳號已變更」或「鎖被拿走」。
   10. 在 `finally` 釋放鎖：`update_one` 的條件是 `sync_lock_owner` 還是自己，`$unset` 鎖的兩個欄位（AC53）。
3. **`GET /{platform 路徑}`**（`router.py`）：
   - 確認已連結後，讀 collection，不解密憑證，也不抓資料。
   - 依 `linkedAccounts` 的 `last_synced_at` 設定 `X-Synced-At`。
   - `last_sync_error_code == "REAUTH_REQUIRED"` 時設定 `X-Auth-Error: true`。
   - 拿掉 `GET` 的限流：只讀資料庫，和其他讀取的 endpoint 一樣不限流。
4. **新增 `POST /{platform}/sync`**：
   - 路徑是 `/github/sync`、`/jira/sync`、`/moodle/sync`，在 `PlatformAdapter` 加 `sync_route_path`。
   - 套用現有的 `rate_limit`。slowapi 用函式名稱區分 endpoint，所以函式要用不同的名稱（例如 `sync_{platform}_items`）。
   - 回應格式與錯誤對應沿用現在 `GET` 的 `get_platform_items`，包括 `X-Data-Stale`、`X-Auth-Error`、`X-Synced-At`。
   - 「被取代」時，回資料庫目前的項目與 `last_synced_at`（AC57）。
   - 等不到鎖時，有舊資料就回舊資料與 `X-Data-Stale: true`，沒有就回 503 `SERVICE_UNAVAILABLE`（AC58、AC59）。
   - 「鎖被拿走」時，照「被取代」回資料庫目前的項目與 `last_synced_at`（AC63）。
   - 「帳號已變更」時，帳號已經不存在就回 `NOT_LINKED`（AC64）；換成另一次連結了，就回資料庫目前的項目（AC65）。
   - 憑證解不開時，照現在回 `REAUTH_REQUIRED`（AC60）。
   - 憑證資料不完整時，照現在回 `NOT_LINKED`（AC62）。
   - 拿掉 Moodle 的 `cache_ttl_seconds`，以及 router 裡的快取讀寫：`GET` 不再抓資料，按鈕又要求一律即時抓，快取已經沒有用途。
5. **新增 `POST /internal/scheduled-sync`**（新 router 檔）：
   - 用 `hmac.compare_digest` 比對 `Authorization: Bearer <SCHEDULED_SYNC_SECRET>`。
   - 密鑰沒設定或是空字串（`if not SECRET`）、header 格式不對、`Bearer` 後面是空的、值不符時，都丟 `AppError` 回 401，`error_code` 為 `INVALID_SCHEDULER_TOKEN`。
   - 新的 `error_code` 要改三個地方：`backend/core/error_codes.py`、ADR 0011 的對照表、ADR 0011 的「例外」一節（和 webhook 一樣，沒設定密鑰也回 401）。
   - 依序列出所有 `linkedAccounts`，逐一呼叫第 2 點的函式。每一筆用 `try/except Exception` 包住，失敗只記 log（使用者 id、平台、`error_code`；未預期的例外記例外類別名稱），接著處理下一筆。
   - 回應格式：`{"succeeded": n, "failed": n, "skipped": n}`。分類照需求 13a：被取代、帳號已變更、憑證解不開、憑證資料不完整算 `skipped`；等不到鎖、鎖被拿走、失敗算 `failed`；成功算 `succeeded`。
   - 加限流 `5/hour`，降低密鑰外洩時的濫用風險。
   - 沒設定密鑰時，啟動時記 error log，比照 `GITHUB_WEBHOOK_SECRET` 的寫法。
6. **連結帳號**（`crud/linked_account.py`）：
   - `create_linked_account` 寫入時產生 `link_id`，寫入成功後呼叫第 2 點的函式。
   - `update_linked_account_by_clerk_id` 在 `needs_reverify` 為真時，和新憑證一起寫入新的 `link_id`；更新成功後呼叫第 2 點的函式。
   - 同步的例外一律接住、記 log，不影響回應。
7. **`LinkedAccountOut`** 加上 `last_synced_at: Optional[datetime]`。其他同步用的欄位（`sync_started_at`、`sync_lock_owner`、`sync_lock_until`、`link_id`、`last_sync_error_code`）不加進 `LinkedAccountOut`，不回給前端。
7a. **CORS**（`backend/main.py`）：`expose_headers` 加上 `X-Synced-At`、`X-Auth-Error`、`X-Data-Stale`（AC56）。這也修好現有的問題：正式環境前後端不同網域，前端一直讀不到 `X-Data-Stale`。

### 前端

8. **`usePlatformItems`**：
   - `fetchItems` 改成只讀 `GET`。
   - 新增 `syncNow()`，呼叫 `POST`，成功或退回舊資料時更新 `items`、`isStale`、`syncedAt`、`authError`；失敗時沿用現在的錯誤處理與 toast。
   - 新增 `syncing` 狀態。
9. **平台清單元件**（`GithubIssuesList`、`JiraIssuesList`、`MoodleAssignmentsList`）：
   - 一律顯示「上次同步：<相對時間>」，沒有紀錄時顯示「尚未同步」。
   - 加一個選填的同步按鈕：用 prop 傳入 `onSync`、`syncing`，有傳才顯示，所以平台頁面有按鈕、儀表板的卡片沒有。
   - `StaleDataBanner` 只在 `isStale` 或 `authError` 時顯示。
10. **平台頁面**（`github.vue`、`jira.vue`、`moodle.vue`）：把 `syncNow`、`syncing` 傳給清單元件。
11. **儀表板**：
    - 加一個「立即同步」按鈕，用 `Promise.allSettled` 同時呼叫三個 `syncNow()`。
    - 各卡片的上次同步時間由第 9 點顯示。
12. **工作效率統計頁**：用 `useLinkedAccount` 的帳號清單，顯示已連結平台各自的 `last_synced_at`。
13. **`frontend/types/`**：連結帳號的型別加上 `last_synced_at`。

### 部署與文件

14. 新增 `.github/workflows/scheduled-sync.yml`（ADR 0013）：
    - `schedule: cron: '0 4 * * *'`，加上 `workflow_dispatch`。
    - 執行 `curl -fsS -X POST "$BACKEND_URL/internal/scheduled-sync" -H "Authorization: Bearer $SCHEDULED_SYNC_SECRET" --max-time 900`。
    - 只輸出回應的筆數。
15. `backend/.env.example` 加上 `SCHEDULED_SYNC_SECRET`。這個變數不是 import 時就必填（沒設定時 endpoint 一律拒絕），所以不改 CI 的環境變數，也不改 `test_ci_env_requirements.py`。
16. `docs/api.md` 的更新：
    - 平台 `GET` 改成只讀資料庫、不限流。
    - 新增 `POST /{platform}/sync`，寫上限流。
    - 新增 `POST /internal/scheduled-sync`。
    - `LinkedAccountOut` 新增 `last_synced_at`。
17. `docs/architecture.md` 的更新：
    - 「外部平台同步」資料流改成定時同步加立即同步。
    - `linkedAccounts` 的內容加上同步結果。
    - 組成表加上 GitHub Actions 的定時觸發。
18. ADR 0013 存進 `docs/decisions/`，並更新 `docs/decisions/README.md` 的清單。
19. 合併前，請開發者設定三項（不讀取、不設定這些值）：
    - Cloud Run 環境變數 `SCHEDULED_SYNC_SECRET`，值用至少 32 bytes 的隨機值產生，例如 `openssl rand -hex 32`。
    - GitHub secret `SCHEDULED_SYNC_SECRET`，和 Cloud Run 的值相同。
    - GitHub variable `BACKEND_URL`。
    - 開發者也要確認 Cloud Run 的請求時間上限：預設 300 秒，要足夠處理所有帳號。

### 考慮過、沒選的做法

- **排程機制**：見 ADR 0013（程式內建定時器、Cloud Scheduler、Cloud Run Jobs、背景執行先回 202）。
- **打開頁面時，超過 24 小時才自動同步**：開發者選擇由自己看同步時間決定要不要按按鈕。
- **同時同步的處理**：
  - 用 `asyncio.Lock`：最多有 3 個 instance，記憶體裡的鎖不共用。
  - 用 Redis 鎖：Redis 是選用的，沒設定時退回記憶體。
  - 用 MongoDB transaction：測試用的 mongomock 不支援；也要求資料庫是 replica set。
  - 只比對開始時間、不上鎖：兩次寫入可能交錯。例如舊的那次刪除不存在的項目時，會刪掉新的那次剛寫入的項目。
- **同步結果另開一個 collection**：要新增 collection，刪除帳號時還要另外清掉；放在 `linkedAccounts` 的選填欄位，舊資料照常讀得出來。
- **`X-Synced-At` 改從項目的 `synced_at` 讀**：同步成功但平台回 0 筆時，沒有項目可讀，會誤顯示成「尚未同步」。
- **同步時間與授權狀態改從帳號清單讀、不用 header**：AC17–AC20 都要重寫；開放 CORS 的三個 header 改動最小，也修好現有的 `X-Data-Stale`（開發者選擇）。
- **鎖只拉長期限、不記擁有者**：沒有保證，鎖過期後仍會交錯（開發者選擇記擁有者）。

### 已接受的風險

觸發條件都需要寫入超過 5 分鐘，或連結變更剛好落在不到一秒的寫入期間；影響是一次同步的結果不完整，下一次同步就會修正。

- 單次同步寫入項目（實作計畫第 2 點第 6 步）超過 5 分鐘時，這次同步回傳「鎖被拿走」，不刪除項目、不寫入同步結果。已寫入的項目會留下，`last_synced_at` 停在更早之前的時間。
- 上一項的期間，如果比較早開始的同步拿到過期的鎖，它會被判定「被取代」，不寫任何項目或同步結果。兩次同步都沒有寫入同步結果，平台上已不存在的項目也都沒有刪除。
- 第 7 步確認之後、第 8 步刪除完成之前，鎖剛好過期被另一次同步拿走，或連結剛好變更（取消連結、刪除使用者、更新憑證）時，第 8 步的刪除擋不住。
- 一次同步的寫入超過 10 秒時，比較晚開始的同步等不到鎖會放棄（需求 24b），這時保留的是比較早開始那次的結果，需求 31 不成立。
- 從拿到鎖到第 7 步確認之前，刪除使用者、取消連結或更新憑證時，已寫入的項目會留下；第 7 步會擋住刪除與同步結果。
- 定時同步和按鈕同時爬 Moodle 時，會同時開兩個瀏覽器（需求 12）。
- 程式拿著鎖時當掉，這個帳號最多 5 分鐘內的同步都等不到鎖，會當成暫時性失敗。

## 測試對應

（測試檔名照 `backend/tests/README.md` 的放置規則，由實作決定；下表寫測試要驗證的內容。）

| AC | 測試 |
|---|---|
| AC1–AC3 | 實作審查時讀 workflow 檔確認設定。實際執行要合併後才能驗證：GitHub 只能對預設分支上的 workflow 觸發 `workflow_dispatch`。合併、開發者恢復 Cloud Run 收費後，手動觸發一次，確認 run 成功 |
| AC4 | 實作審查時確認呼叫步驟用 `curl -f`（或等效的設定）。合併後用 `curl -f` 帶錯的密鑰呼叫後端，確認回 401、指令以非 0 結束；不用改 GitHub 上的 secret |
| AC5 | 後端 integration：兩個使用者、三個平台的帳號，呼叫 endpoint 後各 collection 都有對應的項目 |
| AC6、AC7 | 後端 integration：沒帶 header、帶錯的值、格式不是 `Bearer <值>`、`Bearer` 後面是空的、伺服器沒設定密鑰、伺服器的密鑰是空字串（同時帶 `Bearer `），都回 401，而且 fetch 沒被呼叫 |
| AC8 | 後端 integration：第一個帳號丟 `NonRetryableError`、第二個丟 `RuntimeError`，第三個仍同步成功 |
| AC9 | 後端 integration：失敗帳號的既有項目維持原樣 |
| AC10、AC11 | 後端 integration：用 caplog 確認失敗記錄有 user id、平台、error_code；整個過程的 log 都不含測試用的明文憑證，也不含密文 |
| AC12 | 後端 integration：憑證失效後，`linkedAccounts` 仍有該帳號 |
| AC13 | 後端 unit：一次定時同步裡，fetch 記錄同時執行的數量，最大值為 1 |
| AC14 | 後端 integration：回應的 key 只有 succeeded、failed、skipped |
| AC15 | 後端 integration：密文換成用別的金鑰加密的值，該帳號算 skipped、同步結果欄位不變 |
| AC16 | 後端 integration：fetch 被呼叫就丟例外，`GET` 仍回資料庫的項目 |
| AC17、AC18 | 後端 integration：有、無 `last_synced_at` 時的 header |
| AC19、AC20 | 後端 integration：`last_sync_error_code` 為 `REAUTH_REQUIRED`、`UPSTREAM_ERROR`、`null` 時的 header |
| AC21 | 既有的 NOT_LINKED 測試改成驗證新的 `GET` |
| AC22、AC23 | 後端 integration：帳號清單的回應有 `last_synced_at`，沒有 `sync_started_at`、`sync_lock_until`、`last_sync_error_code` |
| AC24、AC27、AC28 | 既有的平台 `GET` 測試（成功、退回舊資料、各種錯誤）改到 `POST /{platform}/sync` |
| AC25 | 後端 integration：連續兩次 `POST /moodle/sync`，fetch 被呼叫兩次 |
| AC26 | 後端 integration：每個平台超過限制時回 429 |
| AC29 | 後端 integration：不帶 token 回 401 |
| AC30 | 前端 Dashboard 與平台頁面測試：掛載後只呼叫 `GET` |
| AC31、AC32、AC33 | 前端 `usePlatformItems` 與清單元件測試 |
| AC34、AC35 | 前端 Dashboard 測試：一個平台的 `POST` 失敗，另外兩個仍更新，只有一個 toast |
| AC36 | 前端 Dashboard 測試 |
| AC37、AC38 | 前端 productivity 頁面測試 |
| AC39 | 前端 `usePlatformItems` 測試：`GET` 帶 `X-Auth-Error` 時 `authError` 為 true；清單元件測試：`isStale` 為 false、`authError` 為 true 時，畫面顯示授權失效的提示 |
| AC40、AC41 | 後端 integration：連結成功後 collection 有項目；fetch 失敗時仍回 201，帳號存在 |
| AC42、AC43、AC44 | 後端 integration：先把 `last_sync_error_code` 設成 `REAUTH_REQUIRED`，更新憑證後清掉；fetch 失敗時仍回成功 |
| AC45 | 後端 integration：只改 `status` 時 fetch 沒被呼叫 |
| AC46、AC47、AC48 | 後端 unit：用兩個可控制的 fetch（`asyncio.Event`），讓先開始的那次在後開始的那次寫完之後才完成，確認項目、`last_synced_at`、`sync_started_at` 都是後開始那次的；後開始那次新增的項目還在 |
| AC49 | 既有的排程欄位保留測試，改到新的同步函式也通過 |
| AC50 | 後端 integration：定時同步一個使用者時，另一個使用者的項目與 `linkedAccounts` 欄位不變 |
| AC51 | 後端 unit：讓先開始的同步在寫入中途暫停（在項目寫入時等 `asyncio.Event`），再讓後開始的同步進入寫入，確認後者在等鎖、還沒寫任何項目；放行後最後的結果符合 AC46–AC48。拿掉鎖的實作這個測試要失敗 |
| AC52 | 後端 unit：兩次同步抓到的項目不同，後開始那次有一個先開始那次沒有的項目。先開始的同步在第 6 步寫入項目時暫停，把 `sync_lock_until` 改成已過期，讓後開始的同步拿到鎖並寫完；放行先開始的同步，確認後開始那次獨有的項目還在、同步結果仍是後開始那次的 |
| AC53 | 後端 unit：先開始的同步拿到鎖、在第 6 步暫停，把鎖改成已過期；讓後開始的同步拿到鎖之後暫停（還沒釋放）；放行先開始的同步跑完，確認 `sync_lock_owner` 仍是後開始那次的值；再放行後開始的同步 |
| AC54 | 後端 unit：抓資料期間刪掉 `linkedAccounts` 的帳號，結束後 collection 沒有新項目，也沒有新的帳號文件被建立 |
| AC55 | 後端 unit：抓資料期間把 `link_id` 換掉，結束後項目與同步結果都沒變 |
| AC56 | 後端 integration：帶 `Origin`（允許的來源）呼叫 `GET` 與 `POST`，回應的 `Access-Control-Expose-Headers` 包含三個 header |
| AC57 | 後端 unit／integration：讓 `sync_started_at` 比這次晚，`POST` 回資料庫的項目，而不是這次抓到的；`X-Synced-At` 等於資料庫裡的 `last_synced_at` |
| AC58、AC59 | 後端 integration：預先放一把沒過期、別人的鎖，有舊資料時回舊資料與 `X-Data-Stale: true`；沒有舊資料時回 503 `SERVICE_UNAVAILABLE`。等鎖時間在測試裡縮短 |
| AC60 | 後端 integration：密文換成用別的金鑰加密的值，`POST` 回 `REAUTH_REQUIRED`，`last_sync_error_code`、`sync_started_at` 不變 |
| AC61 | 後端 integration：連結帳號後的同步遇到解不開的憑證（mock 解密丟 `SecretDecryptError`），同步結果欄位不存在 |
| AC62 | 後端 integration：帳號文件缺少憑證欄位，`POST` 回 409 `NOT_LINKED` |
| AC63 | 後端 unit：資料庫事先放一筆這次抓不到的項目；寫入項目時暫停，把 `sync_lock_owner` 換成別的值，放行後 `POST` 的回應包含那一筆、`X-Synced-At` 等於資料庫的 `last_synced_at`，同步結果不變 |
| AC64 | 後端 integration：抓資料期間刪掉帳號，`POST` 回 409 `NOT_LINKED`；後端 unit：寫入項目時暫停、刪掉帳號，放行後 `POST` 回 409 `NOT_LINKED` |
| AC65 | 後端 integration：這次抓到的項目和資料庫的不同；抓資料期間換掉 `link_id`，`POST` 回資料庫的項目與 `last_synced_at` |
| AC66、AC67、AC70 | 後端 integration／unit：定時同步裡分別安排成功、抓取失敗（有舊資料）、被取代、帳號已變更（含寫入期間刪除帳號）、憑證資料不完整、預先佔住的鎖（等鎖時間縮短）、寫入途中鎖被換掉的帳號，確認計數各自落在 `succeeded`、`skipped` 或 `failed` |
| AC68 | 後端 unit：先開始那次抓到的項目和資料庫的不同。後開始的同步拿到鎖、寫入第 5 步的開始時間後暫停，把鎖改成已過期，讓先開始的同步拿到鎖；確認先開始的同步回傳「被取代」、項目與同步結果不變 |
| AC69 | 後端 unit：資料庫事先放一筆這次抓不到的項目；拿到鎖、寫入項目時暫停，換掉 `link_id`，放行後確認那一筆還在、同步結果不變 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
