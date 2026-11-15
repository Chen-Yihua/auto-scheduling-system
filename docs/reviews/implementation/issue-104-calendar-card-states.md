# Google 行事曆卡片合併「尚未連接」與「授權已失效」：實作審查紀錄

- 規格：[docs/specs/issue-104-calendar-card-states.md](../../specs/issue-104-calendar-card-states.md)
- PR：#106
- 等級：一般
- 輪數：1（第 1 輪 2026-11-15 `47452c6`）
- 最終結果：仍有阻擋（#1，修正中）

## 摘要

- 發現：3 項（測試抓不到錯的程式 2、沒有錯但可以更好 1；影響小 2、只供參考 1）
- 開發者決策：無
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-15 `47452c6` | #1–#3（#1） | #1 請 feature-implementer 補測試；#2、#3 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 授權失效的舊路徑沒拔乾淨時，AC2、AC12 的測試照樣通過 | 測試抓不到錯的程式 | 影響小 | 是 | 否 | 舊狀態的測試保護 | 請 feature-implementer 補行為層斷言 | 規則 | 修正中 |
| 2 | 1 | 刪掉 toast 按鈕的測試後，沒有測試完整檢查 Google 授權網址的參數 | 測試抓不到錯的程式 | 影響小 | 否 | 否 | — | 開 issue | 規則 | [#107](https://github.com/Chen-Yihua/auto-scheduling-system/issues/107) |
| 3 | 1 | 測試名稱的 AC 編號混用三份規格 | 沒有錯，但可以更好 | 只供參考 | 否 | 否 | — | 開 issue | 規則 | [#108](https://github.com/Chen-Yihua/auto-scheduling-system/issues/108) |

## 問題說明

### #1 授權失效的舊路徑沒拔乾淨時，AC2、AC12 的測試照樣通過

如果 `useGoogleCalendar` 還回傳 `needsReconnect`、卡片還留著「授權已失效，請重新連接。」的分支、帳號設定按鈕還看它，現有測試全部通過。原因是三段測試都只看 `isConnected`／`connect`：`Dashboard.test.ts`、`AccountSettings.test.ts` 的 mock 不提供 `needsReconnect`，讀到 undefined，attribute 不輸出、按鈕條件不成立；`GoogleCalendarEmbed.test.ts:41` 只用 `connect=false` 掛載。這次的程式本身正確。

## 開發者決策

無

## 尚未處理

無
