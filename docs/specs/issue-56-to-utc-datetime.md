# `to_utc_datetime` 的空字串型別契約

- 狀態：已核准
- 等級：一般（修正既有型別標註與執行行為的契約，不涉及資料一致性、認證授權、個資、外部系統可靠性或重大架構決策）
- issue：[#56](https://github.com/Chen-Yihua/auto-scheduling-system/issues/56)
- PR：[#135](https://github.com/Chen-Yihua/auto-scheduling-system/pull/135)

## 簡短說明

修正 `to_utc_datetime` 對 `str` 輸入的 overload，讓型別檢查反映空字串可能回傳 `None`，避免呼叫端直接使用結果時漏掉缺值處理。

## 背景

`backend/core/datetimes.py` 的 `to_utc_datetime` 對 `None` 和空字串回傳 `None`，但目前 `str | datetime` overload 宣告所有 `str` 都回傳 `datetime`。因此，開發者傳入型別為 `str` 的值時，pyright 不會要求處理空字串；結果若直接呼叫 `.astimezone()` 等方法，執行時可能因 `None` 發生錯誤。

目前明確宣告 `str` 參數的正式呼叫端是 `compute_free_times`；它接收 Google FreeBusy API 回傳的 `timeMin`、`timeMax` 與 busy 時段字串，不改變其既有執行行為。

重現步驟：在任一接收 `str` 的呼叫端，以可能為空的字串呼叫 `to_utc_datetime`，再直接使用結果的 datetime 方法，例如 `.astimezone()`。修正前 pyright 將結果視為 `datetime` 而不提示；若實際輸入為 `""`，函式回傳 `None`，後續方法呼叫會產生 `AttributeError`。預期修正後 pyright 將結果視為 `Optional[datetime]`，要求先處理 `None`。

## 需求

1. 保留單一 `to_utc_datetime` 函式與現有執行行為。
2. `to_utc_datetime` 的 `str` 輸入 overload 必須宣告回傳 `Optional[datetime]`；`datetime` 輸入 overload 維持宣告回傳 `datetime`。
3. 補充測試，確認空字串仍回傳 `None`，並以型別檢查驗證 `str` 呼叫端必須處理可能的 `None`。
4. `compute_free_times` 必須在 `to_utc_datetime` 回傳型別變寬後仍通過 backend pyright，且維持有效時間字串的既有計算結果。
5. 型別檢查案例必須同時確認 `str` 輸入的結果是 `Optional[datetime]`，以及 `datetime` 輸入的結果仍是 `datetime`。
6. `compute_free_times` 遇到必要時間欄位為空字串時，必須立即丟出明確的 `ValueError`。

## 不做

- 不新增「一定有值」的替代函式。
- 不改變空白字串丟出 `ValueError` 的既有行為。
- 不改變 `None`、有效 ISO 字串或 `datetime` 的轉換規則。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 在呼叫端傳入型別為 `str` 的值時，pyright 要求呼叫端處理 `to_utc_datetime` 可能回傳的 `None`；型別案例確認 `datetime` 輸入仍可直接取得 `datetime`。 |
| AC2 | 在傳入空字串時，`to_utc_datetime` 要回傳 `None`，且不丟出例外。 |
| AC3 | 在傳入有效 ISO 字串、`datetime`、`None` 或既有支援的時區格式時，轉換結果與目前行為一致。 |
| AC4 | 在 `compute_free_times` 的視窗或 busy 時段必要時間欄位為空字串時，函式要立即丟出 `ValueError`，而不是因後續比較或排序產生間接的 `TypeError`。 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中、未登入／無權限 | 這是後端純函式的型別與轉換行為，不涉及 HTTP、登入或權限流程。 |
| 安全性 | 不處理認證、授權、敏感資料或外部輸入的安全邊界。 |

## 實作計畫

1. 修改 `backend/core/datetimes.py` 的 overload，將 `str` 輸入的回傳型別改為 `Optional[datetime]`，保留 `datetime` overload 為 `datetime`。
2. 修改 `backend/services/google_calendar_client.py` 的 `compute_free_times`，在 Google API 時間欄位轉換後立即檢查 `None` 並丟出 `ValueError`；有效時間字串的流程不變。
3. 檢查其他 production 呼叫端（包含 `backend/services/scheduler.py`）的型別是否仍由既有 guard 或 overload 保證，不擴大本次行為範圍。
4. 新增不放在 `tests/` 的專用 pyright 型別案例，以 `reveal_type` 驗證 `str` 結果為 `Optional[datetime]`、`datetime` 結果為 `datetime`；不進行全專案型別案例重整。
5. 在 `backend/tests/unit/test_datetimes.py` 補強空字串回歸測試，並在 `backend/tests/unit/test_google_calendar_client.py` 補上缺少必要時間欄位的 `ValueError` 回歸測試；以 pyright 驗證型別契約與 backend 呼叫端。

## 測試對應

| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | backend `pyright`，以及指定於 backend、位於 `tests/` 外的專用型別案例；案例以 `reveal_type` 確認 `str` 結果為 `Optional[datetime]`、`datetime` 結果仍為 `datetime` | 是（改前不會指出空字串可能回傳 `None`） |
| AC2 | `backend/tests/unit/test_datetimes.py::test_missing_values_become_none` | 否（執行行為原本正確，這是回歸保護） |
| AC3 | `backend/tests/unit/test_datetimes.py` 現有 ISO、naive、aware datetime 測試 | 否（既有行為應維持） |
| AC4 | `backend/tests/unit/test_google_calendar_client.py` 的 `compute_free_times` 缺少必要時間欄位測試 | 是（改前會在後續比較或排序產生間接的 `TypeError`） |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-17 | 初稿；確認保留單一函式，僅修正 `str` overload 的回傳型別並保留既有執行行為 | 開發者接受 Q1 建議方案 | 開發者 |
| 2026-11-18 | 補充外部 API 資料流、`compute_free_times` 缺值行為、專用型別案例與測試對應 | 回應規格審查；開發者確認 Q2、Q3、Q4 | 開發者 |
| 2026-11-18 | 核准本規格，依核准內容進入實作 | 開發者明確回覆「核准」 | 開發者 |

## 請你決定

無
