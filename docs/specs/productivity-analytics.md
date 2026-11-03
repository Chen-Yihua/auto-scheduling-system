# 工作效率分析頁面

- 狀態：已核准
- PR：#10

## 背景

使用者想用圖表和數字看自己的工作效率。原本系統沒有記錄任務何時完成：手動任務只有任何修改都會更新的 `updated`，外部項目的手動完成標記 `done` 只是布林值，算不出時間趨勢。開發者選定：新增完成時間並顯示趨勢。

## 需求

1. 記錄完成時間 `completed_at`：手動任務與外部項目（GitHub / Jira / Moodle）標記完成時寫入，取消完成時清掉；GitHub / Jira 由平台關閉的項目改用平台提供的關閉時間。
2. 新增 API `GET /analytics/productivity?timezone=<IANA>`，回傳彙總好的統計數字與統計產生時間；沒帶 `timezone` 時預設用 UTC。統計一律讀資料庫，不即時向外部平台抓資料。
3. 新增頁面 `/productivity`：數字卡片＋圖表；header 加入口按鈕。頁面上沒有任何按鈕，開著時每小時自動更新一次。
4. 頁面區分「載入中」「無資料」「載入失敗」三種狀態：資料庫沒有任何可統計的資料是「無資料」，不是錯誤；只有網路或 API 失敗才是「載入失敗」。
5. GitHub / Jira 回傳的所有時間欄位，先統一轉成 UTC datetime 再存進資料庫。

## 不做

- 不記錄實際花費的時間（只用預估的 `duration`）。
- 不回填既有已完成任務的完成時間；不可調整統計區間（固定近 8 週）。
- 不新增圖表套件（用 SVG / Tailwind 自己畫）。
- 不改排程演算法、不改 `SchedulableTaskOut` / `/schedule/tasks` 的回應。
- 不做外部平台定時同步（#13）、全站後端錯誤的 Discord 通知（#14）、部署搬到 Cloudflare（#15），各自另開功能。
- 資料庫裡已存成字串的舊時間不另外轉換，下次同步成功時由新格式覆蓋。

## 假設

