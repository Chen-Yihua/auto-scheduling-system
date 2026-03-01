# Auto-Scheduling Backend（FastAPI + MongoDB）

Backend service for the Auto-Scheduling System, built with FastAPI and MongoDB.  
This service provides RESTful APIs for task management and third-party integrations.

---

## Tech Stack

- FastAPI
- MongoDB
- Pydantic
- Docker
- Pytest

---

## Project Structure

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

---

## Installation

### 1️. Create virtual environment

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

### 2️. Install dependencies

```bash
pip install -r requirements.txt
```

### 3️. Create .env file

```env
MONGO_URI=mongodb://localhost:27017
```

> 或使用 MongoDB Atlas 的連線字串也可，例如：
>
> ```env
> MONGO_URI=mongodb+srv://帳號:密碼@cluster.mongodb.net/?retryWrites=true&w=majority
> ```

### 4️. Run the server

```bash
uvicorn main:app --reload
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs) 

### Health Check

```bash
curl http://localhost:8000/health
```

或直接在瀏覽器打開 `http://localhost:8000/health`，若成功會顯示：

```json
{ "status": "ok" }
```

