# 全站 API 狀態碼盤點與設計原則：規格審查紀錄

- 規格：[docs/specs/issue-62-status-codes.md](../../specs/issue-62-status-codes.md)
- PR：#76
- 等級：標準
- 輪數：2（第 1 輪 2026-11-10 `aedbdbf`；第 2 輪 2026-11-10 `aedbdbf`；兩輪都審 scratchpad 的規格與 ADR 草稿，commit 是當時的 main）
- 最終結果：沒有阻擋項目（第 2 輪的阻擋項目由開發者決定後修改規格）

## 摘要

- 發現：22 項（第 1 輪 15 項、第 2 輪 7 項）：Specification Defect 7、Missing AC 8、Factual Error 4、Improvement Suggestion 3；Major 6、Minor 13、Info 3
- 開發者決策：15 項
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-10 `aedbdbf` | #1–#15（#1–#13） | 盤點補上 Clerk JWKS、422 帶回憑證、外部平台抓項目的 4xx 分類、Moodle 判斷、webhook payload、Redis、排程外部 id、確認排程逐筆失敗；問題清單從 12 項增加到 20 項；第一階段的 `error_code` 一律依實際原因給；#59 的被取代驗收條件寫進需求 4；ADR 加 422 不帶輸入值、沒有 `error_code` 的退回處理、憑證被拒與無法解密的規則、過渡期間；Idempotency 拆成兩個 `error_code` |
| 2 | 2026-11-10 `aedbdbf` | #16–#22（#16–#21） | 帳號列表 500 改 200 寫成第一階段的例外，外部 id 不存在移到第二階段；ADR 過渡期間加 JWKS 與成功回應的例外；盤點補 Moodle 抓作業、刪除手動任務的 Google 路徑；Jira 抓項目 404 歸 `REAUTH_REQUIRED` |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 第一階段 `Closes #59`，但 #59 要求改狀態碼，和「狀態碼一律不變」、ADR 的 503 衝突 | Specification Defect | Major | 是 | 否 | — | 第一階段照樣 `Closes #59`，issue 與 PR 寫明 #59 的「403 限流回 502」被 ADR 0011 取代（需求 4、AC5） | 開發者 | 規格已修改 |
| 2 | 1 | 第一階段 `error_code` 依原因還是依目前狀態碼沒有定義 | Specification Defect | Major | 是 | 否 | 第一階段與狀態碼不變 | 一律依實際原因給，狀態碼維持原值（需求 3、ADR「過渡期間」） | 開發者 | 規格已修改 |
| 3 | 1 | Clerk JWKS 連不上或逾時也回 403 | Missing AC | Major | 是 | 否 | — | JWKS 失敗歸 502／504，第二階段做（P13、ADR） | 開發者 | 規格已修改 |
| 4 | 1 | GitHub、Jira 抓項目時 4xx 一律當成憑證失效；Moodle 判斷是推斷 | Missing AC | Major | 是 | 否 | 外部平台抓項目的錯誤分類 | 補進盤點，列為 P15、P16 | 開發者 | 規格已修改 |
| 5 | 1 | 422 回應帶回送出的 apiKey、password | Missing AC | Major | 是 | 安全 | — | 第一階段一律拿掉 `input`、`ctx`（P14、ADR「回應格式」） | 開發者 | 規格已修改 |
| 6 | 1 | 帳號列表與 PATCH 的憑證解密失敗回 500 | Missing AC | Minor | 是 | 否 | 第一階段與狀態碼不變 | 列表照常回 200 並標示要重新連結；PATCH 回 409 `REAUTH_REQUIRED`（P7、ADR） | 開發者 | 規格已修改 |
| 7 | 1 | webhook payload、Redis 故障、排程外部 id、確認排程逐筆失敗沒列進盤點 | Missing AC | Minor | 是 | 否 | 第一階段與狀態碼不變 | 列為 P17–P20；確認排程單筆失敗列為可接受 | 開發者 | 規格已修改 |
| 8 | 1 | 換新 token 後 Google 其他 4xx 回 500，不是 400 | Factual Error | Minor | 是 | 否 | — | P1 與盤點改正 | 主 session | 規格已修改 |
| 9 | 1 | P5 說前端會當成要重新連結，實際只顯示「儲存失敗」 | Factual Error | Minor | 是 | 否 | — | P5 改正 | 主 session | 規格已修改 |
| 10 | 1 | 盤點幾列描述不精確 | Factual Error | Minor | 是 | 否 | — | reorder、fields、done、`GET /manual-tasks/me`、Moodle 各列改正 | 主 session | 規格已修改 |
| 11 | 1 | ADR 把 PATCH 也寫成「還沒有已存的憑證」 | Specification Defect | Minor | 是 | 否 | — | 連結或更新帳號時被拒一律 400 `INVALID_CREDENTIALS`（ADR「憑證被拒」） | 開發者 | 規格已修改 |
| 12 | 1 | 沒有 `error_code` 的回應怎麼處理沒定義 | Missing AC | Minor | 是 | 否 | — | 前端依狀態碼退回；ADR 改成「本後端產生的錯誤回應」，未知路由 404、405 也帶 `error_code` | 開發者 | 規格已修改 |
| 13 | 1 | 部分列沒有 `檔案:行號`；解密失敗不刪 token 沒寫進 ADR | Specification Defect | Minor | 是 | 否 | — | 補行號；ADR 加「憑證無法解密」 | 主 session | 規格已修改 |
| 14 | 1 | 主 session 擬定的 `error_code` 名稱與分類 | Improvement Suggestion | Info | 否 | 否 | — | 開發者採用；Idempotency 拆成 `IDEMPOTENCY_KEY_REUSED`、`REQUEST_IN_PROGRESS` | 開發者 | 規格已修改 |
| 15 | 1 | `backend/README.md` 沒指向 ADR；第一階段 `detail` 要對齊 | Improvement Suggestion | Info | 否 | 否 | — | 寫進第一階段範圍（需求 3） | 主 session | 規格已修改 |
| 16 | 2 | 第一階段「狀態碼一律不變」和帳號列表改 200、外部 id 不存在要給 `error_code` 衝突 | Specification Defect | Major | 是 | 否 | 第一階段與狀態碼不變 | 帳號列表 500 改 200 寫成第一階段的例外；外部 id 不存在移到第二階段（需求 3、AC5、ADR「過渡期間」） | 開發者 | 規格已修改 |
| 17 | 2 | ADR「過渡期間」沒寫 JWKS 的例外 | Specification Defect | Minor | 是 | 否 | — | ADR 加例外 | 開發者 | 規格已修改 |
| 18 | 2 | Idempotency 409 只有新增子任務會回；fields、done 的 404 行號引錯 | Factual Error | Minor | 是 | 否 | — | 盤點拆列、改行號 | 主 session | 規格已修改 |
| 19 | 2 | Moodle 抓作業也用同一個帳密判斷 | Missing AC | Minor | 是 | 否 | 外部平台抓項目的錯誤分類 | 補進盤點與 P16：明確帳密錯誤才 `REAUTH_REQUIRED` 並設 `X-Auth-Error` | 開發者 | 規格已修改 |
| 20 | 2 | 刪除手動任務漏列 Google 的其他失敗路徑 | Missing AC | Minor | 是 | 否 | — | 補進盤點，問題加 P3、P4、P7 | 開發者 | 規格已修改 |
| 21 | 2 | 抓 Jira 項目的 404「依原因」沒有定義 | Specification Defect | Minor | 是 | 否 | — | 歸 409 `REAUTH_REQUIRED`（網域可能已失效）；`NOT_FOUND` 只用在本系統的資料 | 開發者 | 規格已修改 |
| 22 | 2 | webhook 逾時沒分 504；前端「只看狀態碼」不精確 | Improvement Suggestion | Info | 否 | 否 | — | 盤點與背景改正 | 主 session | 規格已修改 |

