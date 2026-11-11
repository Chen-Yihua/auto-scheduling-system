# API 錯誤回應第二階段：規格審查紀錄

- 規格：[docs/specs/issue-82-status-codes-phase2.md](../../specs/issue-82-status-codes-phase2.md)
- PR：#86
- 等級：高風險
- 輪數：2，另加開發者要求的限定範圍審查 3 次（都在 2026-11-11，審 scratchpad 的規格草稿，commit 是當時的 main `65cbfc1`）
- 最終結果：沒有阻擋項目（最後的阻擋項目由開發者決定或依查證依據修正）

## 摘要

- 發現：30 項（第 1 輪 10、第 2 輪 6、限定範圍 6、第二次限定範圍 5、第三次限定範圍 3）：Specification Defect 13、Missing AC 8、Factual Error 3、Improvement Suggestion 6；Major 8、Minor 16、Info 6
- 開發者決策：見「開發者決策」
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-11 `65cbfc1` | #1–#10（#1–#9） | 前端不自動重送新的錯誤狀態碼；Clerk 驗證分成取得 JWKS 與驗證 token 兩步；確認排程 401、400 的分類；reorder 先檢查再寫入、整批 400；確認排程寫回不丟錯；webhook 沒設定密鑰時啟動時記一次 error log |
| 2 | 2026-11-11 `65cbfc1` | #11–#16（#11–#16） | 依實測改寫 JWKS 的例外與 `kid` 找不到的 cooldown；前端改成依暫時性／永久性錯誤的重送規則；AC9 補 JWKS 失敗的例外；reorder 所有 400 檢查都在寫入之前；`$fetch` 設定改用 `.client` plugin |
| 限定範圍 | 2026-11-11 `65cbfc1` | #17–#22（#17–#19） | Clerk 驗證改成六個步驟並保留 cooldown 與 lock；鎖定 PyJWT、fastapi-clerk-auth 版本；重送規則寫明只套用在 `$fetch`、`useUserSync` 維持不重送；`Retry-After` 的 CORS `expose_headers` |
| 第二次限定範圍 | 2026-11-11 `65cbfc1` | #23–#27（#23） | 非本後端的請求維持 ofetch 預設，本後端以 URL 的 origin 與 path 判斷；`get_signing_keys()` 的 `AttributeError`、`TypeError` 歸成 502；hook 串接與 JWKS 測試的模擬位置 |
| 第三次限定範圍 | 2026-11-11 `65cbfc1` | #28–#30（#28） | 判斷本後端時 base path 正規化成以 `/` 結尾，測試加入沒有 path 的實際設定；cooldown 起點的行號與「成功」的範圍；`TypeError` 的情境 |


## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 新狀態碼 409、503、504 會讓前端自動重送 GET，多打外部平台 | Specification Defect | Major | 是 | 否 | 前端自動重送 | 拿掉 409、503、504（第 2 輪 #13 改成重送規則） | 開發者 | 規格已修改 |
| 2 | 1 | 只轉換 `PyJWKClientConnectionError`，Clerk 斷線、回非 JSON 時仍是 401 | Specification Defect | Major | 是 | 安全 | JWKS 錯誤分類 | 分成取得 JWKS 與驗證 token 兩步；`kid` 找不到 401；非預期例外 500（需求 3、AC4） | 開發者 | 規格已修改 |
| 3 | 1 | 確認排程寫入 Google 回 401、400 時 `failed` 的 `error_code` 沒定義 | Missing AC | Minor | 是 | 否 | — | 401 `REAUTH_REQUIRED`、400 `INTERNAL_ERROR`（需求 5、AC7） | 開發者 | 規格已修改 |
| 4 | 1 | reorder 回 400 時可能已寫入部分項目 | Missing AC | Major | 是 | 否 | reorder 先檢查再寫入 | 先檢查所有 id，整批 400、什麼都不寫（需求 6、AC8） | 開發者 | 規格已修改 |
| 5 | 1 | 共用的寫回函式一改，確認排程會在 Google 事件建立後整批失敗 | Missing AC | Major | 是 | 否 | — | 規則只套用在 reorder、fields、done，確認排程寫回維持不丟錯 | 開發者 | 規格已修改 |
| 6 | 1 | 不認得的來源前綴與 reorder 訊息內容沒定義 | Missing AC | Minor | 是 | 否 | — | 前綴不認得 400；訊息列送出的組合 id | 開發者 | 規格已修改 |
| 7 | 1 | webhook 沒設定密鑰時沒有要求記 error log | Missing AC | Minor | 是 | 安全 | — | 啟動時記一次 error log，請求時不重複記；不含密鑰值（需求 1、AC6） | 開發者 | 規格已修改 |
| 8 | 1 | AC9 和 AC7、AC8 矛盾 | Specification Defect | Minor | 是 | 否 | AC9 的例外 | AC9 列出例外 | 開發者 | 規格已修改 |
| 9 | 1 | 「目前的做法」行號錯誤 | Factual Error | Minor | 是 | 否 | — | 改正 | 主 session | 規格已修改 |
| 10 | 1 | 實作計畫檔案清單不完整 | Improvement Suggestion | Info | 否 | 否 | — | 補上 | 主 session | 規格已修改 |
| 11 | 2 | 抓 JWKS 的例外形式不只 `PyJWKClientConnectionError → URLError → TimeoutError` | Factual Error | Major | 是 | 安全 | JWKS 錯誤分類 | 依實測列出每種例外（需求 3、AC4 測試對應） | 主 session | 規格已修改 |
| 12 | 2 | `kid` 找不到和 JWKS 格式錯同一個例外類別；重新抓取受 30 秒 cooldown 限制 | Factual Error | Minor | 是 | 安全 | JWKS 錯誤分類 | 兩步的界線看呼叫的步驟；cooldown 內 401、重新抓失敗 502／504 | 主 session | 規格已修改 |
| 13 | 2 | 保留 500／502 自動重送，原本 4xx 變 500／502 的 GET 會多送一次 | Specification Defect | Major | 是 | 否 | 前端自動重送 | 改成依暫時性／永久性錯誤的重送規則（需求 7、AC9） | 開發者 | 規格已修改 |
| 14 | 2 | AC9 與假設 1 沒有列 AC4 的畫面變化 | Specification Defect | Minor | 是 | 否 | AC9 的例外 | AC9、假設 1 補上 | 主 session | 規格已修改 |
| 15 | 2 | reorder 其他會回 400 的檢查仍在寫入之後 | Missing AC | Minor | 是 | 否 | reorder 先檢查再寫入 | 所有 400 檢查都在寫入之前（需求 6、AC8） | 開發者 | 規格已修改 |
| 16 | 2 | `$fetch` 設定位置 `app.config` 不能用 | Specification Defect | Minor | 是 | 否 | — | 改用 `.client` plugin，判斷抽成純函式 | 主 session | 規格已修改 |
| 17 | 限定 | 只拆 `get_signing_key_from_jwt` 分不出 `kid` 找不到和重新抓失敗；沒要求保留 cooldown 與 lock | Specification Defect | Major | 是 | 安全 | JWKS 錯誤分類 | 六個步驟的順序，保留 cooldown 與 lock；測試任意 `kid` 不會再抓 | 主 session | 規格已修改 |
| 18 | 限定 | 子類別依賴私有成員，套件沒有鎖版本 | Specification Defect | Minor | 是 | 安全 | — | 鎖定 `PyJWT==2.14.0`、`fastapi-clerk-auth==0.0.9`；假設 3；用真的 `PyJWKClient` 的測試 | 主 session | 規格已修改 |
| 19 | 限定 | `useUserSync` 用原生 `fetch`，範圍沒寫 | Specification Defect | Minor | 是 | 否 | 前端重送 | 適用範圍只限 `$fetch`，`useUserSync` 維持不重送 | 主 session | 規格已修改 |
| 20 | 限定 | 重送表沒涵蓋沒有 `error_code` 的 500 | Missing AC | Minor | 否 | 否 | 前端重送 | 補「其他情況不重送」 | 主 session | 規格已修改 |
| 21 | 限定 | `Retry-After` 讀取路徑目前走不到 | Improvement Suggestion | Info | 否 | 否 | — | 改寫描述 | 主 session | 規格已修改 |
| 22 | 限定 | `X-Data-Stale` 等 header 也沒 expose（既有、範圍外） | Improvement Suggestion | Info | 否 | 否 | — | 開發者先確認正式環境的請求路徑再決定 | 開發者 | 不處理（待確認） |
| 23 | 第二次限定 | 「非本後端的回應」和「暫時性錯誤」兩列重疊 | Specification Defect | Minor | 是 | 否 | 前端重送 | 非本後端維持 ofetch 預設；以 URL 解析後的 origin 與 path 判斷 | 開發者 | 規格已修改 |
| 24 | 第二次限定 | 沒有回應時 ofetch 以 500 判斷；hook 串接沒有測試 | Specification Defect | Minor | 否 | 否 | — | 實作計畫與測試對應補上 | 主 session | 規格已修改 |
| 25 | 第二次限定 | JWKS 測試要模擬 `build_opener`；模組層級的實例共用快取 | Specification Defect | Minor | 否 | 否 | — | 測試對應寫明 | 主 session | 規格已修改 |
| 26 | 第二次限定 | JWKS 的 `keys` 元素不是 object 時回 500 | Specification Defect | Minor | 否 | 否 | JWKS 錯誤分類 | 只在 `get_signing_keys()` 內把 `AttributeError`、`TypeError` 歸成 502 | 開發者 | 規格已修改 |
| 27 | 第二次限定 | Clerk 故障期間 cooldown 擋不住任意 `kid` 的重新抓取 | Improvement Suggestion | Info | 否 | 安全 | — | 寫進需求 3 與已接受的風險（library 既有行為） | 主 session | 規格已修改 |
| 28 | 第三次限定 | `apiBaseUrl` 沒有 path 時，「以 `/` 為界」的比對沒有定義，照字面實作會讓所有請求被當成非本後端 | Missing AC | Major | 是 | 否 | 前端重送 | base path 正規化成以 `/` 結尾；測試加入沒有 path 的實際設定、結尾帶 `/`、`/api` 與 `/api2` | 主 session | 規格已修改 |
| 29 | 第三次限定 | cooldown 起點的行號與「成功」的範圍 | Improvement Suggestion | Info | 否 | 否 | — | 改正行號，寫明成功指 HTTP 與 JSON 解析成功 | 主 session | 規格已修改 |
| 30 | 第三次限定 | AC4 沒有 `TypeError` 的實際情境 | Improvement Suggestion | Info | 否 | 否 | — | AC4 與測試對應補 `n`／`e` 不是字串 | 主 session | 規格已修改 |

