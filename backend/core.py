import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import requests
from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("erm")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

ROLES = ["admin", "manager", "employee"]
DEFAULT_ROLE = "employee"
APP_NAME = "workpulse"
JWT_ALG = "HS256"
ACCESS_MIN = 15
REFRESH_DAYS = 7

DEFAULT_SETTINGS = {
    "idle_threshold_min": 5,
    "screenshot_interval_min": 60,
    "screenshot_retention_days": 30,
    "activity_retention_days": 180,
    "offline_after_min": 5,
    "auto_close_after_min": 30,
    "monitoring_notice": (
        "This organisation monitors work activity while you are clocked in. We record login/logout times, "
        "counts of mouse movements, clicks and key presses (never the keys you type, passwords or content), "
        "idle and break time, and - only if enabled by an administrator for your account - periodic screenshots "
        "captured by the ERM System desktop agent. Monitoring stops when you clock out or take a break. "
        "Screenshots are visible only to administrators and your reporting manager and are deleted automatically."
    ),
}
SENSITIVE = {"_id", "agent_token_hash", "password_hash", "clerk_user_id"}


def now():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid.uuid4())


def aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def clean(doc):
    if isinstance(doc, list):
        return [clean(d) for d in doc]
    if isinstance(doc, dict):
        return {k: clean(v) for k, v in doc.items() if k not in SENSITIVE}
    if isinstance(doc, datetime):
        return aware(doc).isoformat()
    return doc


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain, hashed):
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(emp, kind):
    exp = now() + (timedelta(minutes=ACCESS_MIN) if kind == "access" else timedelta(days=REFRESH_DAYS))
    payload = {"sub": emp["id"], "type": kind, "pv": emp.get("password_version", 0), "exp": exp}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALG)


async def employee_from_token(token, kind):
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session")
    if payload.get("type") != kind:
        raise HTTPException(status_code=401, detail="Invalid session")
    emp = await db.employees.find_one({"id": payload["sub"]}, {"_id": 0})
    if not emp or emp.get("password_version", 0) != payload.get("pv"):
        raise HTTPException(status_code=401, detail="Session no longer valid")
    if emp.get("status") == "inactive":
        raise HTTPException(status_code=401, detail="Account deactivated")
    return emp


async def get_settings():
    doc = await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    return {**DEFAULT_SETTINGS, **{k: v for k, v in doc.items() if k in DEFAULT_SETTINGS}}


async def audit(actor, action, target_type="", target_id="", details=None):
    await db.audit_logs.insert_one({
        "id": new_id(), "ts": now(),
        "actor_id": (actor or {}).get("id", "system"),
        "actor_name": (actor or {}).get("full_name", "System"),
        "actor_role": (actor or {}).get("role", "system"),
        "action": action, "target_type": target_type, "target_id": target_id or "",
        "details": details or {},
    })


async def current_member(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
    emp = await employee_from_token(token, "access")
    emp["role"] = emp.get("role") if emp.get("role") in ROLES else DEFAULT_ROLE
    return emp


def require_role(*roles):
    async def check(member: dict = Depends(current_member)) -> dict:
        if member["role"] not in roles:
            raise HTTPException(status_code=403, detail="Not allowed")
        return member
    return check


async def visible_ids(member):
    """None = everyone (admin); else list of employee ids the caller may see."""
    if member["role"] == "admin":
        return None
    if member["role"] == "manager":
        reports = await db.employees.find({"manager_id": member["id"]}, {"_id": 0, "id": 1}).to_list(5000)
        return [member["id"]] + [r["id"] for r in reports]
    return [member["id"]]


async def ensure_visible(member, employee_id):
    ids = await visible_ids(member)
    if ids is not None and employee_id not in ids:
        raise HTTPException(status_code=404, detail="Employee not found")


async def agent_member(request: Request) -> dict:
    token = request.headers.get("x-agent-token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Missing agent token")
    emp = await db.employees.find_one({"agent_token_hash": hash_token(token)}, {"_id": 0})
    if not emp or emp.get("status") == "inactive":
        raise HTTPException(status_code=401, detail="Invalid agent token")
    await db.employees.update_one({"id": emp["id"]}, {"$set": {"agent_last_used_at": now()}})
    return emp


# Object storage (private screenshots)
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
_storage_key = None


def init_storage(force=False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path, data, content_type):
    resp = requests.put(f"{STORAGE_URL}/objects/{path}", data=data, timeout=120,
                        headers={"X-Storage-Key": init_storage(), "Content-Type": content_type})
    if resp.status_code == 404:
        resp = requests.put(f"{STORAGE_URL}/objects/{path}", data=data, timeout=120,
                            headers={"X-Storage-Key": init_storage(force=True), "Content-Type": content_type})
    resp.raise_for_status()
    return resp.json()


def get_object(path):
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage()}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
