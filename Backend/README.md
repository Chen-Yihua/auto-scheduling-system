# Auto-Scheduling Backend（FastAPI + MongoDB）

本專案為自動排程系統的後端伺服器，使用 [FastAPI](https://fastapi.tiangolo.com/) 搭配 MongoDB 開發，支援 RESTful API 與 Swagger 文件，並具備良好的擴充性與結構化設計。

---

## 需求

- **Python 3.11**（CI 與 Docker 部署都用這個版本）
- **MongoDB**：本機 `mongodb://localhost:27017`，或 MongoDB Atlas
- **Redis**（選用）：不設定就用記憶體，本機開發夠用
- **Chrome / Chromium**（選用）：只有要用 Moodle 帳號連結、作業同步時才需要，後端會用 Selenium 開 headless Chrome；正式環境的 Dockerfile 已內建

---

## 專案結構說明

```text
Backend/
├── main.py                  # FastAPI app 入口（掛路由、CORS、rate limiter、錯誤處理、啟動時建索引）
├── exception_handlers.py    # 集中處理錯誤：資料庫連線失敗回 503、其他資料庫錯誤回 500、沒預期的例外回 JSON 500
├── requirements.txt         # 套件列表
├── .env.example             # 環境變數範本（複製成 .env 並填值）
├── Dockerfile               # 正式環境用的 image（Cloud Run 部署用這個 build）
├── Dockerfile.test          # 在乾淨的容器裡跑 pytest（選用，CI 沒用到，見「用 Docker 跑測試」）
├── cache.py                 # 通用 TTL 快取（Redis，沒設定就退回記憶體）
├── rate_limit.py            # 流量限制（slowapi），key 用 Authorization header 雜湊
├── logging_config.py        # logging 設定
├── db/
│   ├── mongodb.py           # Mongo 連線設定、啟動時建索引（ensure_indexes）
│   ├── security.py          # 驗證 Clerk JWT
│   └── crypto.py            # 第三方帳密加解密/遮罩
├── schemas/                 # Pydantic 資料結構（輸入/輸出，每個資源分開定義）
├── crud/                    # 商業邏輯、資料庫讀寫、串第三方 API
│   └── external_sync.py     # GitHub/Jira/Moodle 共用的「即時抓+失敗退回舊資料」同步邏輯
├── services/
│   └── google_calendar.py   # Google Calendar API 的封裝
├── constants/               # 純資料常數（例如 LLM prompt 模板）
├── routers/                 # API 路由層，只管 HTTP、驗證、rate limit
└── tests/                   # pytest：unit/（不碰 HTTP）與 integration/（走 HTTP），見下方「測試」
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

### 錯誤處理

- 預期中的錯誤（查無資料、沒權限…）在 crud / router 裡直接 `raise HTTPException(...)`。
- **資料庫連不上不用自己 try/except**，讓例外往外丟，由 `exception_handlers.py` 統一回應：連線類錯誤回 **503**，其他資料庫錯誤回 **500**。
- 沒被接住的程式錯誤，由兜底 middleware 回固定訊息的 JSON 500（帶 CORS 標頭，前端才看得到真正的狀態碼），詳細內容只寫進 log，不回傳給前端。

---

## 安裝與啟動方式

### 1. 建立虛擬環境

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

### 2. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 3. 建立 `.env` 檔案

複製 `.env.example` 成 `Backend/.env`，把值填齊：

```env
# 【必填】Clerk（身分驗證）：沒設定，伺服器啟動時會直接報錯。要跟前端用同一個 Clerk 專案
CLERK_ISSUER=
CLERK_JWKS_URL=

# 【必填】Gemini（任務優先度/時長推斷、PR 摘要機器人）
GEMINI_API_KEY=

# 加密第三方帳密用的金鑰，用這行產生：
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SECRET_ENCRYPTION_KEY=

# MongoDB。不設定時預設 mongodb://localhost:27017 與資料庫 auto_scheduling_db；
# 用 MongoDB Atlas 就填連線字串：mongodb+srv://帳號:密碼@cluster.mongodb.net/...
MONGO_URI=
MONGO_DB=

# Google Calendar OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=

# CORS 白名單，逗號分隔，不設定預設只放行 http://localhost:3000
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Clerk Dashboard > Webhooks 給的 Signing Secret（whsec_ 開頭），用來驗證 /users/webhook/clerk。
# 不設定就一律回 401；本機沒有要測 Clerk webhook 可以留空
CLERK_WEBHOOK_SIGNING_SECRET=

# 以下四個是 GitHub PR 摘要機器人用的，本機開發沒有要測這個功能可以留空
DISCORD_MR_WEBHOOK_URL=
DISCORD_MAIN_WEBHOOK_URL=
GITHUB_WEBHOOK_SECRET=
GITHUB_BOT_TOKEN=

# Redis，不設定就用記憶體（本機開發/單一 instance 夠用）；
# 設定後自動改用 Redis 做流量限制的計數跟快取的共用儲存
REDIS_URL=

# 日誌等級（DEBUG / INFO / WARNING / ERROR），不設定預設 INFO
LOG_LEVEL=INFO
```

### 4. 啟動伺服器

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

---

## 如何新增一個新的 Entity（以 Note 為例）

新增一個資料實體要 5 步：Schema → CRUD → Router → 註冊 → 測試。

### 1. Schema（`schemas/note.py`）

```python
from pydantic import BaseModel

class NoteCreate(BaseModel):
    title: str
    content: str

class NoteOut(NoteCreate):
    id: str
    user_id: str
```

### 2. CRUD 操作（`crud/note.py`）

```python
from uuid import uuid4
from db.mongodb import db
from schemas.note import NoteCreate

async def create_note(user_id: str, note: NoteCreate) -> dict:
    doc = {"id": str(uuid4()), "user_id": user_id, **note.model_dump()}
    await db.notes.insert_one(doc)
    doc.pop("_id", None)  # insert_one 會把 Mongo 的 _id 塞進 doc，不要回傳出去
    return doc
```

資料庫連不上不用在這裡 `try/except`，見上方「錯誤處理」。

### 3. 路由（`routers/note.py`）

```python
from fastapi import APIRouter, Depends
from crud import note as note_crud
from db.security import get_current_clerk_user
from schemas.note import NoteCreate, NoteOut

router = APIRouter(prefix="/notes", tags=["notes"])

@router.post("/", response_model=NoteOut)
async def create_note(note: NoteCreate, clerk_user: dict = Depends(get_current_clerk_user)):
    # 擁有者一律用登入者本人的 id，不接受前端指定
    return await note_crud.create_note(clerk_user["sub"], note)
```

### 4. 註冊到 `main.py`

```python
from routers import note
app.include_router(note.router)
```

### 5. 寫測試

- `tests/unit/test_note_crud.py`：直接呼叫 crud 函式，測每個分岔。
- `tests/integration/test_note_api.py`：走 HTTP，測路由、登入驗證、回應格式。
- **只要有「使用者只能動自己的資料」的規則，一定要測「使用者 B 存取使用者 A 的資料會被擋」**。這種規則很容易漏測，拿掉也不會有其他測試失敗。

規則與範例見 [`tests/README.md`](tests/README.md)。

---

## 測試

```bash
pytest                                     # 全部測試
pytest --cov=. --cov-report=term-missing   # 含覆蓋率（CI 用這個）
pytest tests/unit                          # 只跑單元測試（幾秒內跑完，開發時常跑）
pytest tests/integration                   # 只跑走 HTTP 的測試
```

測試依「有沒有走 HTTP」分成兩個資料夾（詳細規則見 [`tests/README.md`](tests/README.md)）：

- **單元測試**（`tests/unit/`）：不碰 HTTP，直接呼叫函式，資料庫、外部 API 都 mock 掉，測邏輯對不對。
- **API 測試**（`tests/integration/test_*_api.py`）：走 HTTP 打 endpoint，確認路由、登入驗證、回應格式都接對了。
- **端對端情境測試**（`tests/integration/test_*_scenario.py`）：不 mock 資料庫，用 `mongomock-motor`（假的、但支援 async/await 的 MongoDB）串好幾個真的 HTTP 呼叫，驗證「上一步寫的資料，下一步真的讀得到、也真的反映更新」——例如建立任務 → 列表看得到 → 編輯 → 確認更新落地 → 刪除 → 確認查不到。

### 用 Docker 跑測試（選用）

`Dockerfile.test` 是想在**乾淨的 Linux 容器**裡跑 `pytest` 時用的映像，跟部署用的 `Dockerfile` 是分開的。目前**沒有任何 CI 使用它**（GitHub Actions 直接在 runner 上執行 `pytest`），只有想在本機複驗時才需要：

```bash
cd Backend
docker build -f Dockerfile.test -t backend-test .
docker run --rm \
  -e CLERK_ISSUER=https://fake.clerk.dev \
  -e CLERK_JWKS_URL=https://fake.clerk.dev/.well-known/jwks.json \
  backend-test
```

注意：

- 容器裡**一定要帶 `CLERK_ISSUER` 和 `CLERK_JWKS_URL`**，沒帶的話所有測試在載入階段就會報 `Missing environment variable`。測試不會真的連 Clerk，填假的網址就可以（`GEMINI_API_KEY` 等其他變數，測試會自己補預設值）。
- 這個映像用 Python 3.13，CI 和正式環境是 3.11。
- 專案目前沒有 `.dockerignore`，`COPY . .` 會把本機的 `Backend/.env` 也複製進映像，**不要把這個映像推送到任何 registry**。

> 如果要新增會真的碰資料庫（不整個 mock 掉）的測試，資料庫 fixture 一定要用 `mongomock_motor.AsyncMongoMockClient`（見 `tests/conftest.py`），不能用純同步的 `mongomock.MongoClient()`——後者對 `await` 出來的結果會直接噴 `TypeError`，而且不會在「有 mock 掉」的測試裡被發現。
