# Google 行事曆卡片合併「尚未連接」與「授權已失效」：實作審查紀錄

- 規格：[docs/specs/issue-104-calendar-card-states.md](../../specs/issue-104-calendar-card-states.md)
- PR：#106
- 等級：一般
- 輪數：2（第 1 輪 2026-11-15 `47452c6`；第 2 輪 2026-11-15 `8b56933`）
- 最終結果：沒有阻擋項目（#2、#3 由開發者決定在這個 PR 補，修正中）

## 摘要

- 發現：3 項（測試抓不到錯的程式 2、沒有錯但可以更好 1；影響小 2、只供參考 1）
- 開發者決策：1 項
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-15 `47452c6` | #1–#3（#1） | #1 請 feature-implementer 補測試；#2、#3 開 issue |
| 2 | 2026-11-15 `8b56933` | 無 | 覆核 #1：三種錯的實作都會讓新測試失敗，已解決 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 授權失效的舊路徑沒拔乾淨時，AC2、AC12 的測試照樣通過 | 測試抓不到錯的程式 | 影響小 | 是 | 否 | 舊狀態的測試保護 | 請 feature-implementer 補行為層斷言：卡片測試傳入 `needsReconnect` attribute、Dashboard 與 AccountSettings 的 mock 回傳 `needsReconnect: ref(true)` | 規則 | `8b56933` |
| 2 | 1 | 刪掉 toast 按鈕的測試後，沒有測試完整檢查 Google 授權網址的參數 | 測試抓不到錯的程式 | 影響小 | 否 | 否 | — | 先開 issue；開發者決定在這個 PR 補 → AC16 | 開發者 | [#107](https://github.com/Chen-Yihua/auto-scheduling-system/issues/107)，修正中 |
| 3 | 1 | 測試名稱的 AC 編號混用三份規格 | 沒有錯，但可以更好 | 只供參考 | 否 | 否 | — | 先開 issue；開發者決定在這個 PR 補 → AC17 | 開發者 | [#108](https://github.com/Chen-Yihua/auto-scheduling-system/issues/108)，修正中 |

## 問題說明

### #1 授權失效的舊路徑沒拔乾淨時，AC2、AC12 的測試照樣通過

如果 `useGoogleCalendar` 還回傳 `needsReconnect`、卡片還留著「授權已失效，請重新連接。」的分支、帳號設定按鈕還看它，現有測試全部通過。原因是三段測試都只看 `isConnected`／`connect`：`Dashboard.test.ts`、`AccountSettings.test.ts` 的 mock 不提供 `needsReconnect`，讀到 undefined，attribute 不輸出、按鈕條件不成立；`GoogleCalendarEmbed.test.ts:41` 只用 `connect=false` 掛載。這次的程式本身正確。修正後，三種錯的實作都會讓新測試失敗（feature-implementer 實際改回錯的寫法確認，第 2 輪審查也逐一推演）。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 2、3 | 不阻擋的發現開 issue 還是在這個 PR 補 | 開 issue；在這個 PR 補 | 在這個 PR 補（規格新增 AC16、AC17） | #2 是這個 PR 刪掉的測試；兩項修正成本都很低 |

## 尚未處理

無
