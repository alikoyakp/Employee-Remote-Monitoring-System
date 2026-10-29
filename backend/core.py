import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone

import requests
from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.concurrency import run_in_threadpool

try:
    from backend.clerk_auth import require_user
except ModuleNotFoundError:
    from clerk_auth import require_user

logger = logging.getLogger("workpulse")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

ROLES = ["admin", "manager", "employee"]
DEFAULT_ROLE = "employee"
ENV = "live" if os.environ.get("CLERK_PUBLISHABLE_KEY", "").startswith("pk_live_") else "preview"
APP_NAME = "workpulse"

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
        "captured by the WorkPulse desktop agent. Monitoring stops when you clock out or take a break. "
        "Screenshots are visible only to administrators and your reporting manager and are deleted automatically."
    ),
}
SENSITIVE = {"_id", "agent_token_hash"}


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


def _admin_emails():
    return {e.strip().lower() for e in os.environ.get("ADMIN_EMAIL", "").split(",") if e.strip()}


def _clerk_profile(user_id):
    r = requests.get(f"https://api.clerk.com/v1/users/{user_id}", timeout=10,
                     headers={"Authorization": f"Bearer {os.environ['CLERK_SECRET_KEY']}", "User-Agent": "emergent-app"})
    r.raise_for_status()
    data = r.json()
    emails = [e["email_address"].lower() for e in data.get("email_addresses", [])
              if (e.get("verification") or {}).get("status") == "verified"]
    name = " ".join(x for x in [data.get("first_name"), data.get("last_name")] if x) or (emails[0].split("@")[0] if emails else "Admin")
    return emails, name


async def _link_employee(uid):
    emails, name = await run_in_threadpool(_clerk_profile, uid)
    admin_email = next((e for e in emails if e in _admin_emails()), None)
    emp = await db.employees.find_one({"email": {"$in": emails}, "clerk_user_id": {"$in": [None, ""]}}, {"_id": 0})
    if emp:
        update = {"clerk_user_id": uid, "env": ENV}
        if admin_email:
            update["role"] = "admin"
        await db.employees.update_one({"id": emp["id"]}, {"$set": update})
        await audit({**emp, **update}, "auth.account_linked", "employee", emp["id"], {"email": emp["email"]})
        return {**emp, **update}
    if admin_email:
        emp = {
            "id": new_id(), "employee_id": f"ADMIN-{uuid.uuid4().hex[:4].upper()}", "full_name": name,
            "email": admin_email, "department_id": None, "designation": "Administrator", "manager_id": None,
            "working_schedule": "Mon-Fri 09:00-18:00", "timezone": "UTC", "role": "admin", "status": "active",
            "screenshots_enabled": False, "clerk_user_id": uid, "env": ENV, "created_at": now(),
        }
        await db.employees.insert_one(dict(emp))
        emp.pop("_id", None)
        await audit(emp, "auth.admin_bootstrapped", "employee", emp["id"], {"email": admin_email})
        return emp
    raise HTTPException(status_code=403, detail="not_registered")


async def current_member(user: dict = Depends(require_user)) -> dict:
    uid = user["user_id"]
    emp = await db.employees.find_one({"clerk_user_id": uid}, {"_id": 0})
    if emp is None:
        emp = await _link_employee(uid)
    if emp.get("status") == "inactive":
        raise HTTPException(status_code=403, detail="account_inactive")
    if emp.get("env") != ENV:
        await db.employees.update_one({"id": emp["id"]}, {"$set": {"env": ENV}})
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
