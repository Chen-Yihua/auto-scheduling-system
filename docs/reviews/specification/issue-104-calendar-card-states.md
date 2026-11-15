# Google 行事曆卡片合併「尚未連接」與「授權已失效」：規格審查紀錄

- 規格：[docs/specs/issue-104-calendar-card-states.md](../../specs/issue-104-calendar-card-states.md)
- PR：#106
- 等級：一般
- 輪數：2，另加開發者要求修改後的限定範圍審查 2 次（都在 2026-11-15，審 scratchpad 的規格草稿，commit 是當時的 main `e887a53`）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：14 項（第 1 輪 5、第 2 輪 2、修改後審查 A 5、修改後審查 B 2）：規格內容互相矛盾或沒有依據 5、規格對現有系統的描述和程式不符 2、規格沒寫某個情境該怎麼做 1、沒有錯但可以更好 6
- 開發者決策：3 項
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-15 `e887a53` | #1–#5（#1–#3） | issue-77 AC1(2) 也標成部分被取代；「暫時無法載入」條件改寫；名稱不符的測試改成重寫；AC3 改檢查舊文字片段；Dashboard 測試改檢查傳給卡片的參數 |
| 2 | 2026-11-15 `e887a53` | #6–#7（#6） | 「暫時無法載入」分成兩條路徑描述，AC5 改成「沒有已知的結果」；Dashboard 測試同時檢查 attribute |
| 修改後 A | 2026-11-15 `e887a53` | #8–#12（#8–#10） | 開發者決定自動查詢不跳 toast、第一次查詢前顯示載入中之後審查。AC7 排除正在連接；issue-77 取代範圍補 AC12；AC8 加前提並開 #105；新增 AC15 |
| 修改後 B | 2026-11-15 `e887a53` | #13–#14（無） | 連接成功後重新查詢、狀態檢查失敗時算有結果；實作計畫補 AC15 的測試 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 沒有把 issue-77-error-codes.md AC1(2) 標成部分被取代 | 規格內容互相矛盾或沒有依據 | 影響小 | 是 | 否 | 被取代範圍 | 背景列出兩份被部分取代的規格；實作計畫 7 兩份都改狀態 | 主 session | 規格已修改 |
| 2 | 1 | 「暫時無法載入」的條件描述和程式不符 | 規格對現有系統的描述和程式不符 | 影響小 | 是 | 否 | 暫時無法載入的描述 | 背景與 AC5 改成看最近一次已知的結果 | 主 session | 規格已修改 |
| 3 | 1 | 實作計畫刪掉名稱不符的測試，和決定的「重寫」不一致 | 規格內容互相矛盾或沒有依據 | 只供參考 | 是 | 否 | — | 改成重寫；AC6 補「不顯示需要連接的文字」 | 主 session | 規格已修改 |
| 4 | 1 | AC3 的舊文字照字面比對會誤判 | 沒有錯，但可以更好 | 影響小 | 否 | 否 | — | 改檢查「尚未連接」「請重新連接。」 | 開發者 | 規格已修改 |
| 5 | 1 | Dashboard 測試把卡片 stub 掉，看不到文字 | 沒有錯，但可以更好 | 只供參考 | 否 | 否 | — | 改檢查傳給卡片的參數 | 開發者 | 規格已修改 |
| 6 | 2 | AC5 沒有涵蓋 `/oauth/status` 失敗的路徑 | 規格對現有系統的描述和程式不符 | 影響小 | 是 | 否 | 暫時無法載入的描述 | 背景分兩條路徑描述；AC5 改成「沒有已知的結果」 | 主 session | 規格已修改 |
| 7 | 2 | Dashboard 測試只看 props 會永遠成立 | 沒有錯，但可以更好 | 只供參考 | 否 | 否 | — | 同時檢查 attribute | 開發者 | 規格已修改 |
| 8 | 修改後 A | 正在連接與第一次查詢還沒回來同時成立時，AC4 與 AC7 矛盾 | 規格內容互相矛盾或沒有依據 | 影響小 | 是 | 否 | — | AC7 加上「不是正在完成 Google 授權」；補兩者同時成立的測試 | 主 session | 規格已修改 |
| 9 | 修改後 A | 被取代範圍漏了 issue-77 AC12 | 規格內容互相矛盾或沒有依據 | 影響小 | 是 | 否 | 被取代範圍 | issue-77 標成部分被取代（AC1、AC12） | 主 session | 規格已修改 |
| 10 | 修改後 A | 前一個使用者的查詢還沒結束就換使用者，AC8 不成立 | 規格內容互相矛盾或沒有依據 | 影響小 | 是 | 安全 | — | AC8 加前提；另開 issue | 開發者 | [#105](https://github.com/Chen-Yihua/auto-scheduling-system/issues/105) |
| 11 | 修改後 A | 連接成功、重新查詢回來前卡片顯示需要連接 | 沒有錯，但可以更好 | 影響小 | 否 | 否 | — | 新增 AC15 | 開發者 | 規格已修改 |
| 12 | 修改後 A | 沒寫明哪些路徑不算有結果 | 沒有錯，但可以更好 | 只供參考 | 否 | 否 | — | 實作計畫 1 補上 Clerk 未載入、結果被丟掉的情況 | 主 session | 規格已修改 |
| 13 | 修改後 B | 連接成功後重新查詢、狀態檢查失敗時算不算有結果 | 規格沒寫某個情境該怎麼做 | 影響小 | 否 | 否 | — | 算有結果，顯示最近一次已知的結果 | 開發者 | 規格已修改 |
| 14 | 修改後 B | 實作計畫 6 沒列 AC15 的測試 | 沒有錯，但可以更好 | 只供參考 | 否 | 否 | — | 補上 | 主 session | 規格已修改 |

## 問題說明

### #1 沒有把 issue-77-error-codes.md AC1(2) 標成部分被取代

issue-77 AC1(2) 規定授權失效時卡片顯示「授權已失效」、帳號設定按鈕是「重新連接 Google Calendar」（`docs/specs/issue-77-error-codes.md:102,147`），這份規格改了這兩件事。`docs/specs/README.md:13` 規定要標成部分被取代。

### #2、#6 「暫時無法載入」的條件描述和程式不符

`useGoogleCalendar.ts` 有兩條路徑：`/oauth/status` 失敗時只在沒有已知結果才設成 true（第 82 行）；抓清單遇到暫時性錯誤時，最近一次不是載入成功就設成 true（第 131 行）。第 1 輪的改寫只對第二條成立，第 2 輪才分開描述。只改描述，行為不變。

### #3 實作計畫和決定不一致

決定是重寫 `GoogleCalendarEmbed.test.ts:53-61` 那個名稱不符的測試，草稿寫成刪掉，AC6 就只剩不檢查「需要連接的文字不出現」的測試。

### #8 AC4 與 AC7 矛盾

從 Google 授權頁回來時，`connecting` 為 true（`useGoogleOAuthCallback.ts:29`），同時第一次查詢還沒回來。實作計畫已定 `connecting` 優先，AC7 的文字沒有跟著寫。

### #9 被取代範圍漏了 issue-77 AC12

issue-77 AC12 依需求 7 規定兩種限流「顯示稍後再試」（`issue-77-error-codes.md:103,113,158`），行事曆自動查詢不跳 toast 後，這部分不成立。

### #10 換使用者時沿用前一個使用者的查詢

`fetchGoogleCalendars` 共用請求與判斷結果是否最新都只看連接次數（`useGoogleCalendar.ts:146,150`），`switchOwner` 不作廢進行中的請求，所以前一個使用者的結果可能寫進新使用者的畫面。main 上原本就有。

### #11、#13 連接成功後的畫面

連接成功後 `connecting` 變回 false，重新查詢回來前卡片會顯示最近一次已知的結果（`useGoogleOAuthCallback.ts:55,70`、`Dashboard.vue:52-54`）。新增 AC15 後，重新查詢時 `/oauth/status` 失敗的路徑（`useGoogleCalendar.ts:79-83`）要另外定義。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 10 | 換使用者時前一個使用者的查詢還沒結束 | A. AC8 加前提、另開 issue；B. 這次一起修並升成高風險 | A | 這次的主題是畫面文字與 toast；資料隔離另外以高風險處理（#105，和 #81 一起看） |
| 11 | 連接成功、重新查詢回來前的畫面 | 顯示載入中；維持現狀 | 顯示載入中（AC15） | 和第一次查詢前的處理一致，不讓使用者看到一閃而過的錯誤訊息 |
| 13 | 連接成功後重新查詢、狀態檢查失敗時 | A. 算有結果，顯示最近一次已知的結果；B. 停在載入中；C. 顯示暫時無法載入 | A | 很少發生；不用改「查詢失敗時維持最近一次已知的結果」的規則，畫面也不會卡住 |

## 尚未處理

無

## 查證紀錄（最後一輪）

| 規格中的事實 | 結果 | 依據（檔案:行號） |
|---|---|---|
| 背景：issue-77 AC1(1) 限流提示原本由頁面自動查詢的 toast 顯示 | 正確 | `docs/specs/issue-77-error-codes.md:103,113,147`；`frontend/composables/useGoogleCalendar.ts:132-137` |
| 背景：issue-77 AC1(2) 卡片顯示「授權已失效」，按鈕「重新連接 Google Calendar」 | 正確 | `docs/specs/issue-77-error-codes.md:102,147` |
| 背景：issue-77 AC12 的 `REAUTH_REQUIRED` 提示、兩種限流顯示稍後再試 | 正確 | `docs/specs/issue-77-error-codes.md:110,113,158` |
| 不做：共用請求只比較連接次數，不比較使用者 | 正確 | `frontend/composables/useGoogleCalendar.ts:145-146,150` |
| AC8：新使用者第一次取得結果前沒有已知的結果 | 正確 | `frontend/composables/useGoogleCalendar.ts:32-47` |
| AC15：`connectedCount` 遞增與 `connecting` 設回 false 在同一段同步程式 | 正確 | `frontend/composables/useGoogleOAuthCallback.ts:55,69-70` |
| AC15：授權完成後首頁與帳號設定都會重新查詢 | 正確 | `frontend/components/dashboard/Dashboard.vue:52-54`；`frontend/components/header/AccountSettings.vue:15` |
| 實作計畫 1：授權完成前發出的請求，結果會被丟掉 | 正確 | `frontend/composables/useGoogleCalendar.ts:81,86,99,109,150` |
| 實作計畫 1：Clerk 未載入時直接 return | 正確 | `frontend/composables/useGoogleCalendar.ts:66` |
| 實作計畫 1：`/oauth/status` 失敗、有已知的結果時維持原本的畫面 | 正確 | `frontend/composables/useGoogleCalendar.ts:79-83` |
| 實作計畫 1：第 19 行、第 141 行的註解內容 | 正確 | `frontend/composables/useGoogleCalendar.ts:19,141` |
| 實作計畫 1：拿掉 `needsReconnect` 後沒有其他使用者 | 正確 | `Dashboard.vue:20,101`、`GoogleCalendarEmbed.vue:9,54`、`AccountSettings.vue:8` 與對應測試；e2e 沒有用到 |
| 實作計畫 2：`connecting` 只在有授權碼時設成 true | 正確 | `frontend/composables/useGoogleOAuthCallback.ts:29` |
| 自動查詢會跳 toast 的地方只有 `useGoogleCalendar.loadCalendars` | 正確 | `useGoogleOAuthCallback`、`useSchedule`、`useTaskForm`、`useScheduleWizard` 都是使用者操作或授權結果 |

## 已接受的風險

- 授權失效的使用者不是從首頁進來時（例如直接打開任務頁），不會得到任何提示，要等他操作時才看到授權失效的 toast（開發者，Q7）。
- 已載入過的行事曆遇到暫時性錯誤或限流時，卡片照常顯示舊的行事曆，沒有任何提示（開發者，Q8）。
- 遇到暫時性錯誤時 `isConnected` 一律設成 true，即使最近一次已知的結果是授權失效或未連接（`useGoogleCalendar.ts:129`）。main 上原本的行為，規格「不做」寫明判斷邏輯不變。
- 前一個使用者的查詢還沒結束就換使用者，新使用者會看到前一個使用者的結果（開發者，#10），另開 #105。
- Google 授權失敗時 `connectedCount` 不遞增，卡片不回到載入中，維持原本的結果（`useGoogleOAuthCallback.ts:35-41,61-70`）。規格沒有改這條路徑。