## 問題說明

### #1、#13 前端自動重送

ofetch 1.4.1 的 GET 預設依狀態碼重送一次（`retryStatusCodes` 含 408、409、425、429、500、502、503、504），前端沒有任何設定。這次許多錯誤從不重送的 4xx 變成 409、500、502、503、504，同一次操作會多打一次後端與外部平台；只拿掉部分狀態碼仍會讓原本 4xx、現在變 500／502 的 GET 多送一次。

### #2、#11、#12 JWKS 錯誤分類

`fastapi_clerk_auth` 的 `_decode_token` 用 `except Exception` 吞掉所有例外後回 403。PyJWT 2.14.0 的 `fetch_data` 只把 `URLError`、`TimeoutError` 包成 `PyJWKClientConnectionError`（`jwt/jwks_client.py:164-169`），讀回應時的斷線、非 JSON、沒有 key 會丟其他例外；`kid` 找不到與 JWKS 格式錯都是 `PyJWKClientError`，重新抓取受 cooldown 限制（`jwt/jwks_client.py:246-265`）。

### #4、#15 reorder 先檢查再寫入

外部項目在迴圈裡逐筆寫入（`backend/crud/schedulable_items.py:103-111`），手動任務與階段的檢查在之後才呼叫（`backend/crud/manual_task.py:351-374`），回 400 時資料已改了一部分。

