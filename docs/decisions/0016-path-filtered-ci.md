# 0016. CI 依改到的檔案決定要跑的測試與部署

- 狀態：已採用
- 日期：2026-11-20

## 背景

`.github/workflows/deploy.yml` 原本在每個 PR 與每次推到 `main` 時都跑全部的測試，推到 `main` 時也每次都部署前端。很多 PR 只改文件，也要等 `frontend-e2e-test`（build Nuxt、裝瀏覽器）跑完才能合併。

`main` 的 ruleset 要求 `backend-test`、`frontend-test`、`frontend-e2e-test` 通過才能合併。workflow 沒有啟動時，這 3 個檢查不會回報，PR 無法合併；job 因為 `if:` 不成立而跳過時，GitHub 當作通過。

## 決定

- `deploy.yml` 新增 `changes` job，用 `dorny/paths-filter` 判斷這次改到 `backend/**`、`frontend/**` 或 `deploy.yml` 本身。
- 測試 job 依結果用 `if:` 跳過；改到 `deploy.yml` 時全部都跑。
- `changes` 失敗時測試照樣執行，不讓「判斷不出來」變成「跳過也算通過」；推到 `main` 時這種情況不部署，要部署就重跑 workflow。
- 推到 `main` 時，只有改到前端才部署前端；後端部署條件同樣寫好，但後端部署目前關閉（`if: false`），條件先註解掉。
- `dorny/paths-filter` 釘在完整的 commit SHA，旁邊註解版本號。

## 放棄的做法

- **workflow 最上層的 `on.pull_request.paths`**：只改文件時 workflow 不啟動，必要的檢查不會回報，PR 無法合併。
- **在 job 裡自己跑 `git diff --name-only`**：不新增外部依賴，但 PR 與 push 的比較基準要自己處理，容易寫錯。
- **另外一個 workflow，在只改文件時回報同名的 check**：要維護兩份同名 job，名稱不一致時會卡住合併。

## 影響

- 多一個第三方 action：升級時要查新版的 commit SHA，並確認它沒有要求更多權限。
- 新增會影響測試的路徑時（例如前端測試開始讀 `docs/` 底下的檔案），要同步改 `changes` 的 `filters`，否則只改那個路徑的 PR 不會跑測試。
- 改 `deploy.yml` 本身一律跑全部測試，改 CI 設定的 PR 看不到「只改文件時跳過」的效果，要到合併後的下一個 PR 才看得到。
- 開啟後端部署時，刪掉 `deploy-backend` 的 `if: false`，取消上一行條件的註解。
- 在 `changes` 執行中手動取消 workflow 時，測試 job 可能被記成 skipped 而算通過；只有維護者能取消，接受這個風險，取消後要重跑。
- PR 改到超過 3000 個檔案時，GitHub API 回傳的清單不完整，可能漏判；這個 repo 不會有這麼大的 PR，不處理。
