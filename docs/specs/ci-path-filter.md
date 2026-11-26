# 依改到的檔案決定 CI 要跑哪些測試與部署

- 狀態：已核准
- 等級：高風險（新增外部依賴 `dorny/paths-filter`，也改變推到 `main` 時要不要部署，屬於「重大架構決策」的新增外部依賴與改部署方式）
- PR：#163

## 簡短說明

`.github/workflows/deploy.yml` 改成先判斷這次改了哪些檔案，只跑受影響的測試與部署；只改文件時，3 個必要的測試 job 都跳過，PR 照樣能合併。

## 背景

- 現在 `deploy.yml` 在每個 PR 與每次推到 `main` 時，都會跑 `backend-test`、`frontend-test`、`frontend-e2e-test`。其中 `frontend-e2e-test` 要 build Nuxt 與安裝瀏覽器，跑很久。
- 最近很多 PR 只改 `docs/`、`.claude/skills/`、`CLAUDE.md`，也要等完整的 CI 跑完。
- 推到 `main` 時，`deploy-frontend` 每次都會部署 Vercel（`deploy.yml` 的 `deploy-frontend`，`if: github.ref == 'refs/heads/main' && github.event_name == 'push'`）。
- `deploy-backend` 目前是 `if: false`，上面一行是註解掉的原本條件 `# if: github.ref == 'refs/heads/main' && github.event_name == 'push'`。Cloud Run 已停用計費，正式環境刻意關閉。
- `main` 的 ruleset「main protection」要求 `backend-test`、`frontend-test`、`frontend-e2e-test` 這 3 個 status check 通過才能合併（`gh api repos/{owner}/{repo}/rulesets`）。
  - 用 workflow 最上層的 `on.pull_request.paths` 讓整個 workflow 不啟動時，這 3 個 check 不會回報，PR 會一直停在「等待中」，無法合併。
  - job 因為 `if:` 條件不成立而跳過（skipped）時，GitHub 把它當作通過必要的檢查（GitHub 文件「Troubleshooting required status checks」）。
- `backend/tests/unit/test_ci_env_requirements.py` 會讀 `deploy.yml`，檢查 `backend-test` job 有帶入必要的環境變數。這個測試用 `_get_job_block` 抓「2 個空白縮排的 `  backend-test:`」那一行到下一個同層 key 之間的內容。
- 根目錄 `README.md` 第 20 行寫「前端與後端各自執行測試，測試通過後才會執行對應的部署」。

## 需求

1. `deploy.yml` 新增一個判斷改了哪些檔案的 job，名稱 `changes`，輸出 `backend`、`frontend` 兩個是否改到的結果。
2. 改到 `backend/**` 時，`backend` 是 true。
3. 改到 `frontend/**` 時，`frontend` 是 true。
4. 改到 `.github/workflows/deploy.yml` 時，`backend` 與 `frontend` 都是 true。
5. 只改上面以外的檔案（例如 `docs/`、`.claude/`、`README.md`、`CLAUDE.md`、`scripts/dev.sh`、`.github/workflows/scheduled-sync.yml`）時，`backend` 與 `frontend` 都是 false。
6. `backend-test` 只在 `backend` 是 true 時執行，否則跳過。
7. `frontend-test` 與 `frontend-e2e-test` 只在 `frontend` 是 true 時執行，否則跳過。
8. `changes` job 失敗時，3 個測試 job 都要照樣執行：判斷不出改了什麼時，不能讓測試被跳過而算通過。
9. `changes` job 失敗時，推到 `main` 也不部署前端；要部署時由開發者重跑 workflow。
10. 推到 `main` 時，`deploy-frontend` 只在 `frontend` 是 true、而且兩個前端測試都通過時部署。
11. `deploy-backend` 的部署條件改成「推到 `main`、`backend` 是 true、`backend-test` 通過」，但這個條件維持註解掉，`if: false` 保留不動；之後開啟後端時，只要刪掉 `if: false` 並取消註解。
12. 3 個測試 job 的名稱不改，必要的 status check 才對得上。
13. 根目錄 `README.md` 第 20 行改成說明「依改到的檔案決定跑哪些測試與部署」。
14. 新增 ADR 0004，並在 `docs/decisions/README.md` 的清單加一列。
15. `CLAUDE.md`「開發流程」第一段的「`backend-test`、`frontend-test`、`frontend-e2e-test` 都要通過」補成「都要通過（PR 沒改到後端或前端時，對應的測試會顯示 skipped，GitHub 也算通過）」；規則不變。
16. 在 `changes` 執行中手動取消 workflow 時，測試 job 可能被記成 skipped 而算通過；這個風險接受、不另外處理（只有維護者能取消，取消後看得到 check 的狀態，重跑即可）。
17. 實作時在這個 PR 實際取消一次 workflow，驗證 GitHub 怎麼記錄測試 job，結果寫在 PR 描述（實作計畫步驟 9）。

