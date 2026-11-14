# 0013. 外部平台定時同步由 GitHub Actions 觸發

- 狀態：已採用
- 日期：2026-11-14

## 背景

外部平台（GitHub、Jira、Moodle）的資料原本只在使用者打開儀表板或平台頁面時即時同步。這有兩個問題：

- 很久沒打開平台頁面時，工作效率統計用的是舊資料（issue #13）。
- 每次打開頁面都即時抓資料，Moodle 每次都要開 headless Chrome 爬網頁，Cloud Run 的用量和費用跟著打開頁面的次數增加。

開發者決定改成每天台灣時間 12:00 定時同步一次，打開頁面只讀資料庫，想看最新資料時按「立即同步」（規格 [issue-13-scheduled-sync.md](../specs/issue-13-scheduled-sync.md)）。

後端部署在 Cloud Run，沒有請求時會縮到 0；開發者也在控制費用，不想讓 instance 常駐。

## 決定

- 新增 GitHub Actions workflow `.github/workflows/scheduled-sync.yml`，用 `schedule`（cron `0 4 * * *`，UTC 04:00 等於台灣時間 12:00）定時執行，另外可以手動觸發（`workflow_dispatch`）。
- workflow 用 `curl` 呼叫後端 `POST /internal/scheduled-sync`，在 `Authorization: Bearer <密鑰>` 帶共用密鑰。密鑰存在 GitHub secrets 的 `SCHEDULED_SYNC_SECRET`，後端讀同名的環境變數。
- 後端用 `hmac.compare_digest` 比對密鑰；沒設定密鑰時一律拒絕。
- 定時同步在這一次請求裡依序處理所有已連結的平台帳號，處理完才回應：Cloud Run 在回應送出後會限制 CPU，所以不在背景執行。
- 回應只帶各結果的筆數，不帶使用者 id 或錯誤內容：公開 repo 的 Actions log 任何人都看得到。

## 放棄的做法

- **程式內建定時器（例如 APScheduler）**：Cloud Run 縮到 0 時定時器不會執行；設定最少保留 1 個 instance 才可靠，但會持續收費。
- **Cloud Scheduler 呼叫 endpoint**：時間準，但要在 GCP 另外設定排程與服務帳號，後端還要驗證 Google 簽發的身分 token；設定不在 repo 裡，也綁定 GCP。
- **Cloud Run Jobs 加 Cloud Scheduler**：不用開放 endpoint，但部署流程要多部署一個 job，綁 GCP 最深。
- **在背景執行、先回 202**：Cloud Run 回應後會限制 CPU，背景工作可能跑不完。

## 影響

- GitHub 的排程常延遲 5 到 30 分鐘，同步時間不精準；repo 60 天沒有活動時，GitHub 會停用排程，要到 Actions 頁面重新啟用。
- 換部署平台時只要改 workflow 呼叫的網址（GitHub variable `BACKEND_URL`）。
- 要在兩個地方設定同一個密鑰：GitHub secrets 與 Cloud Run 的環境變數；換密鑰時兩邊都要改。
- 一次請求要在 Cloud Run 的請求時間上限內做完。使用者變多、超過上限時，要改成分批處理。
- 開發與正式環境共用資料庫（#78），定時同步只由正式環境執行。