### #5 確認排程寫回

確認排程寫回事件 id 共用 `_update_external`（`backend/crud/schedulable_items.py:159-166`）；在那裡丟錯會讓已建立 Google 事件的確認整批失敗。

### #7 webhook 沒設定密鑰

ADR 0011「例外」接受回 401 的前提是記 error log；目前兩個 webhook 都不記（`backend/routers/user.py:26-37`、`backend/routers/pr_review_webhook.py:63-73`）。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 前端自動重送 | 拿掉 409、503、504／接受 | 拿掉（之後由 #13 的決定取代） | 限流時立刻重送違反用意 |
| 2 | JWKS 錯誤分類 | 依步驟區分／接受 | 分成取得 JWKS 與驗證 token：JWKS 連線失敗 502、逾時 504、格式錯或缺 key 502；token 格式錯、簽章無效、過期、`kid` 找不到 401；不用大範圍 except | `kid` 找不到不一定是 Clerk 故障；程式的 bug 不能被誤判成 Clerk 故障 |
| 3 | `failed` 的 401、400 | 依建議 | 401 `REAUTH_REQUIRED`、400 `INTERNAL_ERROR` | — |
| 4、5、6、15 | reorder 與外部 id | 400／404／略過 | 先檢查所有項目（id、格式、前綴、主任務、階段優先序），整批 400、什麼都不寫；規則只套用在 reorder、fields、done | 排序是一次送整份清單，內容有誤屬於 400；不能留下寫一半的資料 |
| 7 | webhook 沒設定密鑰的 log | 依建議 | 啟動時記一次，請求時不重複；不含密鑰、簽章、請求內容 | 避免大量重複的 log |
| 8 | AC9 的例外 | 依建議 | 採納 | — |
| 13 | 前端重送 | 全部關掉／保留 500、502／依錯誤性質 | 暫時性錯誤重送、永久性錯誤與限流不重送；同步呼叫總共最多 3 次；只重送 GET 與帶 `Idempotency-Key` 的 POST；`UPSTREAM_ERROR` 算永久性；後端 `sync.py` 維持 2 次；非同步上限 5 次寫成之後的規則 | 系統的暫時性錯誤要能自動恢復，永久性錯誤重送沒有用 |
| 23 | 非本後端的請求 | 一律不重送／維持 ofetch 預設／套用同一套規則 | 維持 ofetch 預設；本後端以 URL 解析後的 origin 與 path 判斷，不用字串前綴 | 這次的範圍是本後端的錯誤回應 |
| 26 | JWKS 的 `keys` 元素不是 object | 歸成 502／接受 500 | 只在 `get_signing_keys()` 內歸成 502，log 保留例外 | 屬於外部服務的問題，不擴大到整個驗證流程 |
| — | 對照表沒有的 `error_code` | 依建議 | 對外 500 `INTERNAL_ERROR`；log 記原始 `error_code`、例外、request 識別資訊 | 不暴露內部實作 |

## 尚未處理

無。

## 查證紀錄