## 不做

- 不改 `main` 的 ruleset（必要的 status check 維持這 3 個）。
- 不開啟後端部署（`if: false` 保留）。
- 不改 `scheduled-sync.yml`。
- 不把 3 個測試 job 再拆細（例如只改 `backend/tests/` 也照樣跑 `backend-test`）。
- 不改 job 裡實際跑的指令（安裝、lint、typecheck、測試、部署的步驟不動）。
- 不為 `deploy.yml` 的 `if:` 條件新增自動化測試：只能比對字串，驗不出 GitHub 實際的行為；AC5、AC11、AC12 用審查 `deploy.yml` 確認。
- 不處理 PR 改到超過 3000 個檔案時，GitHub API 回傳的清單不完整（寫在 ADR「影響」）。

## 假設

1. `dorny/paths-filter` 釘在最新的 v4 release（目前 `v4.0.3`）對應的 commit SHA；實作時用 `gh api repos/dorny/paths-filter/git/ref/tags/v4.0.3` 查 SHA（若是 annotated tag 要再解到 commit），並在旁邊註解版本號。依據：GitHub 的安全建議，第三方 action 要釘完整的 commit SHA。
2. 推到 `main` 時，`dorny/paths-filter` 預設和這次 push 的前一個 commit（`github.event.before`）比較；`main` 只能透過 PR 合併，所以就是比較這次合併進來的所有改動。實作時依它的 README 確認，不符合就停下回報。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 在 PR 只改 `backend/**` 以外、`frontend/**` 以外、`deploy.yml` 以外的檔案時，3 個測試 job 都顯示 skipped，PR 的必要檢查算通過 |
| AC2 | 在 PR 改到 `backend/**`、沒改 `frontend/**` 與 `deploy.yml` 時，`backend-test` 執行，兩個前端測試 job 顯示 skipped |
| AC3 | 在 PR 改到 `frontend/**`、沒改 `backend/**` 與 `deploy.yml` 時，兩個前端測試 job 執行，`backend-test` 顯示 skipped |
| AC4 | 在 PR 改到 `deploy.yml` 時，3 個測試 job 都執行 |
| AC5 | 在 `changes` job 失敗時，3 個測試 job 都執行（不變條件：判斷失敗不能讓測試被跳過而算通過） |
| AC6 | 在推到 `main`、沒改 `frontend/**` 與 `deploy.yml` 時，`deploy-frontend` 不執行 |
| AC7 | 在推到 `main`、改到 `frontend/**`、兩個前端測試都通過時，`deploy-frontend` 執行 |
| AC8 | 在任何情況下，`deploy-backend` 都不執行（`if: false` 保留） |
| AC9 | 在 PR 的 workflow 跑完時，必要的 status check 名稱仍是 `backend-test`、`frontend-test`、`frontend-e2e-test`（不變條件） |
| AC10 | 在 `backend-test` 跑 `test_ci_env_requirements.py` 時，測試照樣通過（不變條件：`backend-test` 的 job 區塊仍帶入 3 個必要的環境變數） |
| AC11 | 在推到 `main`、`changes` job 失敗時，`deploy-frontend` 不執行 |
| AC12 | 在開發者刪掉 `deploy-backend` 的 `if: false`、取消上一行註解後，部署條件是「推到 `main`、`backend` 是 true、`backend-test` 通過」（`needs` 包含 `changes` 與 `backend-test`） |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 空資料、載入中、未登入／無權限 | 只改 CI 設定，不碰畫面、API 與登入流程 |
| 資料處理 | 不碰資料庫與外部平台同步 |
| 安全性：secrets 外洩 | `changes` job 不讀 secrets；權限只給 `contents: read`、`pull-requests: read`（`dorny/paths-filter` 在 PR 上用 API 讀改到的檔案清單）。第三方 action 釘 commit SHA（假設 1） |
| 安全性：fork 的 PR | 判斷依據是 PR 實際改到的檔案清單；改到 `deploy.yml` 的 PR 能改變判斷規則，這和改這個設計之前一樣（PR 原本就能改 `deploy.yml`），靠合併前看改動擋住；既有的 secrets 行為不變 |