## 問題說明

### #1 #59 的驗收條件和第一階段衝突

#59 建議的驗收條件要求 Google 用 403 回報限流時回 502；規格的第一階段不改狀態碼，ADR 又把外部限流定成 503。

### #2、#6、#7、#16 第一階段與狀態碼不變

第一階段「照對照表加 `error_code`、狀態碼不變」沒有說依原因還是依目前的狀態碼給；之後加進第一階段的帳號列表修正（`crud/linked_account.py:21`、`:55`，目前 500）與外部 id 不存在（`crud/schedulable_items.py:30-38`、`:140-144`，目前靜默 200）都需要改狀態碼。

### #3 Clerk JWKS 失敗

`fastapi_clerk_auth` 的 `_decode_token` 用 `except Exception` 吞掉例外後回 403，JWKS 連不上和 token 無效分不出來。

### #4、#19 外部平台抓項目的錯誤分類

GitHub、Jira 把 400、401、403、404 都當成不可重試的憑證失效（`platforms/github.py:20`、`platforms/jira.py:18`），GitHub 用 403 回報的限流也算在內；Moodle 只要登入後網址不是 `/my/` 就算帳密錯（`platforms/moodle.py:51-55`），連結與抓作業共用。

### #5 422 帶回憑證

FastAPI 預設的 422 回應有 `input` 欄位，缺欄位時是整個 request body；`backend/main.py:54-59` 沒有自訂 handler。

