# issue-85-google-oauth-non-json 規格審查

- 等級：高風險
- 規格：[`docs/specs/issue-85-google-oauth-non-json.md`](../../specs/issue-85-google-oauth-non-json.md)

## 第 1 輪

規格審查發現 3 項阻擋問題：

1. 沒有獨立定義 refresh token 的成功流程。
2. 沒有明確要求解析錯誤時不得更新或刪除既有 token。
3. 沒有定義 HTTP 200、JSON payload 非 object 時的行為。

開發者決定三項都納入本次規格，並分別補入需求、AC、實作計畫與測試對應。

## 第 2 輪

規格審查發現 2 項阻擋問題：

1. 實作計畫未涵蓋新增 AC 的 payload 驗證、token 不更新與 refresh 成功保留 refresh token。
2. AC6 測試對應未明確驗證 `save_google_calendar_token`、`update_google_calendar_token`、`delete_google_calendar_token` 未被呼叫。

主 session 已補齊實作計畫與測試對應，並將有效 token 定義為非空 `access_token`。第二輪後沒有剩餘阻擋發現。
