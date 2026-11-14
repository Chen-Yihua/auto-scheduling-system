# 外部平台定時同步：實作審查紀錄

- 規格：[docs/specs/issue-13-scheduled-sync.md](../../specs/issue-13-scheduled-sync.md)
- PR：#97
- 等級：高風險
- 輪數：3（第 1 輪 2026-11-14 `d2ae520`；第 2 輪 2026-11-14 `3599397`；第 3 輪 2026-11-14 `a4092ed`）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：9 項（程式沒照規格做 1、測試抓不到錯的程式 2、沒有錯，但可以更好 6；一般操作就會遇到的錯 1、影響小的問題 5、不影響功能 3）
- 開發者決策：無
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-14 `d2ae520` | #1–#5（#1） | 補寫入期間刪除帳號的測試；修正 api.md、architecture.md 的表格與寫法；#2、#3 開 issue |
| 2 | 2026-11-14 `3599397` | #6–#8（#6、#7） | 第 1 輪 #1、#4、#5 覆核已修正；立即同步成功後清掉「尚未綁定」等狀態；補 `useLinkedAccount` 的轉換測試；#8 開 issue |
| 3 | 2026-11-14 `a4092ed` | #9（無） | 第 2 輪 #6、#7 覆核已修正；#9 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 寫入期間刪除帳號應算「略過」，沒有測試擋住檢查順序寫反的實作 | 測試抓不到錯的程式 | 影響小的問題 | 是 | 否 | 第 7 步的檢查順序沒有測試 | 請 feature-implementer 補測試 | 規則 | `3599397` |
| 2 | 1 | 授權失效提示在新情境下仍寫「快取資料」「未知時間」 | 沒有錯，但可以更好 | 影響小的問題 | 否 | 否 | — | 開 issue | 規則 | #98 |
| 3 | 1 | Moodle 帳號名稱出現在後端 log，定時同步讓它每天出現 | 沒有錯，但可以更好 | 影響小的問題 | 否 | 安全 | — | 開 issue | 規則 | #99 |
| 4 | 1 | `docs/architecture.md` 組成表與 `docs/api.md`「內部」表的格式被弄壞 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 這個 PR 新增的文件內容寫錯位置，屬於文件同步，請 feature-implementer 在這個 PR 修正 | 主 session | `3599397` |
| 5 | 1 | 寫法：`docs/api.md` 的立即同步說明一個項目塞了五件事 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 由寫這份文件的 feature-implementer 在這個 PR 改 | 規則 | `3599397` |
| 6 | 2 | 立即同步成功後，清單仍顯示「尚未綁定」「憑證無法讀取」或「暫時無法載入」 | 程式沒照規格做 | 一般操作就會遇到的錯 | 是 | 否 | 立即同步沒清掉頁面狀態 | 請 feature-implementer 修正並補測試 | 規則 | `a4092ed` |
| 7 | 2 | 工作效率統計頁讀取帳號同步時間的轉換沒有測試 | 測試抓不到錯的程式 | 影響小的問題 | 是 | 否 | 帳號同步時間轉換沒有測試 | 請 feature-implementer 補測試 | 規則 | `a4092ed` |
| 8 | 2 | 平台讀取不限流、定時同步每小時 5 次有測試，卻沒有驗收條件 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 安全 | — | 開 issue | 規則 | #100 |
| 9 | 3 | 立即同步等不到寫入鎖時，回應沒帶「授權已失效」，提示會暫時消失 | 沒有錯，但可以更好 | 影響小的問題 | 否 | 否 | — | 開 issue | 規則 | #101 |

## 問題說明

### #1 寫入期間刪除帳號應算「略過」，沒有測試擋住檢查順序寫反的實作

實作計畫第 2 點第 7 步規定先確認帳號、再確認鎖（`backend/platforms/account_sync.py:124-131`），程式照做。但寫入期間刪除帳號的情況沒有測試：integration 測試在抓資料期間刪除（`backend/tests/integration/test_scheduled_sync_api.py:231-232`），第 4 步就擋下；unit 測試只在寫入期間換 `link_id`，兩種順序結果相同。順序改反時，定時同步會把這種帳號算成 `failed`，違反 AC66，測試仍會通過。