1. 統計對象與排程精靈同一份清單（`get_all_schedulable_items`：手動任務＋三個外部平台）。
2. 「完成」沿用現有定義：手動任務 `status == "Done"`；外部項目「平台回報完成或使用者手動標記」任一成立。`In Progress` 算未完成。
3. 外部項目的完成時間：平台判定完成時優先用平台時間（GitHub `closed_at`、Jira `resolutiondate`）；平台沒給或只是使用者手動標記時，用標記當下的時間。Moodle 只有手動標記。
4. 手動任務的狀態轉換：非 Done 變 Done → 寫入現在時間；Done → Done 保留原時間；變回非 Done → 清成 null；更新時沒帶 status 不動它。直接以 Done 建立的任務，完成時間＝建立時間。
5. 既有已完成任務沒有完成時間：計入完成率等現況統計，但不計入週趨勢與準時率；回應另給 `untracked_done`，頁面上說明。
6. 週依瀏覽器時區切分，週一 00:00 起算，含本週共 8 週。
7. 逾期：未完成、有截止日、截止日早於現在。
8. 準時完成率：近 8 週內完成、且有截止日的項目中，`completed_at <= due_date` 的比例；分母為 0 時回 null（頁面顯示「—」）。截止日在任務表單與排程精靈都帶時間，不會有「當天完成算遲交」的問題。
9. 預估工時用 `duration`（分鐘）加總；沒有 duration 的項目不計入，另外回「未完成且未估時」的數量。
10. 完成率＝已完成 / 全部；沒有任何項目時回 null。
11. 入口放在 header（圖示按鈕，訪客也看得到，進去顯示 LoginRequiredCard）。
12. 自動更新只在頁面開著時進行，離開頁面就停止；載入失敗後也等下一次（一小時後）自動更新才重試。
13. 統計時間以瀏覽器當地時間顯示，格式 `YYYY/MM/DD HH:mm`。
14. 平台時間欄位缺值時存成 null（Jira 原本存空字串）；前端遇到 null 不顯示「更新於」。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 手動任務從非 Done 改成 Done（`PUT /manual-tasks/{id}` 或 `PATCH /schedule/tasks/done`），系統要寫入當下時間為 `completed_at` |
| AC2 | 手動任務已是 Done 再次設為 Done，或更新時沒帶 status，`completed_at` 要維持原值 |
| AC3 | 手動任務從 Done 改回非 Done，`completed_at` 要清成 null |
| AC4 | 以 status=Done 建立手動任務，`completed_at` 要等於建立時間 |
| AC5 | 外部項目以 `PATCH /schedule/tasks/done` 標記完成要寫入 `completed_at`，取消完成要清掉；之後重新同步平台資料不會覆蓋它 |
| AC6 | GitHub 已關閉的項目，完成時間要用 `closed_at`；Jira 完成的項目要用 `resolutiondate`（API 請求要帶這個欄位） |
| AC7 | `GET /analytics/productivity` 要回傳：總數、完成數、完成率、逾期數、已完成 / 剩餘預估工時、未估時數、依來源與依優先度的總數 / 完成數 |
| AC8 | 週趨勢要依傳入時區分成含本週的 8 週（週一起算），每週回完成數與完成的預估工時；跨時區邊界的完成時間要落在當地時間的那一週；8 週前的完成不列入 |
| AC9 | 準時完成率依假設 8 計算，分母為 0 回 null；沒有任何項目時完成率回 null |
| AC10 | 已完成但沒有完成時間的項目計入 `untracked_done`，不計入週趨勢與準時率 |
| AC11 | 時區不合法時回 400 並帶錯誤訊息；未登入回 403 |
| AC12 | `/productivity` 頁面登入後顯示數字卡片（完成率、逾期、剩餘工時、準時率）、近 8 週完成數長條圖、依來源 / 優先度的完成進度；rate 為 null 顯示「—」 |
| AC13 | 資料庫沒有任何可統計的項目（`total == 0`）時，頁面顯示「目前沒有可統計的資料」，不顯示錯誤狀態；`untracked_done > 0` 時顯示未列入趨勢的說明；未登入顯示 LoginRequiredCard |
| AC14 | API 失敗時頁面以 toast 顯示錯誤訊息（沿用 `getFriendlyErrorTitle`） |
| AC15 | API 失敗（網路錯誤或非 2xx 回應）且還沒有任何統計資料時，頁面要顯示錯誤狀態「統計資料載入失敗，系統會在下次自動更新時重試，請稍候」，不能只留空白，也沒有任何按鈕；之後的自動更新成功時，改為顯示統計、錯誤狀態消失 |
| AC16 | 還沒有統計資料、API 載入中時，頁面顯示「統計資料載入中，請稍候…」，不顯示錯誤狀態或無資料狀態 |
| AC17 | 頁面開著時每小時自動重新呼叫 API；已有統計時更新失敗，畫面維持原本的統計（並依 AC14 跳 toast）；離開頁面後停止自動更新 |
| AC18 | API 回應包含統計產生時間 `generated_at`（UTC）；頁面顯示「統計時間：YYYY/MM/DD HH:mm」（瀏覽器當地時間），每次自動更新成功後跟著更新 |
| AC19 | GitHub 的 `created_at`、`updated_at`、`closed_at` 與 Jira 的 `updated_at`、`resolved_at`，同步時一律轉成 UTC datetime 存入資料庫，缺值存 null；讀取時仍接受資料庫裡舊的字串格式，直到下次同步覆蓋 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 權限（看到別人的統計） | 統計只讀登入者自己的項目（`clerk_user["sub"]`），沒有分享或管理員檢視的需求 |
| 資料處理（刪除、匯出） | 只新增 `completed_at` 欄位與唯讀統計，不刪除或匯出資料 |
| 安全性（竄改統計） | `completed_at` 不在 `ManualTaskUpdate` 裡，client 不能直接寫入，只能透過狀態改變由後端寫入 |

## 實作計畫

**後端**

| 檔案 | 改動 |
|---|---|
| `schemas/manual_task.py` | `ManualTaskOut` 加 `completed_at`（`ManualTaskUpdate` 不加） |
| `crud/manual_task.py` | `completed_at_after_status_change`（假設 4 的規則）；`create_manual_task` 回傳 `completed_at` |
| `routers/manual_task.py` | create：status 為 Done 時 `completed_at=now`；update：有帶 status 時用上面的 helper |
| `crud/schedulable_items.py` | `set_done` 寫入 / 保留 / 清除 `completed_at`；`_normalize_external` 依假設 3 算出 `completed_at` |
| `platforms/base.py`、`github.py`、`jira.py`、`schemas/github.py`、`schemas/jira.py` | `PlatformAdapter.completed_at`；GitHub `closed_at`、Jira `resolutiondate` / `resolved_at` |
| `services/productivity.py` | `build_productivity_summary(items, now, tz_name)`：所有統計規則；回傳 `generated_at` |
| `schemas/analytics.py`、`routers/analytics.py`、`main.py` | `GET /analytics/productivity`；時區不合法丟 `InvalidRequestError`；`ProductivitySummary` 加 `generated_at` |
| `platforms/github.py`、`platforms/jira.py`、`schemas/jira.py` | transform 時把所有時間欄位轉成 UTC datetime（缺值 None）；`completed_at` 同時接受 datetime 與舊的字串；`JiraIssue.updated_at` 改為 `Optional[datetime]` |

