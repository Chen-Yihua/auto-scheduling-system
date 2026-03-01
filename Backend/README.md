# 🧠 Auto-Scheduling Backend（FastAPI + MongoDB）

本專案為自動排程系統的後端伺服器，使用 [FastAPI](https://fastapi.tiangolo.com/) 搭配 MongoDB 開發，支援 RESTful API 與 Swagger 文件，並具備良好的擴充性與結構化設計。

---

## 📁 專案結構說明

```text

Backend/
├── main.py                  # FastAPI app 入口
├── requirements.txt         # 套件列表
├── .env                     # MongoDB 連線資訊
├── db/
│   └── mongodb.py           # Mongo 連線設定
├── schemas/
│   └── user.py              # Pydantic 資料結構（輸入/輸出）
├── crud/
│   └── user.py              # 使用者 CRUD 操作（封裝 DB 存取）
├── routers/
│   └── user.py              # API 路由（ex: /users）

```

## ⚙️ 安裝與啟動方式

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

```env
MONGO_URI=mongodb://localhost:27017
```

> 或使用 MongoDB Atlas 的連線字串也可，例如：
>
> ```env
> MONGO_URI=mongodb+srv://帳號:密碼@cluster.mongodb.net/?retryWrites=true&w=majority
> ```

### 4️. 啟動伺服器

```bash
uvicorn main:app --reload
```

打開瀏覽器 👉 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 Swagger UI 文件

### 🧪 測試連線

```bash
curl http://localhost:8000/health
```

或直接在瀏覽器打開 `http://localhost:8000/health`，若成功會顯示：

```json
{ "status": "ok" }
```

## 🧱 如何新增一個新的 Entity（以 Task 為例）

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
