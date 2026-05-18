import asyncio
import logging
import os
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from auth import oauth2_scheme  # noqa: F401 — registers OAuth2 token URL in OpenAPI
from cache import count_cached_keys, ping_redis
from database import SessionLocal, engine, init_db
from escalation import run_escalation_check
from routers import (
    admin,
    approvals,
    auth,
    checkins,
    goals,
    notifications,
    reports,
    shared_goals,
)

load_dotenv()

logger = logging.getLogger("atomquest")
logging.basicConfig(level=logging.INFO)

ESCALATION_INTERVAL_SECONDS = 24 * 60 * 60


async def _escalation_scheduler() -> None:
    while True:
        await asyncio.sleep(ESCALATION_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            created = run_escalation_check(db)
            logger.info("Scheduled escalation check: %s new log(s)", created)
        except Exception as exc:
            logger.error("Scheduled escalation check failed: %s", exc)
            db.rollback()
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        created = run_escalation_check(db)
        logger.info("Startup escalation check: %s new log(s)", created)
    except Exception as exc:
        logger.error("Startup escalation check failed: %s", exc)
        db.rollback()
    finally:
        db.close()

    task = asyncio.create_task(_escalation_scheduler())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="AtomQuest Goal Portal",
    version="0.1.0",
    description="Goal management, check-ins, approvals, and analytics API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.error("[%s] Unhandled error on %s %s: %s", ts, request.method, request.url.path, exc)
    logger.debug(traceback.format_exc())
    is_dev = os.getenv("ENV", "development") == "development"
    detail = str(exc) if is_dev else "An unexpected error occurred. Please try again later."
    return JSONResponse(status_code=500, content={"detail": detail})


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("[%s] %s %s → %s (%sms)", ts, request.method, request.url.path, response.status_code, elapsed_ms)
    return response


if os.getenv("CORS_ALLOW_ALL", "").lower() in ("true", "1", "yes"):
    cors_origins = ["*"]
else:
    _default = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost"]
    _from_env = [
        origin.strip()
        for origin in os.getenv("atomquest-rho.vercel.app", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    cors_origins = list(dict.fromkeys(_default + _from_env))

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*","X-Demo-Mode"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(checkins.router, prefix="/api")
app.include_router(shared_goals.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(admin.public_router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")


@app.get("/", tags=["health"])
def root():
    return {"message": "AtomQuest Goal Portal API"}


@app.get("/health", tags=["health"])
def health():
    db_status = "disconnected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        pass

    redis_status = "connected" if ping_redis() else "disconnected"
    all_ok = db_status == "connected" and redis_status == "connected"

    return {
        "status": "ok" if all_ok else "degraded",
        "database": db_status,
        "redis": redis_status,
        "redis_keys_cached": count_cached_keys(),
    }