## 實作計畫

### 要改的檔案

- `.github/workflows/deploy.yml`
- `README.md`（第 20 行）
- `CLAUDE.md`（「開發流程」第一段）
- `docs/decisions/0004-path-filtered-ci.md`（新增，內容見 ADR 草稿）
- `docs/decisions/README.md`（清單加一列）

### 步驟

1. 在 `jobs:` 最前面新增 `changes` job：
   - `runs-on: ubuntu-latest`。
   - `permissions: { contents: read, pull-requests: read }`。
   - 步驟：`actions/checkout@v4`（push 事件時 `dorny/paths-filter` 要用 git 比較）、`dorny/paths-filter@<SHA> # v4.0.3`，`id: filter`。
   - `filters`：
     ```yaml
     backend:
       - 'backend/**'
       - '.github/workflows/deploy.yml'
     frontend:
       - 'frontend/**'
       - '.github/workflows/deploy.yml'
     ```
   - `outputs`：`backend: ${{ steps.filter.outputs.backend }}`、`frontend: ${{ steps.filter.outputs.frontend }}`。
2. `backend-test` 加 `needs: changes`，以及：
   `if: ${{ !cancelled() && (needs.changes.result != 'success' || needs.changes.outputs.backend == 'true') }}`
   - 不用預設的 `success()`：`changes` 失敗時預設會跳過，跳過又被當作通過，等於沒跑測試就能合併（需求 8）。
   - `!cancelled()`：手動取消 workflow 時不要繼續跑。
3. `frontend-test`、`frontend-e2e-test` 同上，條件看 `needs.changes.outputs.frontend`。
4. `deploy-frontend`：`needs` 加上 `changes`，`if` 改成
   `github.ref == 'refs/heads/main' && github.event_name == 'push' && needs.changes.outputs.frontend == 'true'`。
   - 沒有寫狀態函式時 GitHub 會自動加上 `success()`，前端測試被跳過或失敗都不會部署。
   - `changes` 失敗時 `outputs.frontend` 是空的，所以不部署（需求 9）。
5. `deploy-backend`：`needs` 改成 `[changes, backend-test]`；註解掉的條件改成
   `# if: github.ref == 'refs/heads/main' && github.event_name == 'push' && needs.changes.outputs.backend == 'true'`；`if: false` 保留。註解寫一行：開啟後端時刪掉 `if: false`、取消上一行的註解。
6. job 的縮排維持 2 個空白，`backend-test:` 那一行的格式不變，`test_ci_env_requirements.py` 的 `_get_job_block` 才抓得到。
7. `README.md` 第 20 行改成：「使用 GitHub Actions（`.github/workflows/deploy.yml`）。依 PR 或 push 改到的檔案決定要跑哪些測試：改到 `backend/` 跑後端測試，改到 `frontend/` 跑前端測試，改到 `deploy.yml` 全部都跑，只改其他檔案時測試直接跳過。測試通過後才會執行對應的部署。」
8. `CLAUDE.md` 照需求 15 修改。
9. PR 開好、CI 啟動後，在 `changes` 還在跑時手動取消一次 workflow（`gh run cancel <run id>`），用 `gh run view <run id> --json jobs` 記下 3 個測試 job 的 `conclusion` 與 `gh pr checks` 的狀態，寫進 PR 描述，再 `gh run rerun <run id>` 重跑（需求 17）。`gh run cancel` 或 `gh run rerun` 不能執行，或重跑沒有啟動時，停下來回報，並在 PR 描述寫明這個 commit 的測試還沒跑完、不能合併。AC4、AC9 看重跑後的 run。錯過 `changes` 執行的時間點時，push 一個空 commit 再試一次，最多 2 次，仍錯過就在回報寫明。
10. 用 `actionlint` 檢查 `deploy.yml`（有就用；本機沒有時用 `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest`，兩者都不能用時在回報寫明）。

