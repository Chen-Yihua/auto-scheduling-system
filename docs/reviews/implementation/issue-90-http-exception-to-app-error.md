# API 錯誤回應第三階段：實作審查紀錄

- 規格：[docs/specs/issue-90-http-exception-to-app-error.md](../../specs/issue-90-http-exception-to-app-error.md)
- PR：#91
- 等級：一般
- 輪數：1（2026-11-13 `0602ce8`）
- 最終結果：沒有阻擋

## 摘要

- 發現：2 項：Test Gap 1、Improvement Suggestion 1；Minor 1、Info 1
- 開發者決策：1 項（#2）
- 尚未處理：無

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-13 `0602ce8` | #1–#2（無） | AC1–AC7 通過；`pyright` 0 errors、`pytest` 1030 passed；implementer 把 `test_manual_task_api.py` 3 個 mock 換成 crud 實際丟的 `NotFoundError`，符合實作計畫第 4 點；#1 開 issue；開發者決定 #2 在這個 PR 處理 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `get_current_clerk_user` 有 credentials 但沒有解出 payload 的分支沒有測試 | Test Gap | Minor | 否 | 否 | — | 開 issue（`main` 上原本就有的缺口；真實請求走不到這個分支） | 主 session | [#92](https://github.com/Chen-Yihua/auto-scheduling-system/issues/92) |
| 2 | 1 | 兩個 integration 測試檔留著沒用到的 `HTTPException` import | Improvement Suggestion | Info | 否 | 否 | — | 開發者決定在這個 PR 處理：規格需求 7、AC8，記進修改紀錄；原本開的 #93 關閉 | 開發者 | 交給 implementer 修正 |

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 2 | 沒用到的 `HTTPException` import 要開 issue 還是在這個 PR 刪 | 在這個 PR 刪／維持 issue | 在這個 PR 刪 | 只刪兩行死碼、不改行為，開 issue 成本比修正高 |
