# Auto Scheduling System

把手動建立的任務、GitHub issue / PR、Jira issue、Moodle 作業集中管理，並串接 Google Calendar。任務的優先度與所需時間可由 AI 協助評估，再依行事曆上的空檔，提供排程建議。

後端使用 FastAPI + MongoDB，前端使用 Nuxt 3，兩端的身分驗證都交給 Clerk。

---

## 架構

```
├── Backend/   # FastAPI + MongoDB，以 Docker 部署到 Google Cloud Run
└── Frontend/  # Nuxt 3 + TypeScript，部署到 Vercel
```

- **身分驗證**：前後端都使用 [Clerk](https://clerk.com/)。前端不會經手使用者密碼；後端以 Clerk 公開的金鑰（JWKS）驗證每個請求附帶的 JWT。
- **資料庫**：MongoDB 負責持久化資料。Redis 為選用，用於限流計數與短期快取；未設定 `REDIS_URL` 時，改用應用程式本身的記憶體（重啟後會清空）。
- **CI/CD**：使用 GitHub Actions（`.github/workflows/deploy.yml`）。前端與後端各自執行測試，測試通過後才會執行對應的部署。

各端的安裝與設定方式，請見 [`Backend/README.md`](Backend/README.md) 與 [`Frontend/README.md`](Frontend/README.md)。

---

## 功能

- **任務管理**：新增、編輯、刪除任務。優先度與所需時間未填寫時，由 AI（Gemini）推估；也可以附上提示讓推估更貼近實際（例如「這件事比看起來更花時間」）。
- **第三方平台同步**（GitHub issue / PR、Jira issue、Moodle 作業）：每次讀取都即時向對方平台取得最新資料，並自動處理分頁。若即時取得失敗，會改用最近一次成功同步的資料；對方平台上已不存在的項目，會從本地快取中移除，不會殘留在畫面上。
- **Google Calendar 整合**：嵌入行事曆、計算空閒與忙碌時段，並依這些時段提供規則式的排程建議。
- **帳號連結管理**：可連結 GitHub、Jira、Moodle 帳號。憑證以加密方式儲存，回傳給前端時一律遮蔽；Moodle 帳號在儲存前，會先以 Selenium 實際登入一次，確認帳密正確。
- **儀表板小工具**：在任務畫面旁顯示 Hacker News 熱門文章與 LeetCode 每日一題，不需登入即可查看。
- **安全強化**：
  - 更新資料時只接受白名單內的欄位，避免 mass assignment。
  - 依登入的使用者限流。
  - 敏感資料加密儲存。
  - 錯誤回應一律使用通用訊息，不向前端洩漏內部例外的細節。
- **GitHub PR 摘要機器人**：與上述使用者功能各自獨立的 webhook，由 AI 產生 PR 摘要並貼到 Discord，供本專案自己的開發流程使用。

---

## 技術選型

| 類別 | 技術 |
|---|---|
| 前端 | Nuxt 3、Vue 3（Composition API）、TypeScript、Nuxt UI、Tailwind CSS、Clerk |
| 後端 | FastAPI、Motor（MongoDB 非同步驅動程式）、Pydantic、slowapi（限流）、Selenium（Moodle 登入與爬取）、Google Gemini（AI 推估與 PR 摘要） |
| 資料庫 | MongoDB（持久化資料）、Redis（選用：快取、限流計數） |
| 測試 | Pytest（單元測試、整合測試）、Vitest（元件與 composable 單元測試）、Playwright（透過 `@nuxt/test-utils` 與 `@clerk/testing` 執行真實瀏覽器的 E2E 測試） |
| 部署 | Docker → Google Cloud Run（後端）、Vercel（前端）、GitHub Actions（CI/CD） |

---

## 測試策略

- **後端**：依「是否經過 HTTP」分成兩個目錄。
  - `tests/unit/`：直接呼叫 crud 與 router 函式，資料庫與外部 API 一律 mock。
  - `tests/integration/`：對應用程式發出真實的 HTTP 請求，包含兩類測試：
    - **API 測試**：逐一驗證每個端點的路由、身分驗證、回應格式與狀態碼。
    - **情境測試**：以記憶體資料庫（`mongomock-motor`）串接多次呼叫，找出單一端點 mock 看不出的問題（例如「更新是否真的寫入、下一次讀取能否看到」）。

  詳見 [`Backend/tests/README.md`](Backend/tests/README.md)。
- **前端**：
  - 元件與 composable 測試在 jsdom 中執行，Nuxt 的 auto-import 以 mock 取代。
  - 另有獨立的 **E2E 測試**：實際 build 並啟動 Nuxt 應用，再以真實的 headless 瀏覽器（Playwright）操作。涵蓋未登入的畫面；若 CI 有設定 Clerk 測試使用者，也會涵蓋真實的登入流程（以該使用者 email 對應的一次性 Clerk 登入 ticket 登入）。

在本機執行：

```bash
# 後端
cd Backend && pytest                   # 全部
cd Backend && pytest tests/unit        # 單元測試，速度快，不經過 HTTP
cd Backend && pytest tests/integration # 整合測試，經過 HTTP

# 前端
cd Frontend && npm run test       # 單元 / 元件測試
cd Frontend && npm run test:e2e   # 真實瀏覽器 E2E（前置條件見 Frontend/README.md）
```
