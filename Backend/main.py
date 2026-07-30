from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from routers import user
from routers import user, linkedAccount, webhook, jira, manualTask, oauth ,moodle
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from routers import github
from logging_config import setup_logging
from db.mongodb import ensure_indexes


# 載入環境變數
load_dotenv()
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    yield


app = FastAPI(
    title="Auto Scheduling API",
    description="這是自排程系統的後端 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 設定
# 從環境變數讀白名單，本機開發預設放行 http://localhost:3000，正式環境用逗號分隔多個網域。
def _get_allowed_origins() -> list[str]:
    origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由註冊
app.include_router(user.router)
app.include_router(linkedAccount.router)
app.include_router(webhook.router)
app.include_router(oauth.router) 
app.include_router(jira.router)
app.include_router(manualTask.router)
app.include_router(github.router)
app.include_router(moodle.router)

# 健康檢查 endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Local development only
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,  # 注意這裡直接傳 app 物件，不是 "main:app"
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )

