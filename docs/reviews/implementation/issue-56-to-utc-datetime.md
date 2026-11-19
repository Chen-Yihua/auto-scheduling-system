# 實作審查：`to_utc_datetime` 的空字串型別契約

- 規格：[issue-56-to-utc-datetime.md](../../specs/issue-56-to-utc-datetime.md)
- 規格審查：[issue-56-to-utc-datetime.md](../specification/issue-56-to-utc-datetime.md)
- issue：[#56](https://github.com/Chen-Yihua/auto-scheduling-system/issues/56)
- PR：[#135](https://github.com/Chen-Yihua/auto-scheduling-system/pull/135)
- 等級：一般
- 審查者：acceptance-reviewer

## 摘要

沒有發現，沒有阻擋項目。

## 第 1 輪

### 執行結果

- `pyright`：通過。
- `pytest`：1106 passed，3 warnings。
- CI：backend、frontend、frontend E2E 全部通過。

### 驗收條件

| AC | 結果 | 依據 |
|---|---|---|
| AC1 | 通過 | `backend/core/datetimes.py` 分開宣告 `str -> Optional[datetime]`、`datetime -> datetime`；`backend/type_cases/to_utc_datetime_types.py` 以 `assert_type` 驗證兩種結果。 |
| AC2 | 通過 | `backend/core/datetimes.py` 空字串回傳 `None`；`backend/tests/unit/test_datetimes.py` 覆蓋空字串與 `None`。 |
| AC3 | 通過 | `backend/tests/unit/test_datetimes.py` 覆蓋 ISO、`Z`、`+00:00`、`+0800`、naive 與 aware `datetime`；實作未改變轉換邏輯。 |
| AC4 | 通過 | `backend/services/google_calendar_client.py` 先檢查 window，再逐筆檢查 busy 的 `start`、`end`；`backend/tests/unit/test_google_calendar_client.py` 四個案例完整覆蓋 window/busy 所有必要時間欄位。 |

### 其他檢查

- 型別案例確實會由 backend pyright 檢查。
- 測試能抓到 overload 回傳型別錯誤，以及只檢查部分必要時間欄位的錯誤實作。
- 有效時間的既有計算流程維持不變。
- 未發現規格外的程式變更、未處理的驗收條件或重大架構影響。

## 發現與處理

| # | 發現 | 分類 | 嚴重程度 | 阻擋合併 | 處理結果 |
|---|---|---|---|---|---|
| — | 沒有發現 | — | — | 否 | 不需修正；審查完成。 |

## 最終結果

- 所有驗收條件通過。
- 沒有待處理項目。
- 沒有建立額外 issue 或 advisory。
