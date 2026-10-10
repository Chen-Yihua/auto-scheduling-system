from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from routers import user, linked_account, pr_review_webhook, manual_task, google_calendar, schedule
from platforms.router import platform_routers
from fastapi.middleware.cors import CORSMiddleware
import os
from core.logging_config import setup_logging
from core.database import ensure_indexes
from slowapi.errors import RateLimitExceeded
from core.rate_limit import limiter, rate_limit_exceeded_handler
from pymongo.errors import ConnectionFailure, PyMongoError
from core.exception_handlers import database_unavailable_handler, database_error_handler, UnhandledExceptionMiddleware


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

# CORS_ALLOWED_ORIGINS 以逗號分隔多個網域
def _get_allowed_origins() -> list[str]:
    origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


# 必須比 CORS 先註冊（在內層），500 回應才會帶 CORS 標頭
app.add_middleware(UnhandledExceptionMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
# pyright: ignore：Starlette 的型別只接受參數為 Exception 的 handler，傳子類別會誤報
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # pyright: ignore[reportArgumentType]

# Starlette 依繼承關係挑最具體的 handler，所以子類別 ConnectionFailure 會先被接住
app.add_exception_handler(ConnectionFailure, database_unavailable_handler)  # pyright: ignore[reportArgumentType]
app.add_exception_handler(PyMongoError, database_error_handler)  # pyright: ignore[reportArgumentType]

app.include_router(user.router)
app.include_router(linked_account.router)
app.include_router(pr_review_webhook.router)
app.include_router(google_calendar.router)
app.include_router(manual_task.router)
app.include_router(schedule.router)
# 外部平台的路由依 PLATFORMS 自動產生
for platform_router in platform_routers:
    app.include_router(platform_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 只用於本機開發
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )

