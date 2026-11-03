# 工作效率分析頁面：審查第 2 輪

- 規格：[docs/specs/productivity-analytics.md](../specs/productivity-analytics.md)
- PR：#10
- 日期：2026-11-03
- 審查的版本：`6e1c70f`（第 1 輪的修正：`c4718ab`、`a75c6ac`、`6e1c70f`）
- 結果：**沒有新的阻擋項目**（第 1 輪的 Missing AC「載入中」還在等開發者決定）

## 審查報告

> 依 `acceptance-reviewer` 的報告整理：每一項的結論、分類、阻擋判定與依據都保留，敘述有精簡。（本輪在存檔規則建立前完成，事後補檔。）

**結論：除了待開發者決定的項目（Missing AC「載入中狀態」、Improvement Suggestion 第 6–9 項），沒有其他阻擋項目。** 上一輪 4 個 Test Gap（AC9、AC12、AC14、AC15）和 AC11 都已解決。這一輪的錯誤實作都會被測試擋下。

**有一件事和指示不同：沒有跑 `git pull`。** 審查角色只能跑唯讀的 git 指令，`git pull` 會改寫工作目錄，所以改跑 `git fetch`。本機 HEAD 和 `origin/feat/productivity-analytics` 一樣，不需要 pull。

**檢查結果**
- 後端：pytest 491 passed，pyright 0 errors。
- 前端：lint、typecheck 通過，vitest 29 個檔案、253 個測試全部通過。

**修正有沒有解決問題**：有。**有沒有改到程式**：沒有，只動到 4 個測試檔和規格檔。**AC11、修改紀錄、測試三者是否一致**：一致（規格寫「未登入回 403」、修改紀錄記「401 → 403」、測試只接受 `== 403`、`docs/api.md` 也寫 403）。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1–AC8 | 通過（沿用第 1 輪；這輪沒改程式，測試全過） | `backend/tests/unit/test_manual_task_*.py`、`test_schedulable_items.py`、`test_*_platform.py`、`test_productivity.py` |
| AC9 | 通過 | `backend/tests/unit/test_productivity.py:127-143`：新增一筆 2026-09-13 完成、有截止日的項目。如果實作不限 8 週，結果會變成 4 個中 3 個準時，測試會擋下 |
| AC10 | 通過 | `backend/tests/unit/test_productivity.py:146-155` |
| AC11 | 通過 | `backend/tests/integration/test_analytics_api.py:35-41`（400＋錯誤訊息）、`:44-50`（只接受 403） |
| AC12 | 通過 | `frontend/tests/pages/productivity.test.ts:79-90`（中文標籤和「1 / 4」）、`:92-99`（真的 `WeeklyBarChart`，檢查 `svg[role="img"]` 和柱頂數值） |
| AC13 | 通過（沿用第 1 輪） | `frontend/tests/pages/productivity.test.ts:101-125` |
| AC14 | 通過 | `frontend/tests/composables/useProductivity.test.ts:62-71`：429 時 toast 標題必須是「請求太頻繁，請稍後再試」 |
| AC15 | 通過 | `frontend/tests/pages/productivity.test.ts:127-149`：檢查按鈕文字是「重試」、按下後重新呼叫 API、成功後錯誤狀態消失 |

### 發現

| # | 分類 | 阻擋 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|
| — | Missing Acceptance Criteria | 待開發者決定 | 載入中狀態（第 1 輪 #5） | `frontend/pages/productivity.vue:53` | — |
| — | Improvement Suggestion | 待開發者決定 | 第 1 輪 #6–#9 | — | — |
| 1 | Test Gap | 否 | AC9「分母為 0 回 null」只用空清單測過。要逃過測試，實作得把「清單是空的」另外寫成特例，不是自然會犯的錯，所以判為不阻擋。 | `backend/tests/unit/test_productivity.py:21-27`、`:146-155` | 在 untracked 測試補一行 `assert summary["on_time"]["rate"] is None` |
| 2 | Improvement Suggestion | 否 | AC12 進度測試的假資料中，來源、優先度、整體的數字都是 1 / 4。實作誤把整體數字塞進每一列，測試分不出來。 | `frontend/tests/pages/productivity.test.ts:41-50`、`:79-90` | 把 by_source、by_priority 改成和整體不同的數字 |
| 3 | Improvement Suggestion | 否 | 修改紀錄刪掉了「401 → 401/403（待開發者確認）」那一列，中間那次修改的紀錄不見了。`docs/specs/README.md` 要求任何修改都要記錄。 | `docs/specs/productivity-analytics.md` 修改紀錄 | 保留原本那一列，再加一列確認紀錄 |

## 處理結果

| # | 處理 | 決定者 | commit / 連結 |
|---|---|---|---|
| 1、2 | 未處理（不阻擋，開發者未要求） | — | — |
| 3 | 補回中間那筆修改紀錄，另記一筆開發者確認 | 主 session（違反既有規則，直接修正） | `01345e2` |
