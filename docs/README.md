# 文件

| 文件 | 內容 | 什麼時候要更新 |
|---|---|---|
| [architecture.md](architecture.md) | 系統由哪些部分組成、資料怎麼流動 | 新增服務、資料庫 collection、外部平台，或改變模組分層 |
| [architecture.drawio](architecture.drawio) | 系統架構圖（用 draw.io 開啟） | 同上 |
| [api.md](api.md) | 後端 API 一覽 | 新增、刪除 endpoint，或改了路徑、登入需求、限流 |
| [decisions/](decisions/) | 架構決策紀錄（ADR）：為什麼這樣做、放棄了什麼 | 做了之後的人會想問「為什麼不用 X」的決定 |
| [specs/](specs/) | 功能規格：需求、假設、驗收條件與修改紀錄 | 每個用 `/feature` 開發的功能一份；驗收條件有任何修改都要同步更新 |
| [reviews/](reviews/) | 每一輪審查的報告與處理結果 | 每輪審查完存一份，處理完補上處理結果 |
| [experiments/](experiments/) | 開發流程的實驗：目的、指標與紀錄 | 開始新的流程實驗，或實驗結束整理結果時 |

欄位層級的 request / response 格式以後端的 `backend/schemas/` 和 FastAPI 自動產生的 `/docs` 為準，這裡不重複列。