### #6 立即同步成功後，清單仍顯示「尚未綁定」「憑證無法讀取」或「暫時無法載入」

`syncNow` 成功時只更新項目與同步時間（`frontend/composables/usePlatformItems.ts:90-96`），沒有清掉打開頁面時記下的 `notLinked`、`needsReauth`、`unavailable`。清單元件先檢查這三種狀態（`frontend/components/platforms/GithubIssuesList.vue:53-78`），所以使用者在頁面上連結帳號後按「立即同步」，同步成功、上次同步時間也更新了，清單仍停在「尚未綁定」。AC31、AC35 在這些情況下不成立。

### #7 工作效率統計頁讀取帳號同步時間的轉換沒有測試

`frontend/composables/useLinkedAccount.ts:115,130` 把 `last_synced_at` 轉成 `lastSyncedAt`，統計頁的測試整個換掉了這個 composable（`frontend/tests/pages/productivity.test.ts:26-29`）。這行寫錯時統計頁一律顯示「尚未同步」，AC37 不成立，測試仍會通過。

## 開發者決策

無

## 尚未處理

無

## 安全與一致性檢查（第 3 輪）

| 項目 | 結果 | 依據 |
|---|---|---|
| 登入與權限：只動得到自己的資料，沒登入或沒權限時的回應 | 有涵蓋 | 平台 `POST`、`GET` 只用 Clerk token 的 `sub`（`backend/platforms/router.py:262-267`）；AC29 有測試。定時同步用 `hmac.compare_digest` 比對密鑰；沒設定密鑰或是空字串、格式不對、`Bearer` 後面是空的，都回 401（`backend/routers/scheduled_sync.py:42-48`；AC6、AC7 有測試）。限流的 key 是 Authorization header 的雜湊（`backend/core/rate_limit.py:16-24`），拿錯密鑰的請求用不到正確密鑰那一組的 `5/hour` 次數。AC50 驗證同步一個使用者不會動到其他使用者 |
| 輸入驗證與注入 | 不適用 | 新的 endpoint 沒有 body 或查詢參數；`LinkedAccountUpdate` 沒有新增欄位，使用者無法透過 PATCH 寫入 `link_id` 或鎖的欄位（`backend/schemas/linked_account.py:14-19`） |
| 憑證、token、個資不出現在 log、回應、錯誤訊息與公開的地方 | 有涵蓋 | 定時同步的回應只有三個筆數（`backend/schemas/scheduled_sync.py`）；未預期的例外只記類別名稱（`backend/routers/scheduled_sync.py:64`）；`LinkedAccountOut` 不帶內部欄位（AC23）；AC11 驗證明文與密文都不在 log。workflow 設 `permissions: {}`，密鑰只放在環境變數。Moodle 帳號名稱出現在 log 已開成 #99 |
| 同時操作 | 有涵蓋 | 搶鎖、開始時間、`link_id` 比對、只釋放自己的鎖（`backend/platforms/account_sync.py:71-188`）；AC46–AC55、AC68、AC69 用暫停點測到 |
| 中途失敗後的資料狀態 | 有涵蓋 | 抓取失敗不動項目（AC9）；第 7、9 步不符時不刪項目、不寫同步結果；`finally` 有條件地釋放鎖（`account_sync.py:183-188`）。程式當掉時鎖最多佔 5 分鐘，列在規格的已接受風險 |
| 和外部系統（Google Calendar、外部平台）的一致性 | 有涵蓋 | 每種結果在 `POST`、定時同步計數、連結時的行為都照需求 13a、24a–24f 實作（`backend/platforms/router.py:238-256`、`backend/routers/scheduled_sync.py:29-34,68-79`）。#9 是「等不到鎖」時 `X-Auth-Error` 的小落差，不影響資料 |
| 既有資料：結構改變時舊資料讀不讀得出來、要不要轉換 | 有涵蓋 | 新增的欄位都是選填；沒有 `link_id` 的舊帳號用 `$exists: False` 比對（`account_sync.py:55-57`），AC55 的參數化測試包括舊帳號；沒有同步紀錄時不帶 `X-Synced-At`（AC18），帳號清單回 `null`（AC22） |
