# API 錯誤回應第一階段：規格審查紀錄

- 規格：[docs/specs/issue-77-error-codes.md](../../specs/issue-77-error-codes.md)
- PR：#79
- 等級：高風險
- 輪數：2，另加開發者要求的限定範圍審查 2 次（第 1 輪、第 2 輪、增量審查、針對性檢查都在 2026-11-10，審 scratchpad 的規格草稿，commit 是當時的 main `1884a74`）
- 最終結果：沒有阻擋項目（最後的阻擋項目由開發者交給主 session 依建議決定後修改規格）

## 摘要

- 發現：36 項（第 1 輪 18、第 2 輪 10、增量審查 6、針對性檢查 2）：Specification Defect 20、Missing AC 11、Factual Error 2、Improvement Suggestion 3；Critical 2、Major 8、Minor 21、Info 5
- 開發者決策：見「開發者決策」
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-10 `1884a74` | #1–#18（#1–#16、#18） | `needs_reauth` 帳號走 PATCH 重新連結；行事曆卡片只有 `NOT_LINKED` 設成未連接；需求 4、5 補齊外部平台各種回應；`detail` 與 `error_code` 一致並改中文；只有解密失敗才標要重新連結；`console.error` 不印錯誤物件；HTTPException handler 保留 header |
| 2 | 2026-11-10 `1884a74` | #19–#28（#19–#26） | AC1 對齊卡片規則；前置檢查失敗不當成未連接；PATCH 解密失敗維持 500；連結時 400／403 分類；任務精靈與任務表單維持以 `detail` 取代說明；`Retry-After` 列入不做；共用資料庫風險記成待確認（#78） |
| 增量 | 2026-11-10 `1884a74` | #29–#34（#29–#32） | 連結帳號各列寫明狀態碼；Jira DNS 判斷依 `socket.gaierror`；元件測試；前置檢查失敗與保留清單的優先順序 |
| 針對性 | 2026-11-10 `1884a74` | #35–#36（#35、#36） | 前置檢查失敗維持最近一次已知的結果；保留的狀態綁定目前的 Clerk 使用者 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `needs_reauth` 的帳號照既有流程無法重新連結 | Specification Defect | Critical | 是 | 否 | — | 前端當成已連結、儲存走 PATCH 並要求完整憑證（需求 6、AC9） | 開發者 | 規格已修改 |
| 2 | 1 | 行事曆卡片遇到任何錯誤都顯示「尚未連接」 | Specification Defect | Major | 是 | 否 | 行事曆卡片狀態 | 只有 `NOT_LINKED` 設成未連接，其他錯誤照常嵌入並跳 toast（需求 7、AC1） | 開發者 | 規格已修改 |
| 3 | 1 | 抓外部平台項目的表少了其他 4xx／3xx、解析失敗、資料庫錯誤 | Missing AC | Minor | 是 | 否 | 外部回應分類 | 需求 5 補三列 | 開發者 | 規格已修改 |
| 4 | 1 | 連結帳號時其他非 200、Moodle 導向別處、解析失敗沒定義 | Missing AC | Major | 是 | 否 | 外部回應分類 | 需求 4 補列；`AccessDeniedError` 的預設 | 開發者 | 規格已修改 |
| 5 | 1 | 舊的 `detail` 文字和新的 `error_code` 衝突 | Missing AC | Major | 是 | 否 | — | 需求 4「`detail`」段、AC16 | 開發者 | 規格已修改 |
| 6 | 1 | Google 換新 token 後的 4xx、換 token 時 429、OAuth 其他錯誤碼 | Missing AC | Minor | 是 | 否 | 外部回應分類 | 需求 4 Google 列 | 開發者 | 規格已修改 |
| 7 | 1 | 沒有可更新的欄位沒有給 `INVALID_REQUEST` | Missing AC | Minor | 是 | 否 | — | 需求 4 | 開發者 | 規格已修改 |
| 8 | 1 | webhook 貼留言、限流 Redis、`cache_delete` 漏列 | Missing AC | Minor | 是 | 否 | — | 需求 4 | 開發者 | 規格已修改 |
| 9 | 1 | `NOT_LINKED` 不顯示錯誤的範圍、`detail` 取代或附加 | Specification Defect | Minor | 是 | 否 | 前端顯示規則 | 只在有「尚未連接」狀態的畫面處理；`detail` 附加（需求 7、AC12） | 開發者 | 規格已修改 |
| 10 | 1 | Moodle `TimeoutException` 分類重疊、登入頁比對規則 | Specification Defect | Minor | 是 | 否 | 外部回應分類 | 需求 5 Moodle 列、AC7 | 開發者 | 規格已修改 |
| 11 | 1 | GitHub secondary rate limit、Google `dailyLimitExceeded` | Specification Defect | Minor | 是 | 否 | 外部回應分類 | 依官方文件補進假設 1 與需求 4、5 | 開發者 | 規格已修改 |
| 12 | 1 | `useUserSync` 的退回方式和 AC12 不一致 | Specification Defect | Minor | 是 | 否 | 前端顯示規則 | AC12 註明例外 | 開發者 | 規格已修改 |
| 13 | 1 | 「憑證無法解密」的範圍沒限定 | Missing AC | Minor | 是 | 安全 | — | 只有 `decrypt_secret` 的 `ValueError` 算（AC18） | 開發者 | 規格已修改 |
| 14 | 1 | HTTPException handler 的 header 與沒列到的狀態碼 | Missing AC | Minor | 是 | 否 | — | 需求 2、AC19 | 開發者 | 規格已修改 |
| 15 | 1 | 前端測試對應不足 | Specification Defect | Minor | 是 | 否 | 測試對應 | 補 vitest | 開發者 | 規格已修改 |
| 16 | 1 | `console.error` 印出送出的憑證與 JWT | Missing AC | Minor | 是 | 安全 | — | 只記 status 與 `error_code`（AC17） | 開發者 | 規格已修改 |
| 17 | 1 | 刪事件時未連接用 `REAUTH_REQUIRED` 沒寫理由 | Improvement Suggestion | Info | 否 | 否 | — | 需求 4 補理由 | 主 session | 規格已修改 |
| 18 | 1 | 背景的 `main.py` 行號 | Factual Error | Info | 是 | 否 | — | 改正 | 主 session | 規格已修改 |
| 19 | 2 | AC1 權限不足照常嵌入，和卡片規則衝突 | Specification Defect | Major | 是 | 否 | 行事曆卡片狀態 | AC1 分成兩種情況 | 開發者 | 規格已修改 |
| 20 | 2 | 清單從沒載入成功、前置檢查失敗時的畫面沒定義 | Missing AC | Major | 是 | 否 | 行事曆卡片狀態 | 顯示「暫時無法載入」，不顯示未連接（需求 7、AC20） | 開發者 | 規格已修改 |
| 21 | 2 | PATCH 解密失敗會從 500 變 401；兩列沒寫維持 500 | Specification Defect | Major | 是 | 否 | 狀態碼維持 | 寫明維持 500；`AppError` 可分別指定狀態碼 | 主 session | 規格已修改 |
| 22 | 2 | 連結時 400、無限流特徵 403 的歸類和分類原則不一致 | Specification Defect | Minor | 是 | 否 | 外部回應分類 | 400 `INTERNAL_ERROR`、403 `INVALID_CREDENTIALS`、其他 `UPSTREAM_ERROR`，狀態碼維持 403 | 開發者 | 規格已修改 |
| 23 | 2 | `detail` 附加和既有畫面衝突 | Specification Defect | Minor | 是 | 否 | 前端顯示規則 | 任務精靈、任務表單維持取代；OAuth 回呼顯示 `detail` | 開發者 | 規格已修改 |
| 24 | 2 | 背景說 OAuth 畫面顯示授權碼無效 | Factual Error | Minor | 是 | 否 | — | 改正 | 主 session | 規格已修改 |
| 25 | 2 | 表格缺縮排 | Specification Defect | Info | 是 | 否 | — | 補縮排 | 主 session | 規格已修改 |
| 26 | 2 | AC12 畫面層、AC19 的 401 測試 | Specification Defect | Minor | 是 | 否 | 測試對應 | 補 vitest；401 改用 unit | 主 session | 規格已修改 |
| 27 | 2 | `Retry-After` 這一階段做不做 | Improvement Suggestion | Info | 否 | 否 | — | 列入不做（第二階段） | 開發者 | 規格已修改 |
| 28 | 2 | 共用資料庫時重新連結會覆寫另一個環境的憑證 | Improvement Suggestion | Minor | 否 | 否 | — | 記成待確認的風險（假設 4），另開 issue | 開發者 | [#78](https://github.com/Chen-Yihua/auto-scheduling-system/issues/78) |
| 29 | 增量 | 連結帳號各列沒寫狀態碼 | Specification Defect | Major | 是 | 否 | 狀態碼維持 | 每列寫明狀態碼，AC8 測試補齊 | 主 session | 規格已修改 |
| 30 | 增量 | 保留清單與前置檢查失敗的優先順序 | Specification Defect | Minor | 是 | 否 | 行事曆卡片狀態 | 曾成功就保留；帳號設定維持上一次已知狀態（之後由 #35 改成最近一次已知的結果） | 開發者 | 規格已修改 |
| 31 | 增量 | Jira DNS 與連不上的判斷重疊 | Specification Defect | Minor | 是 | 否 | 外部回應分類 | 依例外鏈中的 `socket.gaierror` | 主 session | 規格已修改 |
| 32 | 增量 | AC1、AC20 沒有元件測試 | Specification Defect | Minor | 是 | 否 | 測試對應 | 補元件測試 | 主 session | 規格已修改 |
| 33 | 增量 | 需求 4 禁用說法少「權限不足」 | Specification Defect | Info | 否 | 否 | — | 補上 | 主 session | 規格已修改 |
| 34 | 增量 | AC22 測試少 Jira | Missing AC | Minor | 否 | 安全 | — | 補上 | 主 session | 規格已修改 |
| 35 | 針對性 | 「曾成功就保留」和之後的未連接、授權失效結果矛盾 | Specification Defect | Major | 是 | 否 | 行事曆卡片狀態 | 維持最近一次已知的結果（需求 7、AC20） | 開發者交給主 session | 規格已修改 |
| 36 | 針對性 | 保留的清單沒綁定登入使用者，換人登入會看到前一個人的資料 | Specification Defect | Critical | 是 | 安全 | — | 綁定目前的 Clerk 使用者，登出或換使用者時清除（需求 7、AC20） | 開發者交給主 session | 規格已修改 |

## 問題說明

### #1 憑證解不開的帳號無法重新連結

前端靠 `apiKey`／`password` 有沒有值判斷是否已連結（`frontend/composables/useLinkedAccount.ts:99-105`、`:131`），不回憑證時會送 POST 而得到 409，也沒有刪除按鈕（`frontend/components/header/AccountSettings.vue:61`、`:163-178`）。

### #2、#19、#20、#30、#35 行事曆卡片狀態

`useGoogleCalendar` 在任何錯誤時都設成未連接並清空清單（`frontend/composables/useGoogleCalendar.ts:45-50`、`:68-91`），而它是首頁與帳號設定共用的 composable，同一個頁面會重新抓好幾次，所以「成功、失敗、前置檢查失敗」的各種順序都會發生。

### #3、#4、#6、#10、#11、#22、#31 外部回應分類

GitHub、Jira 把 400、401、403、404 都當成憑證失效（`backend/platforms/github.py:21`、`backend/platforms/jira.py:18`），連結時 401 以外的非 200 一律回 403（`github.py:101-102`、`jira.py:108-109`）；Moodle 只看登入後網址（`backend/platforms/moodle.py:51-55`）；Jira DNS 失敗與連不上是同一種例外（`jira.py:102-104`）。

### #5 `detail` 文字

抓項目時 router 一律用 `auth_failed_detail`（「授權已失效，請重新連結帳號」，`backend/platforms/router.py:58`），前端改成顯示 `detail` 後會直接被看到。

### #13、#16、#34、#36 安全

解密的 except 太寬（`backend/platforms/router.py:43-46`）；ofetch 的錯誤物件帶著送出的 body 與 Authorization header；第三方回應原文在例外訊息裡（`github.py:56`、`jira.py:57`）；Clerk 登出時用 Nuxt 路由換頁，記憶體中的狀態會留給下一個登入的使用者。

### #21、#29 狀態碼維持

`exception_handlers.py` 依例外類別決定狀態碼，照 `error_code` 挑類別會改掉目前的狀態碼。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 憑證解不開的帳號怎麼重新連結 | 前端當成已連結走 PATCH／POST 覆寫／只給刪除 | 前端當成已連結走 PATCH | 沿用既有流程，不改 POST 語意 |
| 2 | 行事曆卡片 | 第三種狀態／iframe 照常 | iframe 照常，只有 `NOT_LINKED` 設成未連接 | 使用者仍看得到行事曆 |
| 3–8、10–12、14、15 | 第 1 輪其他補充 | 依建議 | 採納 | — |
| 9 | `NOT_LINKED` 範圍與 `detail` | 依建議 | 只在有狀態的畫面；`detail` 附加 | — |
| 13 | 解密失敗的範圍 | 只接 `ValueError`／照目前 | 只接 `ValueError` | 設定錯誤不該被藏成要重新連結 |
| 16 | `console.error` | 這個 PR 修／已接受的風險 | 這個 PR 修 | — |
| 19 | AC1 的寫法 | 依建議 | 採納 | — |
| 20 | 清單從沒載入成功 | 暫時無法載入／照常 iframe | 暫時無法載入；前置檢查失敗不當成未連接 | AC1 才驗證得了 |
| 22 | 連結時 400／403 | 依原則分類／維持 `UPSTREAM_ERROR` | 依原則分類，狀態碼維持 403 | 權限不足的 token 不該被當成暫時故障 |
| 23 | `detail` 附加的範圍 | 既有取代的畫面維持／全站附加／依類型 | 既有取代的畫面維持，其他附加，OAuth 回呼顯示 | 不讓既有訊息變差 |
| 27 | `Retry-After` | 這一階段做／不做 | 不做，第二階段 | — |
| 28 | 共用資料庫風險 | 已接受／另開 issue／這個 PR 處理 | 記成待確認的風險並另開 #78；觸發條件中同一個 Clerk 使用者 id 尚未以實際環境設定確認 | 既有問題，範圍比這個 PR 大 |
| 30 | 保留清單與前置檢查失敗 | 曾成功就保留／一律暫時無法載入 | 曾成功就保留，帳號設定維持上一次已知狀態，只保留頁面執行期間 | — |
| 35、36 | 最近一次結果、綁定使用者 | 依建議 | 開發者要求收斂、不再提問，交給主 session 依建議決定 | — |
| — | 過渡期間 `error_code` 與狀態碼不符 ADR 0011 對照表 | 接受／這一階段一起改 | 接受，第二階段統一 | 第一階段只加 `error_code` |
| — | `AccessDeniedError` 的預設 `error_code` | `INVALID_CREDENTIALS`／`REAUTH_REQUIRED`／`UPSTREAM_ERROR` | `INVALID_CREDENTIALS` | 只用在連結時驗證 token |

## 尚未處理

無。

## 查證紀錄

| 規格中的事實 | 結果 | 依據 |
|---|---|---|
| Google 5xx、429 以外的 4xx 轉成 400；前端把 400 當未連結 | 正確 | `backend/services/google_calendar.py:34-40`；`frontend/utils/errorMessages.ts:32-34` |
| GitHub、Jira 的 400、401、403、404 不重試；429、5xx、其他 4xx 重試、502 | 正確 | `backend/platforms/github.py:21`、`:55-59`；`backend/platforms/jira.py:18`、`:56-60`；`backend/platforms/sync.py:45-52` |
| 連結時 401 回 401、其他非 200 回 403、連不上 502 | 正確 | `backend/platforms/github.py:95-102`；`backend/platforms/jira.py:102-109` |
| Moodle 帳密判斷只看登入後網址；WebDriver 錯誤重試、502 | 正確 | `backend/platforms/moodle.py:51-55`、`:175-178`、`:182-189` |
| 帳號列表一個帳號解不開整個 500；PATCH 用已存的憑證解不開 500 | 正確 | `backend/crud/linked_account.py:21`、`:55`；`backend/platforms/jira.py:164`；`backend/platforms/moodle.py:203` |
| 422 帶回 `input`；沒有自訂 handler | 正確（實測） | `backend/main.py:54-59` |
| Clerk library 沒帶或無效的 token 回 403 | 正確 | `backend/core/security.py:20`；`fastapi_clerk_auth.ClerkHTTPBearer.__call__` |
| `AccessDeniedError` 只用在連結時驗證 token | 正確 | `backend/platforms/github.py:102`；`backend/platforms/jira.py:109` |
| Jira DNS 失敗的例外鏈裡有 `socket.gaierror` | 正確（實測 httpx 0.28.1） | `httpx/_transports/default.py:118`；`httpcore/_exceptions.py:14` |
| 前置檢查失敗目前直接設成未連結 | 正確 | `frontend/composables/useGoogleCalendar.ts:45-50`；`frontend/composables/usePlatformItems.ts:61-67` |
| 任務精靈、任務表單目前以 `detail` 取代預設說明 | 正確 | `frontend/composables/useScheduleWizard.ts:110-111`、`:157-158`；`frontend/composables/useTaskForm.ts:167-174` |
| 假設 1（限流的 reason、header、訊息） | 依官方文件，以測試固定 | GitHub「Rate limits for the REST API」、Google Calendar「Handle API errors」 |
| 假設 2（政大 SSO 帳密錯時停在登入頁） | 無法查證，以測試固定、上線後驗證 | `backend/platforms/moodle.py:39` |

## 已接受的風險

- 過渡期間 `error_code` 和狀態碼不完全符合 ADR 0011 對照表，第二階段統一。
- GitHub 403 限流、Moodle 登入失敗維持不重試，沒有舊資料時仍回 401。
- Moodle 只靠送出後是否停在登入頁判斷帳密錯誤，SSO 很慢時可能誤判。
- `socket.gaierror` 也包括 DNS 伺服器暫時失敗（`EAI_AGAIN`），會被當成網域錯；狀態碼同為 502。
- 抓 Clerk JWKS 失敗和 token 無效都帶 `UNAUTHENTICATED`，第二階段區分。
- 「最近一次已知的結果」只存在前端記憶體，重新整理後不保留。
- 共用資料庫時的覆寫不是已接受的風險：觸發條件待確認，追蹤在 #78（規格假設 4）。
