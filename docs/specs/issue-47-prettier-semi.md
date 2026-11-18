# 前端 Prettier 分號風格一致

- 狀態：已核准
- 等級：一般（修改前端格式化工具設定，影響開發工具輸出，不涉及應用程式執行時行為、資料、權限或安全性）
- issue：#47
- PR：尚未建立

## 簡短說明

保留前端 Prettier 現有的分號設定，將 repo 現有前端程式碼統一為分號風格，符合主流前端程式碼慣例，避免格式化工具設定與程式碼風格不一致。

## 背景

目前 [frontend/.prettierrc](../../../frontend/.prettierrc) 設定 `semi: true`，但前端既有程式大多不使用分號。開發者或 agent 在 `frontend` 目錄執行 `npm run format` 時，Prettier 會將檔案加入分號，造成與既有程式碼不一致的格式變更，增加審查成本。

## 需求

1. 保留前端 Prettier 的 `semi: true` 設定。
2. 保持現有 `npm run format` 的其他格式化設定不變。
3. 將現有前端程式碼統一為 Prettier `semi: true` 的分號風格。
4. 將因 `semi: true` 直接造成的既有前端檔案格式變更納入本 PR。
5. 將程式碼格式變更與設定檔檢查分開提交。

## 不做

- 不將前端 Prettier 設定改為 `semi: false`。
- 不處理與前端 Prettier 分號設定無關的格式規則。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 在最新 `main` 建立的乾淨工作目錄執行 `cd frontend && npm run format` 後，前端原始碼遵循 `semi: true`，不再因缺少分號而產生格式化 diff。 |
| AC2 | 執行 `cd frontend && npm run format` 後，所有由 `semi: true` 直接造成的既有前端檔案格式變更都納入本 PR，且不納入其他格式規則造成的差異。 |
| AC3 | 前端 Prettier 設定維持 `semi: true`。 |
| AC4 | 程式碼格式變更使用獨立 commit，且本次不修改 `frontend/.prettierrc`。 |
| AC5 | 執行 `cd frontend && npm run lint`、`cd frontend && npm run typecheck` 與 `cd frontend && npm run test` 後，前端檢查全部通過。 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗、空資料、載入中、未登入／無權限、資料處理 | 本次只修改開發工具格式化設定，不改變應用程式執行流程或資料處理。 |
| 安全性 | 不處理使用者輸入、認證、授權或外部資料。 |

## 實作計畫

1. 確認 `frontend/.prettierrc` 維持 `semi: true`，不修改設定檔。
2. 在前端目錄執行 `npm run format`，將因 `semi: true` 直接造成的既有前端檔案格式變更整理成格式專用 commit；排除其他格式規則造成的差異。
3. 執行既有 lint、typecheck、test 檢查，確認格式變更沒有造成程式或測試問題。

## 測試對應

| AC | 測試 |
|---|---|
| AC1 | 在 `frontend` 執行 `npm run format`，再重複執行並檢查工作樹，確認不再產生分號相關 diff。 |
| AC2 | 比對格式化前後的 diff，確認只納入 `semi: true` 直接造成的既有檔案變更。 |
| AC3 | 讀取 `frontend/.prettierrc`，確認 `semi` 維持 `true`。 |
| AC4 | 檢查 git log 與 `git diff`，確認格式變更為獨立 commit，且 `frontend/.prettierrc` 沒有修改。 |
| AC5 | `cd frontend && npm run lint`、`cd frontend && npm run typecheck`、`cd frontend && npm run test`。 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-18 | 建立 issue #47 規格草稿 | 將已確認的格式化行為與驗收方式記錄下來 | 待核准 |
| 2026-11-18 | 核准規格 | 開發者確認保留 `semi: true`，將既有前端程式碼統一為分號風格；確認需求、AC1–AC5、實作計畫與測試對應 | 開發者 |

## 請你決定

無。
