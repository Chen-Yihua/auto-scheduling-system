# API 錯誤回應第一階段：實作審查紀錄

- 規格：[docs/specs/issue-77-error-codes.md](../../specs/issue-77-error-codes.md)
- PR：#79
- 等級：高風險
- 輪數：1（第 1 輪 2026-11-10 `441ccc6`）
- 最終結果：仍有阻擋（#1，交回實作修正）

## 摘要

- 發現：2 項：Implementation Defect 1、Improvement Suggestion 1；Major 1、Info 1
- 開發者決策：0 項
- 尚未處理：1 項（#1）

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-10 `441ccc6` | #1–#2（#1） | AC20 以外的 AC 通過；implementer 的 6 項實作選擇判斷符合規格；#1 交回實作修正（`a37ee89`：帳號列表抓取成功時把列表裡沒有的平台恢復成未連結）；#2 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 換使用者後，平台列表沿用前一個使用者的「憑證無法讀取」狀態 | Implementation Defect | Major | 是 | 安全 | 換使用者時的前端狀態 | 交回實作：帳號列表抓取成功時把列表裡沒有的平台恢復成未連結的初始值（或換使用者時重設），補用真的 `useLinkedAccount` 的 vitest | 規則 | 已修正（`a37ee89`，待第 2 輪確認） |
| 2 | 1 | 平台列表沒有把「授權已失效、沒有舊資料」記成已知的結果 | Improvement Suggestion | Info | 否 | 否 | — | 開 issue（目前的呼叫端走不到） | 主 session | [#80](https://github.com/Chen-Yihua/auto-scheduling-system/issues/80) |

## 問題說明

### #1 換使用者時的前端狀態

`usePlatformItems` 換使用者時只清自己的狀態（`frontend/composables/usePlatformItems.ts:66-83`），`useLinkedAccount` 的 `fetchKeys` 只更新後端列表裡有的平台（`frontend/composables/useLinkedAccount.ts:98-111`）。前一個使用者的 `needsReauth: true` 會留下來，`fetchItems` 看到它就直接顯示「憑證無法讀取」、不打 API（`usePlatformItems.ts:99-105`），違反 AC20「換成另一個使用者後，不顯示先前的結果」。

## 開發者決策

無。

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 1 | 交回實作修正中 | 無 |
