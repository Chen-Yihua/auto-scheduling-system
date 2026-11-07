# API 回應的時間沒有時區：實作審查紀錄

- 規格：[docs/specs/issue-16-utc-datetimes-in-responses.md](../../specs/issue-16-utc-datetimes-in-responses.md)
- PR：#54
- 輪數：1（第 1 輪 2026-11-07 `36ed07e`）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：4 項（Improvement Suggestion 4；Minor 1、Info 3）
- 開發者決策：0 項
- 尚未處理：2 項（另開 #55、#56）

審查特別確認了改用 `tz_aware=True` 之後的風險（這部分沒有經過規格審查）：沒有找到把帶時區與不帶時區的時間混在一起比較或相減的程式路徑；收斂補時區函式後，只有在實際不會出現的輸入下行為才不同；實作者改的 4 處既有測試都是測試對「讀出不帶時區」的假設，沒有改測試去配合錯誤行為。

`docs/reviews/productivity-analytics-round3.md`（#1）曾建議「不對 Mongo client 全域開 `tz_aware=True`」；這次由開發者決定改採全域設定，理由見規格審查紀錄的「開發者決策」。舊紀錄依 `docs/reviews/README.md` 保留原樣。

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 4 則既有測試的名稱或說明還寫著「Mongo 讀出的時間不帶時區」 | Improvement Suggestion | Minor | 否 | 否 | — | 開 issue | 規則 | [#55](https://github.com/Chen-Yihua/auto-scheduling-system/issues/55) |
| 2 | 1 | `to_utc_datetime` 的型別標註說 `str` 一定回 `datetime`，但空字串回 `None` | Improvement Suggestion | Info | 否 | 否 | — | 開 issue | 規則 | [#56](https://github.com/Chen-Yihua/auto-scheduling-system/issues/56) |
| 3 | 1 | 規格審查紀錄的「PR」欄位還是「（核准前）」 | Improvement Suggestion | Info | 否 | 否 | — | 補上 #54 | 主 session（文件同步） | 和本紀錄同一個 commit |
| 4 | 1 | 舊的逐輪審查紀錄建議過「不要全域開 `tz_aware=True`」 | Improvement Suggestion | Info | 否 | 否 | — | 舊紀錄不改，在本紀錄的摘要交代 | 主 session（文件同步） | 和本紀錄同一個 commit |

## 問題說明

無（沒有阻擋、需要決策的項目；#1、#2 的內容見 issue）。

## 開發者決策

無。

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 1 | 不阻擋，另開 issue | #55 |
| 2 | 不阻擋，另開 issue | #56 |