| 規格中的事實 | 結果 | 依據 |
|---|---|---|
| `AppError` 的預設狀態碼與 handler 照實回傳 | 正確 | `backend/core/errors.py:9-60`；`backend/core/exception_handlers.py:26-27` |
| 明確指定狀態碼的各處 | 正確 | `backend/platforms/router.py:64,79,89`、`jira.py:176`、`moodle.py:234`、`http_errors.py:96`、`backend/services/google_calendar.py:48`、`backend/routers/pr_review_webhook.py:60,186,189`、`backend/crud/schedulable_items.py:37`、`backend/crud/user.py:34`、`backend/crud/linked_account.py:78` |
| Redis 500、資料庫連不上 503 | 正確 | `backend/core/exception_handlers.py:62-75` |
| `ClerkHTTPBearer` 一律 403、`_decode_token` 吞掉例外 | 正確 | `fastapi_clerk_auth/__init__.py:143-163`；`backend/core/security.py:20` |
| JWKS 各種失敗的實際例外 | 正確（實測，見需求 3） | `jwt/jwks_client.py:156-169`、`:198-201`、`:227-228`、`:246-265` |
| 解析 token header 只丟 `InvalidTokenError` 系列 | 正確（實測） | `jwt/exceptions.py` |
| GitHub、Jira、Google 都取得得到外部回應的 header | 正確 | `backend/platforms/http_errors.py:22-70`；`backend/services/google_calendar.py:36-49`；`backend/services/google_oauth.py:60-81`；`backend/routers/google_calendar.py:29-38` |
| `FailedConfirmation` 的欄位與失敗原因 | 正確 | `backend/schemas/schedule.py:34-37`；`backend/services/scheduler.py:366-381`；`backend/services/google_calendar.py:170-177` |
| 外部 id 不存在靜默 200；reorder 寫入先於檢查 | 正確 | `backend/crud/schedulable_items.py:32-48,96-111,147-152`；`backend/crud/manual_task.py:351-374` |
| ofetch 預設重送與在 Nuxt 改全域 `$fetch` 的方式 | 正確（`.client` plugin 可行，`app.config` 不行） | `frontend/node_modules/ofetch/dist/shared/*.mjs`；`frontend/node_modules/nitropack/dist/runtime/internal/client.mjs:1-3` |
| 兩個 webhook 密鑰在啟動時讀取 | 正確 | `backend/routers/user.py:19`；`backend/routers/pr_review_webhook.py:29` |
| Cloud Run 帶 `X-Cloud-Trace-Context` | 無法查證（平台行為） | — |
| 外部服務的 `Retry-After` 是秒數 | 無法查證（外部文件）；只轉送整數秒數，錯了只會少帶 header | — |

## 已接受的風險

- 確認排程期間 Google 回 401 時不換新 token，直接給 `REAUTH_REQUIRED`；token 剛好在寫入途中過期時，使用者會被要求重新連接。
- reorder 先檢查、後寫入之間，項目被同步刪除時，`update_one` 不更新任何資料，不回錯。
- PyJWKClient 的 30 秒 cooldown：Clerk 換金鑰後，最多 30 秒內用新金鑰簽的 token 會被回 401（library 既有行為）。
- 不處理 `PyJWKClient` 的同步請求會卡住 event loop 的問題。
- 只記 Cloud Run 的 `X-Cloud-Trace-Context`，不新增 request ID 機制。
- `UPSTREAM_ERROR` 在前端算永久性錯誤、不重送；外部服務的暫時性錯誤只靠後端 `sync.py` 的重試（Google 的呼叫沒有後端重試）。
- Clerk 故障期間的重新抓取：cooldown 的起點是上次**成功**抓取的時間（HTTP 與 JSON 解析成功），抓取失敗不會更新。所以上次成功抓取後 30 秒內 cooldown 有效（AC4 測的是這個情況）；Clerk 故障、而且已超過這 30 秒時，每個帶未知 `kid` 的請求都會再抓一次，JWKS 快取（300 秒）過期後則每個請求都會抓。每次抓取最長等 30 秒（`jwks_client_timeout`），而且是同步的，會卡住 event loop，連不需要登入的 endpoint 也會變慢。接受的理由：這是 library 既有、目前程式也一樣的行為，不是這次造成的；Clerk 故障時登入本來就無法完成；要改善需要改成非同步抓取或記錄失敗的抓取並退避，超出這次「狀態碼與分類」的範圍。
- 格式錯誤的 JWKS 回應會被 library 快取 300 秒，這段期間每個請求都是 502：library 既有的行為。
