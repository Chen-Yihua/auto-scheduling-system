# Auto-Scheduling Backend（FastAPI + MongoDB）

本專案為自動排程系統的後端伺服器，使用 [FastAPI](https://fastapi.tiangolo.com/) 搭配 MongoDB 開發，支援 RESTful API 與 Swagger 文件，並具備良好的擴充性與結構化設計。

---

## 專案結構說明

```text

Backend/
├── main.py                  # FastAPI app 入口（掛路由、CORS、rate limiter、啟動時建索引）
├── requirements.txt         # 套件列表
├── .env.example             # 所有需要的環境變數（複製成 .env 並填值）
├── Dockerfile                # 正式環境用的 image（Cloud Run 部署用這個 build）
├── cache.py                  # 通用 TTL 快取（Redis，沒設定就退回記憶體）
├── rate_limit.py              # 流量限制（slowapi），key 用 Authorization header 雜湊
├── logging_config.py          # logging 設定
├── db/
│   ├── mongodb.py            # Mongo 連線設定、啟動時建索引（ensure_indexes）
│   ├── security.py           # 驗證 Clerk JWT
│   └── crypto.py              # 第三方帳密加解密/遮罩
├── schemas/                  # Pydantic 資料結構（輸入/輸出，每個資源分開定義）
├── crud/                     # 商業邏輯、資料庫讀寫、串第三方 API
│   └── external_sync.py       # GitHub/Jira/Moodle 共用的「即時抓+失敗退回舊資料」同步邏輯
├── services/
│   └── google_calendar.py     # Google Calendar API 的封裝
├── constants/                 # 純資料常數（例如 LLM prompt 模板）
├── routers/                  # API 路由層，只管 HTTP、驗證、rate limit
└── tests/                    # pytest（單元測試 + 端對端情境測試，見下方「測試」）

```

### 目前有的路由

| Router | 對應功能 |
|---|---|
| `users` | 使用者資料、Clerk webhook |
| `linkedAccount` | 連結 GitHub/Jira/Moodle 帳號（含驗證、加密） |
| `manualTask` | 手動任務 CRUD，缺 priority/duration 時用 Gemini 推斷 |
| `github` / `jira` / `moodle` | 第三方平台資料同步（即時抓 + fallback） |
| `oauth` | Google Calendar 授權、空閒時段查詢 |
| `schedule` | 排程建議 |
| `webhook` | GitHub PR 摘要機器人（Gemini + Discord），跟使用者功能無關，是這個 repo 自己開發流程用的 |

## 安裝與啟動方式

### 1️. 建立虛擬環境

#### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 2️. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 3️. 建立 `.env` 檔案

複製 `.env.example` 成 `.env`，把值填齊：

```env
# Clerk（身分驗證，兩邊都要）
CLERK_ISSUER=
CLERK_JWKS_URL=
CLERK_SECRET_KEY=

# MongoDB，本機開發用 mongodb://localhost:27017，
# 或用 MongoDB Atlas 的連線字串：mongodb+srv://帳號:密碼@cluster.mongodb.net/...
MONGO_URI=

# Gemini（任務優先度/時長推斷、PR 摘要機器人）
GEMINI_API_KEY=

# Google Calendar OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=

# 加密第三方帳密用的金鑰，用這行產生：
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SECRET_ENCRYPTION_KEY=

# CORS 白名單，逗號分隔，不設定預設只放行 http://localhost:3000
CORS_ALLOWED_ORIGINS=http://localhost:3000

# 以下三個是 GitHub PR 摘要機器人用的，本機開發沒有要測這個功能可以留空
DISCORD_MR_WEBHOOK_URL=
DISCORD_MAIN_WEBHOOK_URL=
GITHUB_WEBHOOK_SECRET=
GITHUB_BOT_TOKEN=

# Redis，不設定就用記憶體（本機開發/單一 instance 夠用）；
# 設定後自動改用 Redis 做流量限制的計數跟快取的共用儲存
REDIS_URL=
```

### 4️. 啟動伺服器

```bash
uvicorn main:app --reload
```

打開瀏覽器 👉 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 Swagger UI 文件

### 測試連線

```bash
curl http://localhost:8000/health
```

或直接在瀏覽器打開 `http://localhost:8000/health`，若成功會顯示：

```json
{ "status": "ok" }
```

## 如何新增一個新的 Entity（以 Task 為例）

新增一個資料實體只需要以下 4 步：

### 1. Schema（`schemas/task.py`）

```python
from pydantic import BaseModel

class TaskCreate(BaseModel):
    title: str
    deadline: str

class TaskInDB(TaskCreate):
    id: str
```

---

### 2. CRUD 操作（`crud/task.py`）

```python
from db.mongodb import db
from schemas.task import TaskCreate
from bson import ObjectId

async def insert_task(task: TaskCreate):
    result = await db.tasks.insert_one(task.dict())
    return str(result.inserted_id)
```

---

### 3. 路由（`routers/task.py`）

```python
from fastapi import APIRouter
from crud import task as task_crud
from schemas.task import TaskCreate

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/create")
async def create_task(task: TaskCreate):
    return {"id": await task_crud.insert_task(task)}
```

### 4. Router 加入 `main.py`

```python
from routers import task
app.include_router(task.router)
```

## 測試

```bash
pytest                              # 全部測試
pytest --cov=. --cov-report=term-missing   # 含覆蓋率（CI 用這個）
```

測試依「有沒有走 HTTP」分成兩個資料夾（詳細規則見 `tests/README.md`）：
```bash
pytest tests/unit          # 單元測試：不碰 HTTP，直接呼叫函式，資料庫、外部 API 都 mock 掉
pytest tests/integration   # 整合 / API 測試：用 AsyncClient 打 endpoint
```
- **單元測試**（`tests/unit/`）：每個函式各自把資料庫、外部 API mock 掉，測邏輯對不對。
- **API 測試**（`tests/integration/test_*_api.py`）：走 HTTP 打 endpoint，確認路由、登入驗證、回應格式都接對了。
- **端對端情境測試**（`tests/integration/test_*_scenario.py`）：不 mock 資料庫，用 `mongomock-motor`（假的、但支援 async/await 的 MongoDB）串好幾個真的 HTTP 呼叫，驗證「上一步寫的資料，下一步真的讀得到、也真的反映更新」——例如建立任務 → 列表看得到 → 編輯 → 確認更新落地 → 刪除 → 確認查不到。

> 如果要新增會真的碰資料庫（不整個 mock 掉）的測試，資料庫 fixture 一定要用 `mongomock_motor.AsyncMongoMockClient`（見 `tests/conftest.py`），不能用純同步的 `mongomock.MongoClient()`——後者對 `await` 出來的結果會直接噴 `TypeError`，而且不會在「有 mock 掉」的測試裡被發現。
