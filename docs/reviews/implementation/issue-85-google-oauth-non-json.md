# issue-85-google-oauth-non-json 實作審查

- PR：#128
- 等級：高風險
- 分支：`issue-85-google-oauth-non-json-main`

## 第 1 輪

### 摘要

- 發現：0 項
- 阻擋合併：0 項
- 不阻擋發現：0 項
- 主要風險：未發現。HTTP 200 的非 JSON、非 object、缺少或空白 `access_token` 均會回固定 `UPSTREAM_ERROR`，且不異動 token。

### 驗收條件

| AC | 結果 | 依據 |
|---|---|---|
| AC1 | 通過 | `backend/services/google_oauth.py:29-39`、`backend/routers/google_calendar.py:73-74`；callback 測試涵蓋 HTTP 200 非 JSON。 |
| AC2 | 通過 | `backend/services/google_oauth.py:55-61`、`:92-95`；refresh 測試涵蓋 HTTP 200 非 JSON。 |
| AC3 | 通過 | `backend/services/google_oauth.py:29-39`；callback 與 refresh 測試涵蓋非 object payload。 |
| AC4 | 通過 | `backend/services/google_oauth.py:35-39`；測試涵蓋缺少 `access_token`。 |
| AC5 | 通過 | `UPSTREAM_DETAIL` 為固定文字；測試確認 detail 不含 Google 回應原文。 |
| AC6 | 通過 | payload 驗證在儲存／更新前完成；測試確認 callback 不 save、refresh 不 update/delete。 |
| AC7 | 通過 | `backend/routers/google_calendar.py:72-79`；既有 callback 成功測試通過。 |
| AC8 | 通過 | `backend/services/google_oauth.py:99-102`；既有 refresh 成功測試確認保留原 refresh token。 |
| AC9 | 通過 | 既有 callback、refresh、連線、逾時、認證與授權測試通過。 |

### 執行的檢查

- `pyright`：0 errors, 0 warnings, 0 informations。
- `pytest`：1179 passed, 3 warnings。
- `git diff --check`：通過。
- 未修改 `docs/api.md`：本 PR 沒有新增或變更 endpoint、路徑、登入需求或限流。

### 安全與一致性檢查

- 登入與權限：通過；本次未改變既有依賴驗證。
- token 與第三方回應原文不外洩：通過；錯誤 detail 使用固定 `UPSTREAM_DETAIL`。
- 中途失敗後的資料狀態：通過；錯誤 payload 驗證先於 token 寫入。
- 與 Google 的一致性：通過；有效 token 維持成功流程，無效 payload 不異動既有 token。
- 既有資料相容性：通過；沒有新 refresh token 時保留既有 refresh token。

### 結果

沒有待處理項目，實作符合核准規格。
