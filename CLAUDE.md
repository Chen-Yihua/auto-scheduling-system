# CLAUDE.md

專案介紹、架構與安裝方式見 [README.md](README.md)。這份只寫在這個 repo 動手時一定要遵守的規則。

## 完成的定義

改完程式後，依改到的範圍跑下面的檢查，全部通過才算完成。

```bash
# 後端（從 repo 根目錄先 source .venv/bin/activate）
cd backend && pyright && pytest

# 前端
cd frontend && npm run lint && npm run test
```

- 前端目前沒有型別檢查（專案沒裝 `vue-tsc`，CI 也不跑）。改到型別相關的程式碼時，要在回報中說明型別沒有經過工具驗證。
- 新行為要有對應的測試；修 bug 要補對應的回歸測試。
- 測試失敗時，修程式碼，不是改測試去配合錯誤的行為；確定是測試本身寫錯，才改測試並說明理由。

## 做這類任務前先讀

| 任務 | 文件 |
|---|---|
| 寫或修改後端測試 | [backend/tests/README.md](backend/tests/README.md)（測試放哪個檔、`_api.py` 結構、docstring 寫法） |
| 後端錯誤處理、丟例外 | [backend/README.md](backend/README.md)「錯誤處理」 |
| 新增後端 entity / 外部平台 | [backend/README.md](backend/README.md)「如何新增一個新的 Entity」「如何新增外部平台」 |
| 新增後端套件 | [backend/README.md](backend/README.md)「安裝依賴套件」（正式用 vs 測試用分兩個檔） |
| 前端元件、composable、頁面 | [frontend/README.md](frontend/README.md)「開發慣例」 |

## 跨前後端的連動

- 改了 `backend/schemas/` 的回應格式，要同步改 `frontend/types/`（手動維護，不會自動產生）。
- 新增「import 時就必填」的環境變數，要同步更新 `.github/workflows/deploy.yml`、`backend/.env.example`，以及 `backend/tests/unit/test_ci_env_requirements.py`。

## 測試範圍

只寫以下測試：真實行為、商業規則、發生過或可能發生的 bug。不要為了衝覆蓋率去測 UI 開關、不會走到的防禦分支、很薄的包裝元件。被要求提高覆蓋率時，先排除設定檔、types、自動產生的檔案，剩下沒覆蓋的照實說明為什麼不值得測。

## 註解

讀者是團隊裡的其他開發者。預設不寫註解，只有讀者會看不懂、或可能把它「簡化」成錯的寫法時，才寫一行說明原因，例如 `不用 X：原因`。

- 不要重述程式碼在做什麼，不要寫重複函式名稱的段落標題，不要寫修改歷史。
- 因果要寫清楚，不要讓人分不出哪個是原因、哪個是結果。
- 模組 docstring 只寫這個檔案做什麼，不提其他檔案。
- 註解與文件用繁體中文。

## 共用的開發環境

開發者通常同時開著自己的 `npm run dev`，以及正在編輯同一批檔案的 VS Code。

- dev server 可能開著時，不要跑 `npm run build`、`nuxi build`、`npm run test:e2e`，也不要刪 `.nuxt` / `.output`：它們會改寫 `.nuxt`，弄壞 dev server。`eslint`、`vitest` 可以跑。
- 要起臨時 dev server 前，先用 `ps` 確認有沒有 `nuxt dev` 在跑；有的話不要再起一個共用同一個 `.nuxt` 的。
- 停掉臨時 server 時只砍自己起的那個 PID，不要用 `pkill` 或對 `nuxi`、`node` 這類通用名稱 grep 再 kill。
- 改了開發者在編輯器開著的檔案，之後要從磁碟重讀，確認修改沒被編輯器存檔蓋掉，並提醒開發者重新載入 buffer。
