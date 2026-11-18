# 授權失效提示正確反映清單資料狀態

- 狀態：已核准
- 等級：一般
- issue：#98
- PR：待建立

## 簡短說明

修正 GitHub、Jira 與 Moodle 清單在授權失效時的提示文字，讓提示符合目前是否有清單資料與上次同步時間。

## 背景

使用者開啟平台清單或按「立即同步」後，若平台回傳授權失效，`StaleDataBanner` 會顯示授權失效提示。當帳號從未成功同步、或授權失效時沒有舊資料，清單沒有項目，但提示仍寫「目前顯示的是快取資料（上次同步：未知時間）」，同時 `SyncStatus` 顯示「尚未同步」，造成畫面資訊矛盾。

目前 `StaleDataBanner` 在 [frontend/components/platforms/StaleDataBanner.vue](/home/auto-scheduling-system/frontend/components/platforms/StaleDataBanner.vue:15) 無條件把「快取資料」和 `formatRelativeTime(syncedAt)` 放進授權失效提示；`formatRelativeTime(null)` 在 [frontend/utils/time.ts](/home/auto-scheduling-system/frontend/utils/time.ts:3) 回傳「未知時間」。`SyncStatus` 在 [frontend/components/platforms/SyncStatus.vue](/home/auto-scheduling-system/frontend/components/platforms/SyncStatus.vue:11) 已將沒有同步時間顯示為「尚未同步」。三個平台清單分別持有完整的 `issues` 或 `assignments` 陣列，可提供提示元件判斷是否有可顯示資料。

## 需求

1. 授權失效且有上次同步時間時，提示顯示平台授權可能已失效、目前顯示的是快取資料、上次同步的相對時間，以及請重新連結帳號。
2. 授權失效且沒有上次同步時間時，提示不顯示「未知時間」或「上次同步」片段。
3. 授權失效且清單沒有任何項目時，提示不顯示「目前顯示的是快取資料」片段。
4. 授權失效且清單有項目但沒有上次同步時間時，提示保留清單資料狀態與重新連結帳號的提示，但不顯示「未知時間」。

## 不做

- 不修改授權失效的判斷、API 回應標頭、同步流程或錯誤 toast。
- 不修改一般 `stale` 提示的文字或顯示條件。
- 不修改 `SyncStatus` 的「尚未同步」或相對時間顯示。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 在授權失效、有清單項目且有上次同步時間時，系統顯示快取資料與上次同步的相對時間，並顯示重新連結帳號提示。 |
| AC2 | 在授權失效、清單沒有任何項目且沒有上次同步時間時，系統不顯示「目前顯示的是快取資料」或「未知時間」，並顯示重新連結帳號提示。 |
| AC3 | 在授權失效、清單有項目但沒有上次同步時間時，系統不顯示「未知時間」，並保留授權失效與重新連結帳號提示。 |
| AC4 | 在授權失效、清單沒有任何項目但有上次同步時間時，系統不顯示「目前顯示的是快取資料」，但顯示上次同步的相對時間與重新連結帳號提示。 |
| AC5 | 在一般資料過期提示且有或沒有清單項目時，系統維持既有提示顯示行為。 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中、未登入、未綁定、無權限 | 本次只處理 API 已回報授權失效後的共用提示文字，不改平台載入、登入、綁定或授權流程。 |
| 資料處理、資料一致性、安全性、外部系統狀態 | 本次不改資料寫入、同步一致性、憑證處理或外部平台請求，只改前端顯示。 |

## 實作計畫

1. 在 `StaleDataBanner` 增加代表清單是否有項目的必要輸入，授權失效訊息依清單是否有資料與 `syncedAt` 組合可見片段，避免呼叫 `formatRelativeTime(null)` 產生「未知時間」。
2. 在 GitHub、Jira、Moodle 清單把各自的資料陣列狀態傳給 `StaleDataBanner`。
3. 擴充 `StaleDataBanner` 元件測試，覆蓋有資料/無資料與有時間/無時間的授權失效組合，並確認一般過期提示不變。

## 測試對應

| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | `frontend/tests/components/StaleDataBanner.test.ts`：授權失效、有資料、有同步時間時顯示完整提示 | 否 |
| AC2 | `frontend/tests/components/StaleDataBanner.test.ts`：授權失效、無資料、無同步時間時省略快取資料與未知時間 | 是 |
| AC3 | `frontend/tests/components/StaleDataBanner.test.ts`：授權失效、有資料、無同步時間時省略未知時間 | 是 |
| AC4 | `frontend/tests/components/StaleDataBanner.test.ts`：授權失效、無資料、有同步時間時省略快取資料但保留同步時間 | 是 |
| AC5 | `frontend/tests/components/StaleDataBanner.test.ts`：一般過期提示維持既有文字；三個平台清單元件測試確認清單資料狀態傳給提示元件 | 否 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-18 | 建立 issue #98 規格草稿 | 記錄已確認的提示行為與測試範圍 | 待確認 |

## 請你決定

無
