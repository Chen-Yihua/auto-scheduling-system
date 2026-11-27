# E2E 本機的除錯資料、伺服器 log 與 UI 模式，CI 不印 MongoDB log

- 狀態：已核准
- 等級：一般（只改 E2E 的本機設定、CI 啟動 MongoDB 的方式與文件；CI 不上傳任何檔案，機密的保護沒有變弱）
- 規格審查：有
- PR：[#190](https://github.com/Chen-Yihua/auto-scheduling-system/pull/190)

## 簡短說明
本機 E2E 失敗時留下截圖、錄影、trace，伺服器輸出存成檔案、只在伺服器的指令失敗結束時印出，並可以用 Playwright 的 UI 模式（官方的圖形介面，開著期間可以反覆重跑測試）重跑測試、不用每次重新啟動伺服器；CI 照舊每次重新啟動，而且不印 MongoDB 的 log。

## 背景
本機 E2E 失敗時除錯資料不足、伺服器輸出和測試進度混在一起、每次重跑都要重新 build；CI 會把 MongoDB 的 log 印進公開的 CI log。

這份規格由 PR #190 的短版規格（快速路徑）改寫而來：實作審查第 1 輪發現短版規格的做法有問題，開發者決定在這個 PR 修正，所以改走完整流程。

PR #189（`e2e-playwright`）合併後的情況：
- 本機測試失敗時只留 trace（可以一步步重播測試的紀錄檔）；截圖、錄影都關閉。
- 本機的前端、後端、MongoDB 伺服器輸出全部印在終端機，和測試進度混在一起。
- 每次 `npm run test:e2e` 都重新 build 前端、重新啟動三個伺服器，大約多 1～2 分鐘。
- CI 的 MongoDB 是 GitHub Actions 的 service container（job 旁邊另外開的容器）；job 結束時 GitHub 會自動把它的 log 印進公開的 CI log。

短版規格實作後發現的事實（PR #190 第一版，commit 210584d）：
- service container 加上 `--log-driver none` 後，MongoDB 的 log 不印了，但 GitHub 的「Print service container logs」改印出 `Error response from daemon: configured logging driver does not support reading` 與 `##[warning]Docker logs fail with exit code 1`。
- Playwright 沒有「只啟動 webServer（Playwright 在測試前自動啟動的伺服器）」的指令。`reuseExistingServer`（「port 上已經有伺服器就沿用」的設定）只在 port 上已經有伺服器時沿用它；`npm run test:e2e` 自己啟動的伺服器，測試結束時會被關掉。第一版的 `npm run e2e:serve` 用 `playwright test` 跑一個永遠不結束的測試撐住伺服器，這不是官方做法，副作用是每次啟動都清空 `test-results/`，而且沒有 Clerk 金鑰時一個伺服器都沒啟動、卻照樣一直開著。官方讓伺服器在多次執行之間保持開著的方式是 UI 模式（`playwright test --ui`）：UI 開著期間 webServer 一直開著，在 UI 裡重跑測試時沿用。
- 本機伺服器的輸出都設成 `ignore` 時，伺服器啟動失敗只看得到 Playwright 印的結束碼，看不到原因；`mongodb-memory-server` 第一次執行要下載 MongoDB 執行檔，下載失敗時完全看不到原因。

不沿用開發者的 `npm run dev` 與開發用後端：開發用後端沒有設 `GOOGLE_API_BASE_URL`（`e2e-user-flows`），排程測試會改到真的 Google 日曆；setup 也會清空資料庫。

## 需求

### 本機失敗時的除錯資料
1. 本機執行 `npm run test:e2e` 時，測試失敗就留下那個測試的截圖、錄影、trace；通過的測試不留。trace 裡已有瀏覽器的 Console、Network 請求與畫面快照，前端不另外收集 log。UI 模式由 Playwright 自己決定，一律錄 trace。
2. CI 不錄截圖、錄影、trace，不上傳任何檔案，伺服器的輸出不印也不存。

### 本機伺服器的 log
3. 本機執行時，MongoDB、後端、前端伺服器的輸出分別寫進 `frontend/e2e-logs/mongo.log`、`backend.log`、`frontend.log`，每次啟動時覆寫。
4. 執行 `npm run test:e2e` 時，三個伺服器的指令都沒有以非 0 結束碼結束，終端機就只顯示測試進度與結果，不顯示伺服器的輸出；測試結束時 Playwright 關掉伺服器也算在內。
5. 執行 `npm run test:e2e` 時，某個伺服器（MongoDB、後端、前端都一樣）的指令以非 0 結束碼結束，終端機就印出那個伺服器的 log 內容，啟動時與測試進行中都一樣。測試結束時 Playwright 關掉伺服器不算失敗結束。UI 模式下同樣的內容顯示在 UI 的 Output 面板。
6. `frontend/e2e-logs/` 不進版控，寫入時不會讓開著的 `npm run dev` 重啟。

### UI 模式與沿用伺服器
7. `npm run test:e2e:ui` 用 Playwright 的 UI 模式執行 E2E，在瀏覽器打開 UI（WSL 也能用）。
8. UI 開著期間，在 UI 裡重跑測試不重新 build 前端、不重新啟動伺服器。
9. 關掉 UI（在終端機按 Ctrl+C）時，三個伺服器都關掉；MongoDB 等 `startMongo.mjs` 清理完才算關掉。
10. 沒有 Clerk 金鑰時，UI 模式不啟動任何伺服器，只顯示「沒有 Clerk 金鑰，跳過 E2E」這一個測試。
11. 本機執行 `npm run test:e2e` 時，port 上已經有 E2E 伺服器就沿用，沒有就自己啟動、結束後關掉。
12. CI 不沿用已開著的伺服器，每次重新啟動。

### CI 的 MongoDB
13. CI 的 MongoDB 改在 job 的步驟裡用 `docker run --log-driver none` 啟動，不用 service container；CI log 裡沒有 MongoDB 的 log，也沒有讀不到 log 的錯誤或警告。

### 文件
14. `frontend/README.md`「測試」寫出下面每一項：
    1. `npm run test:e2e:ui` 的用法。
    2. 在 UI 的 Projects 設定勾選 `setup`、`guest`、`signed-in` 三個；只勾 `signed-in` 時 setup 不會先跑。
    3. 改了程式後，在執行 `npm run test:e2e:ui` 的終端機按 Ctrl+C，再重新執行；只關瀏覽器分頁時，伺服器還用舊程式開著，`npm run test:e2e` 也會沿用它們。
    4. 打開 UI、重新整理 UI 分頁，或 UI 開著時在另一個終端機執行 `npm run test:e2e`，都會清空 `test-results/`，要先看完上一次失敗的紀錄。
    5. 伺服器 log 的位置；伺服器起不來時去看 `e2e-logs/`，UI 模式也可以看 Output 面板。
    6. 失敗時截圖、錄影、trace 的位置，以及用 `npx playwright show-trace <檔案>` 打開 trace。
15. `docs/specs/e2e-playwright.md` 的「狀態」改成部分被這份規格取代，並連到這份規格。

## 不做
- 不處理：沿用開發者的 `npm run dev` 與開發用後端。原因見背景。
- 不處理：自己寫指令或腳本，在 UI 模式以外讓 E2E 伺服器保持開著。開發者選擇官方的 UI 模式。
- 不處理：伺服器啟動逾時時印出 log。逾時時 Playwright 直接關掉伺服器，指令的失敗分支不會執行；這時看 `e2e-logs/` 的檔案。
- 不處理：UI 正在跑測試時，同時在另一個終端機執行 `npm run test:e2e`。兩邊共用同一個 E2E 資料庫與登入狀態，setup 會清空資料庫。
- 不處理：沿用伺服器時，測試行程與後端拿到的 `E2E_SECRET_ENCRYPTION_KEY` 不同（`playwright.config.ts` 每次執行產生一把）。現有測試沒有用到；`e2e-user-flows` 會用到，由那份規格處理。
- 不處理：用 docker compose 啟動 CI 的 MongoDB。CI 只有一個容器，本機不用 Docker（`mongodb-memory-server`），compose 只多一個檔案。

## 假設
1. UI 模式用 `--ui-port` 在瀏覽器打開，而不是另開視窗：WSL 不一定能開視窗，瀏覽器在每個環境都能用。

## 驗收條件
| # | 需求 | 條件 |
|---|---|---|
| AC1 | 1 | 本機執行 `npm run test:e2e` 有測試失敗時，`frontend/test-results/` 裡有那個測試的截圖、錄影、trace；通過的測試沒有截圖、錄影、trace |
| AC2 | 2 | `GITHUB_ACTIONS=true` 時，`trace`、`screenshot`、`video` 都是 `off`，每個 `webServer` 的 `stdout`、`stderr` 都是 `ignore`；`deploy.yml` 沒有上傳 artifact |
| AC3 | 3 | 沒有已開著的 E2E 伺服器時，本機執行一次 `npm run test:e2e` 後，`frontend/e2e-logs/` 有 `mongo.log`、`backend.log`、`frontend.log`，都有內容；再執行一次，每個檔只有這一次的內容 |
| AC4 | 4 | 本機執行 `npm run test:e2e`、三個伺服器都正常啟動時，從開始到指令結束（包括測試結束、關掉伺服器的時候），終端機的輸出只有測試進度與結果，沒有伺服器的輸出 |
| AC5 | 5 | 本機執行 `npm run test:e2e`、讓後端啟動失敗（例如 `E2E_PYTHON` 指到不存在的指令）時，終端機印出 `backend.log` 的內容，裡面有失敗原因 |
| AC6 | 6 | `git check-ignore frontend/e2e-logs/backend.log` 成功；開著 `npm run dev` 時跑一次 E2E，dev server 沒有重啟、仍回 200 |
| AC7 | 7 | 執行 `npm run test:e2e:ui` 後，終端機印出 UI 的網址，用瀏覽器打開看得到測試清單 |
| AC8 | 8 | 在 UI 勾選 `setup`、`guest`、`signed-in`，連續執行兩次全部測試：第二次沒有 build、沒有啟動伺服器，`frontend.log` 裡 build 的輸出只出現一次 |
| AC9 | 9 | 在執行 `test:e2e:ui` 的終端機按 Ctrl+C、指令結束後，3100、8001、27018 都沒有程式在聽，沒有殘留的行程（包括 `startMongo.mjs`） |
| AC10 | 10 | 沒有 Clerk 金鑰時執行 `npm run test:e2e:ui`：UI 只有「沒有 Clerk 金鑰，跳過 E2E」這一個測試，3100、8001、27018 都沒有程式在聽 |
| AC11 | 11 | UI 開著、沒有在跑測試時，在另一個終端機執行 `npm run test:e2e`：沒有 build、沒有啟動伺服器，測試照常通過 |
| AC12 | 11 | 沒有 E2E 伺服器時執行 `npm run test:e2e`：自己啟動三個伺服器；指令結束後 3100、8001、27018 都沒有程式在聽，沒有殘留的行程（包括 `startMongo.mjs`） |
| AC13 | 12 | `GITHUB_ACTIONS=true` 時，每個 webServer 的 `reuseExistingServer` 是 `false` |
| AC14 | 13 | CI 的 `frontend-e2e-test` 通過；`deploy.yml` 的 `frontend-e2e-test` 沒有 `services`；job log 裡沒有 MongoDB 的 log，也沒有讀不到 log 的錯誤或警告 |
| AC15 | 14 | `frontend/README.md`「測試」有需求 14 的每一項 |
| AC16 | 15 | `docs/specs/e2e-playwright.md` 的「狀態」是：部分被 [e2e-local-run](e2e-local-run.md) 取代（需求 12 的 CI 部分、需求 19 的本機部分、需求 21 與 AC18 的「本機成功時沒有 trace」只適用 `npm run test:e2e`、實作計畫的「不設 `reuseExistingServer`」與 CI 用 service container 兩處、「不做」的 MongoDB log） |

## 實作計畫
1. `e2eConfig.ts`（本機）：
   - `screenshot: 'only-on-failure'`、`video: 'retain-on-failure'`，`trace` 維持 `retain-on-failure`（本機不重試，`on-first-retry` 錄不到）。
   - 三個 webServer 的指令都把輸出導到 `e2e-logs/<名稱>.log`（覆寫）；指令失敗時把那個 log 印到 stderr 再以原本的結束碼結束，webServer 的 `stderr` 設成 `pipe`、`stdout` 設成 `ignore`，所以只有失敗時終端機看得到內容。
   - MongoDB 的指令包一層 shell 後，Playwright 結束時仍要等 `startMongo.mjs` 清理完（做法由實作決定）。
   - `reuseExistingServer: !isCI`。
2. `package.json`：新增 `test:e2e:ui`（`playwright test --ui-port=<固定 port>`）；刪掉 `e2e:serve`、`frontend/e2e-serve.config.ts` 與 `frontend/tests/e2e/keepAlive.ts`。
3. `deploy.yml` 的 `frontend-e2e-test`：刪掉 `services.mongodb`，在跑 E2E 前加一步 `docker run -d --log-driver none -p 27018:27017 mongo:7`，並等 port 可以連線再往下。
4. `.gitignore` 有 `/frontend/e2e-logs/`；`eslint.config.mjs` 忽略 `e2e-logs/**`。
5. `e2eConfig.test.ts`：AC3 的斷言要能分辨覆寫（`>`）與附加（`>>`）；AC10 斷言沒有金鑰時沒有 webServer、只收集 `noClerkKeys.ts`。
6. `frontend/README.md`「測試」照需求 14 改寫，步驟寫成編號清單，一條一件事。
7. `docs/specs/e2e-playwright.md` 的「狀態」照 AC16 改；這份規格存成 `docs/specs/e2e-local-run.md`，PR 描述的短版規格換成這份規格的連結。

考慮過、沒選的做法：
- 用 `playwright test` 跑一個永遠不結束的測試撐住伺服器（第一版）：不是官方做法，沒有金鑰時沒有伺服器卻照樣開著。
- 自己寫腳本啟動伺服器，或 README 寫出三個伺服器的指令讓開發者自己開：開發者選擇官方的 UI 模式。

## 測試對應
| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | `e2eConfig.test.ts` 斷言本機的 `screenshot`、`video`、`trace`；手動加一個會失敗、一個會成功的臨時測試執行（跑完刪除） | 只有失敗的測試有截圖、錄影、trace。PR 描述附上結果 |
| AC2 | `e2eConfig.test.ts`（沿用 #189 的 AC16、AC17 測試） | 通過 |
| AC3 | `e2eConfig.test.ts` 斷言本機三個指令都用 `>` 導到 `e2e-logs/<名稱>.log`（不是 `>>`）；手動連跑兩次 | 三個檔都有內容；第二次後每個檔只有第二次的內容。PR 描述附上結果 |
| AC4 | 手動跑一次 | 終端機沒有伺服器的輸出。PR 描述附上輸出 |
| AC5 | 手動：`E2E_PYTHON=/nonexistent npm run test:e2e` | 終端機印出 `backend.log` 的內容，有找不到指令的訊息。PR 描述附上輸出 |
| AC6 | `git check-ignore`；開著臨時 dev server 跑一次 E2E | 被忽略；dev server 沒有重啟、仍回 200 |
| AC7 | 手動：`npm run test:e2e:ui` | 印出網址；瀏覽器打開看得到測試清單。PR 描述附上結果 |
| AC8 | 手動：在 UI 勾選三個 project 後連跑兩次 | 第二次沒有 build；`frontend.log` 裡 build 的輸出只出現一次 |
| AC9 | 手動：按 Ctrl+C，指令結束後馬上用 `ss -ltnp` 與 `ps` 檢查 | 三個 port 都沒有程式在聽，沒有殘留行程 |
| AC10 | `e2eConfig.test.ts`（沒有金鑰時沒有 webServer）；手動：`NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY= NUXT_CLERK_SECRET_KEY= npm run test:e2e:ui` | UI 只有一個跳過的測試；三個 port 都沒有程式在聽 |
| AC11 | 手動：UI 開著、沒有在跑測試時，另一個終端機 `npm run test:e2e` | 沒有 build 的輸出、測試通過 |
| AC12 | 手動：沒有 E2E 伺服器時 `npm run test:e2e`，結束後馬上檢查 | 三個 port 都沒有程式在聽，沒有殘留行程 |
| AC13 | `e2eConfig.test.ts` | `GITHUB_ACTIONS=true` 時每個 webServer 的 `reuseExistingServer` 是 `false` |
| AC14 | `e2eConfig.test.ts` 讀 `deploy.yml` 斷言沒有 `services`；這個 PR 的 CI log | CI 通過；log 裡沒有 MongoDB 的內容、沒有「Docker logs fail」的警告 |
| AC15 | 讀 `frontend/README.md` | 需求 14 的每一項都有 |
| AC16 | 讀 `docs/specs/e2e-playwright.md` 的「狀態」 | 和 AC16 寫的一致，連結點得開 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-27 | 短版規格改寫成完整規格；AC3 改成三個伺服器都存檔；新增 AC4、AC5（指令以非 0 結束時才印 log）；原 AC5、AC6（`e2e:serve`）改成 UI 模式（新 AC7～AC12，其中 AC10「沒有金鑰時」是新增的）；原 AC8 改成用 `docker run` 啟動 MongoDB（新 AC14）；原 AC9（README）改成 UI 模式的用法並新增 Projects 勾選、清空 `test-results/`、啟動失敗時去看哪裡（新 AC15）；原 AC1、AC3 限定 `npm run test:e2e` | 實作審查第 1 輪：AC8 的 service container 做法會出現警告（開發者選 `docker run`）；#5 MongoDB 啟動失敗看不到原因（開發者選存檔、失敗時才印）；#1、#2 `e2e:serve` 的副作用與不是官方做法（開發者選 UI 模式）。檢查過原 AC2、AC4、AC7 內容不變，只改編號 | 開發者 |

## 請你決定
無
