# 規格審查紀錄：issue-92-get-current-clerk-user

## 第 1 輪

- 結果：1 項阻擋、1 項不阻擋建議。
- 阻擋項目：AC3 將 `get_current_clerk_user` 的例外寫成「回傳」，與實際程式及 AC1 的「丟出」不一致。已將 AC3 改為「丟出」。
- 不阻擋建議：測試對應的「改程式前是否失敗」不適合測試缺口；已改為「錯誤實作時是否失敗」，以描述新增回歸測試的目的。
- 依據：`backend/core/security.py:143-149`、`backend/tests/unit/test_security.py:332-351`。
- 審查者：specification-reviewer

## 開發者決策

無。
