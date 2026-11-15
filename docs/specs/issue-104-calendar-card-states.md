# Google 行事曆卡片合併「尚未連接」與「授權已失效」，自動查詢不跳 toast

- 狀態：已核准
- 等級：一般（只改畫面上的文字、提示方式與狀態的顯示，不改連接、授權的判斷，也不改 API 與資料）
- issue：[#104](https://github.com/Chen-Yihua/auto-scheduling-system/issues/104)
- PR：[#106](https://github.com/Chen-Yihua/auto-scheduling-system/pull/106)

## 簡短說明
首頁的 Google 行事曆卡片把「尚未連接」和「授權已失效」合併成同一種「需要連接」的提示，第一次查詢回來前顯示載入中的占位畫面；頁面自動查詢行事曆的結果只顯示在卡片上，不再跳 toast，toast 只留給使用者的操作。帳號設定的按鈕文字改成只看現在有沒有連上，排程頁的「尚未連接」提示改成指向帳號設定。

## 背景
- 首頁卡片 `frontend/components/dashboard/GoogleCalendarEmbed.vue` 現在有五種內容，依序檢查、第一個成立的就顯示：正在連接（`connecting`）、暫時無法載入（`unavailable`）、行事曆 iframe（`connect`）、「Google Calendar 授權已失效，請重新連接。」（`needsReconnect`）、「尚未連接 Google Calendar，請前往 **帳號設定** 以完成連接。」。卡片只在 `frontend/components/dashboard/Dashboard.vue` 使用。
- 「從沒連接過」和「授權失效」要做的事一樣，都是到帳號設定按按鈕、到 Google 授權頁同意，但卡片顯示兩段不同的文字，而且「授權已失效」的提示沒有告訴使用者要去哪裡操作。
- 狀態來源 `frontend/composables/useGoogleCalendar.ts`：
  - 每次都同時設定 `isConnected` 和 `needsReconnect`，兩者不會同時為 true（第 102-103、120-121、129-130 行）。從沒連接過與授權失效時，`isConnected` 都是 false。
  - `unavailable` 有兩條設定的路徑，規則不同：授權狀態檢查（`/oauth/status`）本身失敗時，沒有已知的結果才設成 true，有已知的結果就維持原本的畫面（第 82 行）；抓行事曆清單遇到暫時性錯誤時，最近一次已知的結果不是載入成功就設成 true，是載入成功就繼續顯示原本的行事曆（第 131 行）。
  - 最近一次已知的結果存在 `knownResult`（`'loaded' | 'not_linked' | 'reauth' | null`，第 29 行），換使用者或登出時清成 null（第 32-46 行）。
  - 自動查詢遇到授權失效時跳授權失效的 toast（第 124 行），遇到暫時性錯誤（含限流）時跳「Google Calendar 資料暫時無法取得」或「請求太頻繁」的 toast（第 132-138 行）。
- 自動查詢的時機：首頁登入後與連接成功後（`Dashboard.vue`），以及 header 的帳號設定掛載時（`frontend/components/header/AccountSettings.vue`，由 `AppHeader.vue:65` 放在每一頁）。所以授權失效的 toast 現在每一頁都會跳，首頁還同時有卡片的文字。
- 第一次查詢回來前，`isConnected`、`unavailable` 都是 false，卡片落到最後的「尚未連接」，查詢回來才換成正確的內容。
- 使用者操作時的 toast 在別的檔案：產生排程建議、確認排程（`frontend/composables/useSchedule.ts:58,94,124`）、刪除任務（`frontend/composables/useTaskForm.ts:180`），都用 `useGoogleCalendarAuth` 的 `reauthToast`。
- 帳號設定 `AccountSettings.vue:221` 的按鈕現在是 `googleCalendarConnected || googleNeedsReconnect ? '重新連接 Google Calendar' : '連接 Google Calendar'`，旁邊在已連接時顯示「已連接」標記。
- 排程頁 `frontend/components/tasks/ScheduleSuggestion.vue:75` 在沒連接過時（`notLinked`）顯示「尚未連接 Google Calendar，請先在右側卡片完成連接」。右側的行事曆卡片本身沒辦法連接，實際上要去帳號設定。授權失效時這個畫面顯示 toast，不顯示這段文字。載入中用 `USkeleton` 灰色方塊（第 67-69 行）。
- 這份規格取代兩份已核准規格的一部分：
  - [google-calendar-reauth.md](google-calendar-reauth.md)：AC1 的首頁 toast 與卡片文字（「首頁只跳一個 toast…」「行事曆卡片顯示『授權已失效，請重新連接』」），以及 AC3、AC4 裡前端自動查詢跳 toast 的部分（AC3「前端在這些暫時性錯誤時仍顯示『稍後再試』，而且只跳一個 toast」、AC4「失敗時最多跳一個 toast」）。AC1 的 toast 按鈕規則仍適用於使用者操作時的 toast；AC3 的後端規則、AC4 共用同一個請求的規則不變。
  - [issue-77-error-codes.md](issue-77-error-codes.md)：
    - AC1(1) 行事曆「限流時顯示『請求太頻繁，請稍後再試』」的部分：原本由頁面自動查詢（首頁與帳號設定）的 toast 顯示（需求 7，`issue-77-error-codes.md:103,113`）。
    - AC1(2) 的「卡片顯示『授權已失效』並提示重新連結，帳號設定的按鈕是『重新連接 Google Calendar』」。
    - AC12 用在行事曆自動查詢（`useGoogleCalendar`）的「`REAUTH_REQUIRED` 提示重新連結」與「兩種限流顯示稍後再試」。
    - AC1 的其他規則（不顯示「尚未連接」、帳號設定維持「已連接」、保留載入成功的清單、排程建議頁的限流提示）與 AC12 用在其他畫面的部分不變。
- 原本的 #26 擔心 `connect` 和 `needsReconnect` 同時為 true 時卡片顯示錯誤，查證後兩者不會同時為 true，#26 已關閉。它指出的測試（`frontend/tests/components/GoogleCalendarEmbed.test.ts:53-61`，名稱寫「即使 needsReconnect 還沒更新」，傳入的卻是 `needsReconnect: false`）在這份規格裡處理。

## 需求
1. 首頁卡片有四種狀態：正在連接、已連接（顯示行事曆）、暫時無法載入、需要連接。
2. 「需要連接」涵蓋從沒連接過，以及 token 失效兩種情況。
3. 「需要連接」的文字是「Google Calendar 未連接或授權已失效，請前往 **帳號設定** 連接。」，其中「帳號設定」用粗體，和現在「尚未連接」提示的寫法一樣。
4. 正在連接、暫時無法載入、已連接三種狀態的判斷與顯示不變。
5. 這個使用者第一次查詢還沒有結果時，卡片顯示載入中的灰色方塊（`USkeleton`，和排程建議卡片載入時一樣），沒有文字。這是等結果時的占位畫面，不算第五種狀態。
6. 頁面自動查詢行事曆（首頁、帳號設定掛載時、連接成功後重新查詢）遇到授權失效時，不跳 toast。
7. 頁面自動查詢行事曆遇到暫時性錯誤（含限流）時，不跳 toast。
8. 使用者操作時（產生排程建議、確認排程、刪除任務）遇到授權失效，toast 維持不變：標題「Google Calendar 授權已失效」，按鈕「重新連接 Google Calendar」。
9. 帳號設定的按鈕文字只看現在有沒有連上：沒連上顯示「連接 Google Calendar」，已連接顯示「重新連接 Google Calendar」。
10. 「已連接」標記的顯示規則不變。
11. 排程頁沒連接過時的提示改成「尚未連接 Google Calendar，請前往 **帳號設定** 連接。」，其中「帳號設定」用粗體。

## 不做
- `useGoogleCalendar` 判斷已連接、暫時無法載入、最近一次已知的結果的邏輯不變；只拿掉 toast，並多提供「第一次查詢還沒有結果」的狀態。
- 使用者操作時的其他 toast（排程、任務儲存與刪除的成功或失敗）不變。
- 前一個使用者的查詢還沒結束時就換成另一個使用者，新使用者會沿用那次查詢、看到前一個使用者的結果（`useGoogleCalendar.ts:146,150` 只比較連接次數，不比較使用者）。這是既有的問題，牽涉使用者之間的資料隔離，另開 issue 處理：#105（和 #81 一起看）。
- 授權失效的使用者不是從首頁進來時（例如直接打開任務頁），不另外提示；使用者操作時會看到授權失效的 toast，帳號設定的按鈕也會是「連接 Google Calendar」。

## 驗收條件
| # | 條件 |
|---|---|
| AC1 | 已登入、從沒連接過 Google Calendar 的使用者打開首頁，查詢完成後，行事曆卡片顯示「Google Calendar 未連接或授權已失效，請前往 **帳號設定** 連接。」，沒有行事曆 iframe |
| AC2 | 已登入、Google 授權失效（後端回 `REAUTH_REQUIRED`）的使用者打開首頁，行事曆卡片顯示和 AC1 相同的文字，沒有行事曆 iframe |
| AC3 | 沒連上時，卡片上不再出現舊文字裡的「尚未連接」與「請重新連接。」（這兩個片段只出現在舊文字，新文字沒有） |
| AC4 | 正在完成 Google 授權時，卡片顯示「正在連接 Google Calendar，請稍候…」，和現在一樣 |
| AC5 | 沒有已知的結果（例如從沒載入成功過），又遇到系統或 Google 的暫時性問題時，卡片顯示「Google 行事曆暫時無法載入，請稍後再試」，和現在一樣 |
| AC6 | 已連接時，卡片顯示行事曆 iframe，不顯示需要連接的文字 |
| AC7 | 已登入的使用者打開首頁，不是正在完成 Google 授權，而且第一次查詢還沒回來時，卡片顯示載入中的灰色方塊，不顯示需要連接、暫時無法載入的文字，也沒有 iframe |
| AC8 | 前一個使用者的查詢已經結束的情況下，換成另一個使用者登入後，新使用者第一次查詢回來前，卡片顯示載入中的灰色方塊，不顯示前一個使用者的行事曆 |
| AC9 | 頁面自動查詢遇到授權失效時，不跳任何 toast |
| AC10 | 頁面自動查詢遇到暫時性錯誤（Google 5xx、限流、伺服器錯誤）時，不跳任何 toast |
| AC11 | 產生排程建議、確認排程、刪除任務時遇到授權失效，跳出的 toast 標題仍是「Google Calendar 授權已失效」，按鈕仍是「重新連接 Google Calendar」 |
| AC12 | 帳號設定裡，從沒連接過、或授權失效的使用者看到的按鈕是「連接 Google Calendar」，沒有「已連接」標記 |
| AC13 | 帳號設定裡，已連接的使用者看到的按鈕是「重新連接 Google Calendar」，旁邊有「已連接」標記 |
| AC14 | 排程頁產生排程建議時，如果使用者從沒連接過 Google Calendar，顯示「尚未連接 Google Calendar，請前往 **帳號設定** 連接。」 |
| AC15 | Google 授權完成（「正在連接」結束）後、重新查詢回來前，卡片顯示載入中的灰色方塊，不顯示需要連接的文字 |

## 不適用的情境
| 情境 | 原因 |
|---|---|
| 未登入 | 首頁未登入時顯示登入提示卡片，不顯示行事曆卡片，這次沒有改到 |
| 空資料 | 已連接但沒有任何行事曆時照常嵌入 iframe，這次沒有改到這條路徑 |
| 資料處理、安全性、權限 | 只改畫面文字、提示方式與顯示條件，不改 API、資料、授權判斷 |

## 實作計畫
1. `useGoogleCalendar.ts`：
   - 拿掉自動查詢時的兩個 toast（授權失效與暫時性錯誤），`useToast`、`reauthToast` 不再在這裡使用。錯誤照常 `logApiError`。
   - 拿掉 `needsReconnect`：拿掉 toast 以後沒有任何元件需要它；授權失效與未連接的區分仍由 `knownResult` 負責。
   - 新增一個對外的狀態，表示「這個使用者第一次查詢還沒有結果」：換使用者或登出時（`resetKnownResult`）回到「還沒有結果」；查詢得到任何結果（已連接、未連接、授權失效、暫時無法載入；`getToken` 失敗走暫時性錯誤的分支，也算暫時無法載入）後變成「有結果」。Clerk 還沒載入完就直接 return、或結果不是最新而被丟掉時，維持「還沒有結果」，所以不要在 `finally` 設定。之後重新查詢時不回到「還沒有結果」，畫面維持最近一次已知的結果；唯一的例外是連接成功（`connectedCount` 遞增）時回到「還沒有結果」，等授權完成後的重新查詢回來才顯示結果（AC15）。這時如果 `/oauth/status` 失敗而維持最近一次已知的結果（第 82 行），也算有結果：灰色方塊結束，卡片顯示最近一次已知的結果。`knownResult` 不是 reactive，所以要另外用 ref 表示。
   - 更新已經不成立的註解：第 19 行（「卡片不能顯示成『尚未連接』」）隨 `needsReconnect` 拿掉；第 141 行說共用請求是為了「失敗時才不會跳兩個 toast」，改成為了不重複發請求。
2. `GoogleCalendarEmbed.vue`：
   - 拿掉 `needsReconnect` prop 與它的分支，最後的 `v-else` 改成需求 3 的文字。
   - 新增 prop 表示第一次查詢還沒有結果，排在 `connecting` 之後、`unavailable` 之前，顯示 `USkeleton`。判斷順序：`connecting` → 載入中 → `unavailable` → `connect` → 需要連接。正在連接排在載入中前面，因為連接完成前查詢不會有新結果。
3. `Dashboard.vue`：不再傳 `needs-reconnect`，改傳載入中的狀態給卡片。
4. `AccountSettings.vue`：按鈕文字改成 `googleCalendarConnected ? '重新連接 Google Calendar' : '連接 Google Calendar'`，不再取出 `needsReconnect`。
5. `ScheduleSuggestion.vue`：`notLinked` 的提示改成需求 11 的文字。
6. 測試：
   - `useGoogleCalendar.test.ts`：原本斷言「跳 toast」的測試改成斷言不跳 toast（授權失效、暫時性錯誤、限流、共用請求時）；原本斷言 `needsReconnect` 的地方改成斷言 `isConnected` 為 false，以及之後狀態檢查失敗時維持需要連接的畫面（`unavailable` 為 false）；新增「第一次查詢前是還沒有結果、查詢後變成有結果、換使用者後回到還沒有結果、重新查詢時不回到還沒有結果、`connectedCount` 遞增時回到還沒有結果」。
   - `GoogleCalendarEmbed.test.ts`：`connect=false` 的測試改成檢查新文字，並檢查「尚未連接」「請重新連接。」都不出現；原本 AC1（`needsReconnect=true`）的測試刪掉，因為 prop 已移除；原本名稱不符的 AC6 測試重寫成「`connect=true` 時有 iframe，不顯示需要連接的文字」，名稱和內容一致；新增載入中的測試（有灰色方塊、沒有需要連接與暫時無法載入的文字、沒有 iframe）。
   - `Dashboard.test.ts`：這個檔案把卡片 stub 掉、只測頁面本身的邏輯，所以「卡片收到 needsReconnect」的測試改成：卡片收到 `connect=false`，卡片的 props 與 attribute 都沒有 `needsReconnect`／`needs-reconnect`（拿掉 prop 以後只看 props 一定是 undefined，驗不出 Dashboard 有沒有停止傳入）；新增「載入中的狀態傳給卡片」。卡片顯示什麼文字由 `GoogleCalendarEmbed.test.ts` 負責。`Dashboard.sync.test.ts` 的 mock 裡的 `needsReconnect` 一併拿掉。
   - `AccountSettings.test.ts`：mock 拿掉 `needsReconnect`；原本「授權已失效 → 重新連接」的測試改成「沒連上 → 連接 Google Calendar、沒有已連接標記」；新增「已連接 → 重新連接 Google Calendar」的斷言。
   - `ScheduleSuggestion.test.ts`：檢查新文字，而且不再出現「右側卡片」。
7. 把 [google-calendar-reauth.md](google-calendar-reauth.md) 的「狀態」改成「部分被 [issue-104-calendar-card-states.md](issue-104-calendar-card-states.md) 取代（AC1、AC3、AC4）」，[issue-77-error-codes.md](issue-77-error-codes.md) 的「狀態」改成「部分被 [issue-104-calendar-card-states.md](issue-104-calendar-card-states.md) 取代（AC1、AC12）」，其他內容不改。測試名稱裡指向這兩份規格、而且行為被這份規格改掉的 AC 編號（例如 `AccountSettings.test.ts` 的「AC1(2)」、`useGoogleCalendar.test.ts` 跳 toast 的「AC1」「AC3」「AC4」），重寫時改成這份規格的 AC 編號。

## 測試對應
| AC | 測試 |
|---|---|
| AC1 | `frontend/tests/components/GoogleCalendarEmbed.test.ts`：`connect=false` 時顯示需要連接的文字、沒有 iframe |
| AC2 | `frontend/tests/composables/useGoogleCalendar.test.ts`：`REAUTH_REQUIRED` → `isConnected` 為 false、`unavailable` 為 false、有結果；`frontend/tests/components/Dashboard.test.ts`：卡片收到 `connect=false`，props 與 attribute 都沒有 `needsReconnect`／`needs-reconnect`；顯示的文字由 AC1 的測試涵蓋 |
| AC3 | `GoogleCalendarEmbed.test.ts`：`connect=false` 時「尚未連接」「請重新連接。」都不出現 |
| AC4 | `GoogleCalendarEmbed.test.ts` 既有的 `connecting=true` 測試維持通過 |
| AC5 | `GoogleCalendarEmbed.test.ts` 既有的 `unavailable` 測試維持通過；`useGoogleCalendar.test.ts` 既有的狀態檢查失敗、抓清單失敗測試維持通過（只改 toast 的斷言） |
| AC6 | `GoogleCalendarEmbed.test.ts`：重寫原本名稱不符的測試，`connect=true` 時有 iframe、不顯示需要連接的文字 |
| AC7 | `useGoogleCalendar.test.ts`：第一次查詢前是還沒有結果，查詢後（已連接、未連接、授權失效、暫時無法載入）變成有結果，之後重新查詢不回到還沒有結果；Clerk 還沒載入完、結果不是最新而被丟掉時維持還沒有結果；`GoogleCalendarEmbed.test.ts`：載入中顯示灰色方塊、沒有文字與 iframe，正在連接和載入中同時成立時顯示「正在連接」；`Dashboard.test.ts`：載入中的狀態傳給卡片 |
| AC8 | `useGoogleCalendar.test.ts`：前一個使用者的查詢結束後換成另一個使用者，回到還沒有結果、行事曆清單清空 |
| AC9 | `useGoogleCalendar.test.ts`：授權失效時 `toast.add` 沒有被呼叫（包括首頁和帳號設定同時查詢） |
| AC10 | `useGoogleCalendar.test.ts`：Google 5xx、限流、伺服器錯誤時 `toast.add` 沒有被呼叫 |
| AC11 | `useSchedule.test.ts`、`useTaskForm.test.ts` 既有的授權失效 toast 測試維持通過 |
| AC12 | `frontend/tests/components/AccountSettings.test.ts`：`isConnected` 為 false → 按鈕「連接 Google Calendar」、不含「重新連接」、沒有標記 |
| AC13 | `AccountSettings.test.ts`：`isConnected` 為 true → 按鈕「重新連接 Google Calendar」、有「已連接」標記 |
| AC14 | `frontend/tests/components/ScheduleSuggestion.test.ts`：`notLinked` 時顯示新文字、不含「右側卡片」 |
| AC15 | `useGoogleCalendar.test.ts`：已有結果（未連接或授權失效）後 `connectedCount` 遞增，回到還沒有結果；重新查詢成功後變成有結果、`isConnected` 為 true；重新查詢時 `/oauth/status` 失敗，也變成有結果，維持最近一次已知的結果（`isConnected` 為 false、`unavailable` 為 false） |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定
無
