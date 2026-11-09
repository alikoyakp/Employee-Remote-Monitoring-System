import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

import auth  # noqa: E402
from core import client, db, init_storage  # noqa: E402
import importer  # noqa: E402
import reports  # noqa: E402
import routes_org  # noqa: E402
import tracking  # noqa: E402
from seed import seed_sample_data  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ERM System API")


@app.get("/api/health")
async def health():
    return {"ok": True}


for r in (auth.router, routes_org.router, importer.router, tracking.router, reports.router):
    app.include_router(r)

ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    # Cookie sessions use SameSite=None, so reject state-changing requests from unknown origins.
    # CORS_ORIGINS="*" (preview/dev only) disables this check; production must list explicit origins.
    origin = request.headers.get("origin")
    has_session = request.cookies.get("access_token") or request.cookies.get("refresh_token")
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and origin and has_session and "*" not in ORIGINS:
        host = (request.headers.get("x-forwarded-host") or request.headers.get("host", "")).split(",")[0].strip()
        if origin.split("://", 1)[-1] != host and origin not in ORIGINS:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.employees.create_index("id", unique=True)
    await db.employees.create_index("employee_id")
    await db.employees.create_index("email")
    await db.employees.create_index("clerk_user_id")
    await db.employees.create_index("agent_token_hash")
    await db.departments.create_index("id", unique=True)
    await db.sessions.create_index([("employee_id", 1), ("status", 1)])
    await db.sessions.create_index("start")
    await db.breaks.create_index([("employee_id", 1), ("end", 1)])
    await db.activity.create_index([("employee_id", 1), ("minute", 1)], unique=True)
    await db.activity.create_index([("employee_id", 1), ("day", 1)])
    await db.screenshots.create_index([("employee_id", 1), ("taken_at", -1)])
    await db.audit_logs.create_index([("ts", -1)])
    await db.imports.create_index([("created_at", -1)])
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("updated_at", expireAfterSeconds=86400)
    await db.password_tokens.create_index("token_hash")
    await db.password_tokens.create_index("expires_at", expireAfterSeconds=30 * 86400)
    await seed_sample_data()
    await auth.seed_admins()
    try:
        await run_in_threadpool(init_storage)
        logger.info("Storage initialized")
    except Exception as e:
        logger.error("Storage init failed: %s", e)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