### #11 PATCH 的憑證被拒

只改 Jira 網域或 Moodle 帳號時，用已存的憑證驗證（`platforms/jira.py:161-167`、`platforms/moodle.py:200-206`）。

### #12 沒有 error_code 的回應

Cloud Run 自己回的 5xx、504 與網路錯誤不經過後端；`frontend/utils/errorMessages.ts` 只處理 429。

### #13、#17、#20、#21 其他規格缺漏

部分盤點列沒有行號；ADR 少了不刪 token 的理由與 JWKS 的過渡例外；刪除手動任務會先取 token 與 primary calendar（`services/google_calendar.py:232`）；Jira 404 的分法沒有寫。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | #59 的驗收條件 | `Closes #59` 並寫明被取代／`Refs #59`／第一階段破例改狀態碼 | `Closes #59`，寫明被 ADR 0011 取代 | 使用者看到的問題在第一階段修正 |
| 2 | 第一階段 `error_code` 的給法 | 一律依原因／只有 Bug 依原因 | 一律依原因 | 前端一次改完 |
| 3 | Clerk JWKS 失敗 | 歸 502／504／接受現狀 | 歸 502／504，第二階段 | 符合外部服務暫時問題的分類 |
| 4 | 外部平台抓項目的 4xx | 依建議補進盤點 | 採納 | — |
| 5 | 422 帶回憑證 | 一律拿掉／只對敏感 schema／接受 | 一律拿掉，第一階段 | 新增 schema 時不會漏 |
| 6 | 帳號列表解密失敗 | 200 並標示／整個 409／維持 500 | 200 並標示 | 不讓其他正常的帳號看不到 |
| 7 | 其他漏列的錯誤路徑 | 依建議 | 採納 | — |
| 11 | PATCH 被拒 | 一律 `INVALID_CREDENTIALS`／依有沒有送新憑證 | 一律 `INVALID_CREDENTIALS` | 使用者正在編輯表單 |
| 12 | 沒有 `error_code` 的回應 | 依建議 | 採納 | — |
| 14 | 擬定的名稱與分類 | 依建議 | 採納，Idempotency 拆成兩個 | 前端要能分辨可重試與不可重試 |
| 16 | 第一階段的狀態碼例外 | 列表留第一階段／兩者都移到第二階段 | 列表留第一階段寫成例外，外部 id 不存在移到第二階段 | 列表打不開是 Bug，改成成功不影響相容性 |
| 17 | ADR 的 JWKS 例外 | 依建議 | 採納 | — |
| 19 | Moodle 抓作業 | 依建議 | 採納 | — |
| 20 | 刪除手動任務的 Google 路徑 | 依建議 | 採納 | — |
| 21 | Jira 抓項目 404 | 依建議 | `REAUTH_REQUIRED` | 使用者要到設定改網域 |

