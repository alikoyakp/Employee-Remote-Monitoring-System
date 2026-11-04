import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from clerk_auth import clerk_router  # noqa: E402
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


for r in (clerk_router, routes_org.router, importer.router, tracking.router, reports.router):
    app.include_router(r)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
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
    await seed_sample_data()
    try:
        await run_in_threadpool(init_storage)
        logger.info("Storage initialized")
    except Exception as e:
        logger.error("Storage init failed: %s", e)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
