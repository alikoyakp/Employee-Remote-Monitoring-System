import os
import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from core import (audit, aware, create_token, current_member, db, employee_from_token, hash_password, hash_token,
                  logger, new_id, now, require_role, verify_password)

router = APIRouter(prefix="/api/auth")
MAX_ATTEMPTS = 5
LOCK_MIN = 15
LINK_HOURS = 72
COOKIE = {"httponly": True, "secure": True, "samesite": "none", "path": "/"}


class LoginIn(BaseModel):
    email: str
    password: str


class SetPasswordIn(BaseModel):
    token: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


def check_strength(pw):
    if len(pw) < 8 or pw.isalpha() or pw.isdigit():
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters and include a number or symbol")


def set_session(response, emp):
    response.set_cookie("access_token", create_token(emp, "access"), max_age=15 * 60, **COOKIE)
    response.set_cookie("refresh_token", create_token(emp, "refresh"), max_age=7 * 86400, **COOKIE)


def _ip(request):
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.strip().lower()
    ident = f"{_ip(request)}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until") and aware(att["locked_until"]) > now():
        raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {LOCK_MIN} minutes.")
    emp = await db.employees.find_one({"email": email, "status": {"$ne": "inactive"}}, {"_id": 0})
    if not emp or not emp.get("password_hash") or not verify_password(body.password, emp["password_hash"]):
        count = (att or {}).get("count", 0) + 1
        upd = {"count": count, "updated_at": now()}
        if count >= MAX_ATTEMPTS:
            upd.update(count=0, locked_until=now() + timedelta(minutes=LOCK_MIN))
        await db.login_attempts.update_one({"identifier": ident}, {"$set": upd}, upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password. New here? Ask your administrator for a login link.")
    await db.login_attempts.delete_one({"identifier": ident})
    await db.employees.update_one({"id": emp["id"]}, {"$set": {"last_login_at": now()}})
    await audit(emp, "auth.login", "employee", emp["id"])
    set_session(response, emp)
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", **COOKIE)
    response.delete_cookie("refresh_token", **COOKIE)
    return {"ok": True}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
    emp = await employee_from_token(token, "refresh")
    response.set_cookie("access_token", create_token(emp, "access"), max_age=15 * 60, **COOKIE)
    return {"ok": True}


async def _apply_password(emp, password):
    pv = emp.get("password_version", 0) + 1
    await db.employees.update_one({"id": emp["id"]}, {"$set": {"password_hash": hash_password(password), "password_version": pv, "password_set_at": now()}})
    return {**emp, "password_version": pv}


@router.post("/set-password")
async def set_password(body: SetPasswordIn, response: Response):
    check_strength(body.password)
    link = await db.password_tokens.find_one({"token_hash": hash_token(body.token), "used": False})
    if not link or aware(link["expires_at"]) < now():
        raise HTTPException(status_code=400, detail="This link is invalid or has expired. Ask your administrator for a new one.")
    emp = await db.employees.find_one({"id": link["employee_id"], "status": {"$ne": "inactive"}}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=400, detail="This account is no longer active")
    emp = await _apply_password(emp, body.password)
    await db.password_tokens.update_many({"employee_id": emp["id"], "used": False}, {"$set": {"used": True, "used_at": now()}})
    await audit(emp, "auth.password_set", "employee", emp["id"])
    set_session(response, emp)
    return {"ok": True}


@router.get("/link-info")
async def link_info(token: str):
    link = await db.password_tokens.find_one({"token_hash": hash_token(token), "used": False})
    if not link or aware(link["expires_at"]) < now():
        raise HTTPException(status_code=400, detail="This link is invalid or has expired. Ask your administrator for a new one.")
    emp = await db.employees.find_one({"id": link["employee_id"]}, {"_id": 0, "full_name": 1, "email": 1})
    return {"full_name": emp["full_name"], "email": emp["email"]}


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, response: Response, member: dict = Depends(current_member)):
    emp = await db.employees.find_one({"id": member["id"]}, {"_id": 0})
    if not emp.get("password_hash") or not verify_password(body.current_password, emp["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    check_strength(body.new_password)
    emp = await _apply_password(emp, body.new_password)
    await audit(member, "auth.password_changed", "employee", member["id"])
    set_session(response, emp)
    return {"ok": True}


@router.post("/password-link/{emp_id}")
async def create_password_link(emp_id: str, admin: dict = Depends(require_role("admin"))):
    emp = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.get("status") == "inactive":
        raise HTTPException(status_code=400, detail="Activate this employee first")
    token = secrets.token_urlsafe(32)
    await db.password_tokens.update_many({"employee_id": emp_id, "used": False}, {"$set": {"used": True, "used_at": now()}})
    await db.password_tokens.insert_one({"id": new_id(), "token_hash": hash_token(token), "employee_id": emp_id, "used": False,
                                         "created_by": admin["id"], "created_at": now(), "expires_at": now() + timedelta(hours=LINK_HOURS)})
    await audit(admin, "auth.password_link_created", "employee", emp_id, {"reset": bool(emp.get("password_hash"))})
    return {"path": f"/set-password?token={token}", "expires_hours": LINK_HOURS}


async def seed_admins():
    """Create (or give a first password to) ADMIN_EMAIL accounts. Never overwrites an existing password."""
    password = os.environ.get("ADMIN_PASSWORD", "")
    for email in [e.strip().lower() for e in os.environ.get("ADMIN_EMAIL", "").split(",") if e.strip()]:
        emp = await db.employees.find_one({"email": email}, {"_id": 0})
        if emp is None:
            await db.employees.insert_one({
                "id": new_id(), "employee_id": f"ADMIN-{uuid.uuid4().hex[:4].upper()}", "full_name": email.split("@")[0],
                "email": email, "department_id": None, "designation": "Administrator", "manager_id": None,
                "working_schedule": "Mon-Fri 09:00-18:00", "timezone": "UTC", "role": "admin", "status": "active",
                "screenshots_enabled": False, "created_at": now(),
                **({"password_hash": hash_password(password), "password_version": 1} if password else {})})
            logger.info("Seeded admin %s", email)
        else:
            upd = {"role": "admin", "status": "active"}
            if password and not emp.get("password_hash"):
                upd.update(password_hash=hash_password(password), password_version=emp.get("password_version", 0) + 1)
            await db.employees.update_one({"id": emp["id"]}, {"$set": upd})