**前端**

| 檔案 | 改動 |
|---|---|
| `types/analytics.ts`、`types/manualTask.ts`、`types/github.ts`、`types/jira.ts` | 對應後端回應格式（`generated_at`；Jira `updated_at` 可為 null） |
| `composables/useProductivity.ts` | 帶 JWT 與瀏覽器時區呼叫 API；`loading` / `summary` / `error`；每小時自動更新，頁面卸載時停止 |
| `components/productivity/WeeklyBarChart.vue`、`ProgressList.vue` | SVG 直條圖、水平進度條 |
| `pages/productivity.vue` | 數字卡片、圖表、統計時間、載入中 / 無資料 / 載入失敗狀態（移除重試按鈕）、未列入趨勢說明、LoginRequiredCard |
| `components/platforms/JiraIssuesList.vue` | `updated_at` 為 null 時不顯示「更新於」 |
| `components/header/AppHeader.vue` | 入口按鈕 |
| `utils/labels.ts`、`utils/format.ts` | 來源中文對照；百分比與工時格式 |

**文件**：`docs/api.md` 加入新 endpoint；`docs/architecture.md` 補上工作效率統計與 `completed_at`。

## 測試對應

| AC | 測試 |
|---|---|
| AC1–AC3 | `backend/tests/unit/test_manual_task_crud.py`、`test_manual_task_router.py`、`test_schedulable_items.py` |
| AC4 | `backend/tests/unit/test_manual_task_router.py` |
| AC5 | `backend/tests/unit/test_schedulable_items.py` |
| AC6 | `backend/tests/unit/test_github_platform.py`、`test_jira_platform.py`、`test_schedulable_items.py` |
| AC7–AC10 | `backend/tests/unit/test_productivity.py` |
| AC11 | `backend/tests/integration/test_analytics_api.py` |
| AC1＋AC7 串接 | `backend/tests/integration/test_analytics_scenario.py` |
| AC12–AC13 | `frontend/tests/pages/productivity.test.ts`、`tests/components/WeeklyBarChart.test.ts`、`tests/utils/format.test.ts` |
| AC14 | `frontend/tests/composables/useProductivity.test.ts` |
| AC15–AC17 | `frontend/tests/composables/useProductivity.test.ts`、`frontend/tests/pages/productivity.test.ts` |
| AC18 | `backend/tests/unit/test_productivity.py`、`backend/tests/integration/test_analytics_api.py`、`frontend/tests/pages/productivity.test.ts` |
| AC19 | `backend/tests/unit/test_github_platform.py`、`test_jira_platform.py`、`test_schedulable_items.py`；`frontend/tests/components/JiraIssuesList.test.ts` |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-02 | 新增 AC15 | 驗收時發現的缺漏：原本只規定失敗時跳 toast，toast 消失後頁面空白、沒有重試方式；開發者決定在 PR #10 補上 | 開發者 |
| 2026-11-02 | AC11 由「未登入回 401」改為「未登入被擋（401/403）」 | 驗收時發現：專案現有的 Clerk 驗證未登入一律回 403，原條件與既有行為衝突 | 未確認（Claude 提出並告知開發者） |
| 2026-11-03 | AC11 由「未登入被擋（401/403）」改為「未登入回 403」 | 開發者確認未登入一律是 403 | 開發者（2026-11-03） |
| 2026-11-03 | 規格由本機計畫檔移入 `docs/specs/` | 依 ADR 0002 | 開發者 |
| 2026-11-03 | 需求 2 補上 `timezone` 預設 UTC | 審查發現規格與 `docs/api.md` 不一致 | 開發者（2026-11-03） |
| 2026-11-03 | 新增 AC16（載入中狀態） | 審查發現的缺漏 | 開發者（2026-11-03） |
| 2026-11-03 | AC13 改為「無資料」不算錯誤；AC15 移除重試按鈕、改為等待自動更新；新增 AC17（每小時自動更新） | 開發者要求頁面沒有按鈕、定時更新，並區分無資料與載入失敗 | 開發者（2026-11-03） |
| 2026-11-03 | 新增 AC18（統計產生時間） | 開發者要求顯示統計時間，選擇「統計產生時間」 | 開發者（2026-11-03） |
| 2026-11-03 | 新增 AC19（GitHub / Jira 時間統一格式） | 開發者要求時間先統一格式再存資料庫，範圍為所有時間欄位，舊資料等下次同步覆蓋 | 開發者（2026-11-03） |
