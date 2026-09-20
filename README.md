# Auto Scheduling System

全端儀表板：把使用者的任務與截止日期集中在同一個地方——手動建立的任務、GitHub issue / PR、Jira issue、Moodle 作業——並整合 Google Calendar，提供 AI 輔助的優先度/時長估算，以及規則式的排程建議。

使用 FastAPI（後端）+ MongoDB 與 Nuxt 3（前端）開發，兩端都用 Clerk 做身分驗證。

---

## 架構

```
├── Backend/   # FastAPI + MongoDB，部署到 Google Cloud Run（Docker）
└── Frontend/  # Nuxt 3 + TypeScript，部署到 Vercel
```

- **身分驗證**：兩端都用 [Clerk](https://clerk.com/)。前端不會接觸到密碼，後端只會用 Clerk 的 JWKS 驗證 JWT。
- **資料庫**：MongoDB（持久資料）+ Redis（選用，用於流量限制計數與短時間快取；沒設定 `REDIS_URL` 時退回程序內記憶體）。
- **CI/CD**：GitHub Actions（`.github/workflows/deploy.yml`）。前後端各有自己的測試 job，通過後才會執行對應的部署 job。

各端的安裝與設定說明見 [`Backend/README.md`](Backend/README.md) 和 [`Frontend/README.md`](Frontend/README.md)。

---

## 功能

- **手動任務管理**：新增/編輯/刪除任務；優先度和時長沒填時由 AI（Gemini）推斷，也可以附上提醒來引導推斷（例如「這比看起來花更久」）。
- **第三方平台同步**（GitHub issue/PR、Jira issue、Moodle 作業）：每次讀取都即時抓取並自動翻頁；即時抓取失敗時，退回最後一次成功同步的快照；上游已經不存在的項目會從本地快取清掉，不會一直殘留。
- **Google Calendar 整合**：嵌入行事曆、計算空閒/忙碌時段，並提供建立在其上的規則式排程建議。
- **帳號連結管理**：連結 GitHub/Jira/Moodle 帳號；憑證加密儲存，回傳給前端時一律遮罩；Moodle 連結會先用 Selenium 做真實登入驗證才儲存。
- **儀表板小工具**：Hacker News 熱門文章與 LeetCode 每日一題，顯示在任務畫面旁（不需要登入）。
- **資安強化**：只允許更新白名單欄位（防止 mass assignment）、依登入使用者限流、機密加密，錯誤回應為通用訊息，不會把內部例外細節洩漏給前端。
- **GitHub PR 摘要機器人**：一個獨立於使用者功能的 webhook，把 AI 產生的 PR 摘要貼到 Discord，給這個 repo 自己的開發流程使用。

---

## 技術棧

| 層 | 技術 |
|---|---|
| 前端 | Nuxt 3、Vue 3（Composition API）、TypeScript、Nuxt UI、Tailwind CSS、Clerk |
| 後端 | FastAPI、Motor（非同步 MongoDB 驅動）、Pydantic、slowapi（流量限制）、Selenium（Moodle 爬蟲）、Google Gemini（AI 推斷與 PR 摘要） |
| 資料庫 | MongoDB（持久資料）、Redis（選用：快取 / 流量限制儲存） |
| 測試 | Pytest（單元測試 + 整合/API 測試）、Vitest（元件/composable 單元測試）、Playwright（透過 `@nuxt/test-utils` + `@clerk/testing` 做真實瀏覽器 E2E） |
| 部署 | Docker → Google Cloud Run（後端）、Vercel（前端）、GitHub Actions（CI/CD） |

---

## 測試策略

- **後端**：依「有沒有走 HTTP」分成兩個資料夾。`tests/unit/` 直接呼叫 crud / router 函式，資料庫與外部 API 都 mock 掉；`tests/integration/` 對應用程式發出真的 HTTP 請求：每個 endpoint 的 **API 測試**（路由、登入驗證、回應格式、狀態碼），以及用記憶體資料庫（`mongomock-motor`）串起多個呼叫的**情境測試**，抓出單一 endpoint mock 看不到的問題（例如「更新真的有存進去、下一次讀取看得到嗎」）。詳見 [`Backend/tests/README.md`](Backend/tests/README.md)。
- **前端**：元件與 composable 測試跑在 jsdom，Nuxt 的 auto-import 用 mock 取代；另外有獨立的 **E2E 測試**，會真的 build 並啟動 Nuxt app，用真實的 headless 瀏覽器（Playwright）操作，涵蓋未登入的畫面，以及（CI 上有設定 Clerk 測試使用者時）真實的登入流程（用該使用者 email 的一次性 Clerk 登入 ticket 登入）。

在本機執行：

```bash
# 後端
cd Backend && pytest                   # 全部
cd Backend && pytest tests/unit        # 單元測試，很快，不走 HTTP
cd Backend && pytest tests/integration # 整合測試，走 HTTP

# 前端
cd Frontend && npm run test       # 單元/元件測試
cd Frontend && npm run test:e2e   # 真實瀏覽器 E2E（前置條件見 Frontend/README.md）
```