### 為什麼這樣做

- 必要的 status check 只看 job 的結果，所以 workflow 要照樣啟動，在 job 層用 `if:` 跳過；這是 GitHub 文件建議的做法。
- `dorny/paths-filter` 同時處理 PR（比較 PR 的 base）與 push（比較前一個 commit），不用自己算比較基準。

### 放棄的做法

- **workflow 最上層的 `on.pull_request.paths`**：只改文件時整個 workflow 不啟動，3 個必要的 check 不會回報，PR 無法合併。
- **在 job 裡自己跑 `git diff --name-only`**：不新增外部依賴，但 PR 與 push 的比較基準要自己處理，大約 15 行 shell，比較容易寫錯（開發者選了 `dorny/paths-filter`）。
- **拆成兩個 workflow，再加一個只改文件時回報同名 check 的 workflow**：GitHub 舊文件的做法，要維護兩份同名 job，兩邊名稱不一致時會卡住合併。
- **`changes` 失敗時照預設跳過測試**：跳過算通過，等於沒有測試就能合併。

## 測試對應

這次只改 CI 設定，用 CI run 驗證，不新增自動化測試（見「不做」）：GitHub 實際怎麼判斷 `if:` 與必要檢查，本機無法重現。

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | 合併後第一個只改文件的 PR 的 CI run（待辦） | 3 個測試 job 是 skipped，PR 顯示可合併 |
| AC2 | 合併後第一個只改 `backend/` 的 PR 的 CI run（待辦） | `backend-test` 執行，兩個前端測試 job 是 skipped |
| AC3 | 合併後第一個只改 `frontend/` 的 PR 的 CI run（待辦） | 兩個前端測試 job 執行，`backend-test` 是 skipped |
| AC4 | 這個 PR 的 CI run（改到 `deploy.yml`） | 3 個測試 job 都執行並通過 |
| AC5 | 審查 `deploy.yml` 3 個測試 job 的 `if:`；不刻意製造 `changes` 失敗 | 條件在 `needs.changes.result != 'success'` 時成立 |
| AC6 | 合併後第一個只改文件的 commit 推到 `main` 的 workflow run（待辦） | `deploy-frontend` 是 skipped |
| AC7 | 這個 PR 合併後推到 `main` 的 workflow run（待辦；改到 `deploy.yml`，所以 `frontend` 是 true），以及合併後第一個改到 `frontend/` 的 commit 推到 `main` 的 run（待辦） | `changes` 成功，`deploy-frontend` 執行並成功 |
| AC8 | 審查 `deploy.yml`；這個 PR 合併後推到 `main` 的 workflow run（待辦；改到 `deploy.yml`，所以 `backend` 是 true） | `deploy-backend` 仍有 `if: false`；那次 run 裡 `deploy-backend` 是 skipped |
| AC9 | 這個 PR 的 `gh pr checks` | `backend-test`、`frontend-test`、`frontend-e2e-test` 都出現並通過 |
| AC10 | 這個 PR 的 CI run；本機 `cd backend && pytest tests/unit/test_ci_env_requirements.py` | `backend-test` 通過，`test_ci_env_requirements.py` 通過 |
| AC11 | 審查 `deploy.yml` 的 `deploy-frontend` 條件；不刻意製造 `changes` 失敗 | 條件包含 `needs.changes.outputs.frontend == 'true'`，沒有狀態函式（隱含 `success()`） |
| AC12 | 審查 `deploy.yml` 的 `deploy-backend` | 註解掉的條件包含推到 `main` 與 `needs.changes.outputs.backend == 'true'`；`needs` 是 `[changes, backend-test]`；沒有狀態函式（隱含 `success()`） |

需求 17 的驗證：實作計畫步驟 9，結果寫在 PR 描述（記錄 GitHub 的行為，不論結果是什麼都不擋合併）。

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
