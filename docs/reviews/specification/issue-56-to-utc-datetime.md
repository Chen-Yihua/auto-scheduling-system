# 規格審查：`to_utc_datetime` 的空字串型別契約

- 規格：[issue-56-to-utc-datetime.md](../../specs/issue-56-to-utc-datetime.md)
- issue：[#56](https://github.com/Chen-Yihua/auto-scheduling-system/issues/56)
- 等級：一般
- 審查者：specification-reviewer

## 審查結果

規格經兩輪審查後，阻擋項目已處理，開發者已核准規格。

## 第 1 輪

### 發現

1. **修 bug 背景缺少完整重現步驟與實際錯誤**  
   - 分類：規格內容互相矛盾或沒有依據
   - 嚴重程度：一般操作就會遇到的錯
   - 阻擋合併：是
   - 處理：補上空字串輸入、直接呼叫 datetime 方法時的實際 `AttributeError`、修正前後型別檢查差異與程式依據。

2. **Google FreeBusy 字串來源描述不正確**  
   - 分類：規格對現有系統的描述和程式不符
   - 嚴重程度：影響小的問題
   - 阻擋合併：是
   - 處理：依 `backend/services/google_calendar.py` 的資料流，改為 Google FreeBusy API 回傳的 `timeMin`、`timeMax` 與 busy 時段字串。

3. **AC1 與測試對應不足以驗證型別契約及受影響呼叫端**  
   - 分類：規格沒寫某個情境該怎麼做
   - 嚴重程度：一般操作就會遇到的錯
   - 阻擋合併：是
   - 處理：補列 `compute_free_times`，並要求型別案例同時驗證 `str` 與 `datetime` overload，以及 backend `pyright` 通過。

### 開發者決策

開發者確認將 `compute_free_times` 的型別處理與明確型別案例納入本 PR。

## 第 2 輪

### 發現

1. **`compute_free_times` 缺少時間欄位時的行為未定義**  
   - 分類：規格沒寫某個情境該怎麼做
   - 嚴重程度：一般操作就會遇到的錯
   - 阻擋合併：是
   - 處理：開發者選定必要時間欄位為空字串時立即丟出明確的 `ValueError`，並新增 AC4 與回歸測試要求。

2. **AC1 的型別案例與 pyright 執行方式不可驗證**  
   - 分類：規格內容互相矛盾或沒有依據
   - 嚴重程度：一般操作就會遇到的錯
   - 阻擋合併：是
   - 處理：開發者確認只新增 `to_utc_datetime` 專用型別案例，放在 `tests/` 外並由 backend `pyright` 檢查；不進行全專案型別案例重整。

### 開發者決策

開發者確認第 2 輪修正，並於 2026-11-18 核准規格。

## 最終檢查

- 所有需求、驗收條件與測試對應均已寫入核准規格。
- 規格狀態為「已核准」。
- 未建立 ADR 或術語表。