## 尚未處理

無。

## 查證紀錄

最後一輪的查證紀錄：

| 規格中的事實 | 結果 | 依據 |
|---|---|---|
| `_STATUS_BY_ERROR` 的對應；DB 連不上 503、其他 500 | 正確 | `backend/core/exception_handlers.py:25-33`、`:41-48`、`:75-83` |
| router 直接丟 `HTTPException` 的位置 | 正確 | `backend/routers/user.py:24-112`、`linked_account.py:49`、`google_calendar.py:45-55`、`schedule.py:116`、`:155`、`pr_review_webhook.py:56-62`、`backend/platforms/router.py:40-64` |
| 沒帶或無效的 JWT 回 403 | 正確 | `backend/core/security.py:20`、`fastapi_clerk_auth/__init__.py:151-163`、`docs/api.md:3` |
| 只有限流有 `error_code` | 正確 | `backend/core/rate_limit.py:39-44` |
| 逾時歸成 502 | 正確 | `backend/services/google_calendar.py:82-84`、`backend/platforms/router.py:59-61` |
| 前端判斷表與 `useUserSync` | 正確 | `frontend/utils/errorMessages.ts:16-44`、`frontend/composables/useUserSync.ts:14-17`、`:77` |
| users、linked-accounts 各列、P5、P7、P9 | 正確 | `backend/crud/user.py`、`backend/crud/linked_account.py`、`backend/platforms/github.py:94-102`、`jira.py:101-109`、`:161-167`、`moodle.py:186-189`、`:200-206` |
| 外部平台抓項目、P15、P16 | 正確（Moodle 抓作業第 2 輪補上） | `backend/platforms/router.py:38-69`、`github.py:20`、`:55-58`、`jira.py:18`、`:56-60`、`moodle.py:51-55`、`sync.py:45-52`、`:77` |
| manual-tasks、reorder、fields、done、P19 | 正確（第 2 輪改正 409 與行號） | `backend/routers/manual_task.py:117-120`、`:215-225`；`backend/crud/manual_task.py:322`、`:353-356`；`backend/crud/schedulable_items.py:30-40`、`:139-144` |
| suggest、confirm、oauth、P1、P4、P8、P20 | 正確 | `backend/services/google_calendar.py:34-40`、`:51-54`、`:100`、`:160-168`；`backend/services/google_oauth.py:74`、`:82`；`backend/routers/google_calendar.py:43-55` |
| GitHub webhook、P17 | 正確 | `backend/routers/pr_review_webhook.py:75`、`:81-84`、`:160-166` |
| P13：JWKS 失敗被吞掉後回 403 | 正確 | `fastapi_clerk_auth/__init__.py:125-146` |
| P14：422 帶回 `input` | 正確（實際重現） | `backend/main.py:52-59`、`backend/schemas/linked_account.py:4-10` |
| P18：限流計數遇到 Redis 故障 500 | 無法查證（推論，規格已標註） | `backend/core/rate_limit.py:25-36` |
| AC3：盤點涵蓋 `docs/api.md` 的每個 endpoint | 正確 | `docs/api.md:9-77` |

## 已接受的風險

- 盤點記錄的是核准當時的狀態，合併後不隨程式更新；後續各階段的 issue 依當時的程式碼重寫，實作審查不把盤點和之後程式的差異當成新發現。
- 過渡期間同一個 `error_code` 可能搭配和對照表不同的狀態碼（ADR「過渡期間」）。
- webhook 沒設定簽章密鑰時維持 401（ADR「例外」）。
- 外部平台同步失敗但有舊資料時回 200 加 header；確認排程時單筆失敗列在 `failed`；AI 推估與 Gemini 失敗不回錯誤（規格「可接受的既有設計」）。
