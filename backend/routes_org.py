import re
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import (DEFAULT_SETTINGS, ROLES, audit, clean, current_member, db, ensure_visible, get_settings, new_id, now,
                  require_role, visible_ids)
from tracking import live_states
from validation import CODE_RE, DEFAULT_SCHEDULE, EID_RE, EMAIL_RE, parse_schedule

router = APIRouter(prefix="/api")


def ci(value):
    return {"$regex": f"^{re.escape(value)}$", "$options": "i"}


class DepartmentIn(BaseModel):
    code: str
    name: str
    description: str = ""


class EmployeeIn(BaseModel):
    employee_id: str
    full_name: str
    email: str
    department_id: Optional[str] = None
    designation: str = ""
    manager_id: Optional[str] = None
    working_schedule: str = DEFAULT_SCHEDULE
    timezone: str = "UTC"
    role: str = "employee"
    status: str = "active"


class ToggleIn(BaseModel):
    enabled: bool


class SettingsIn(BaseModel):
    idle_threshold_min: int
    screenshot_interval_min: int
    screenshot_retention_days: int
    activity_retention_days: int
    offline_after_min: int
    auto_close_after_min: int
    monitoring_notice: str


# Me
@router.get("/me")
async def me(member: dict = Depends(current_member)):
    dept = await db.departments.find_one({"id": member.get("department_id")}, {"_id": 0}) if member.get("department_id") else None
    mgr = await db.employees.find_one({"id": member.get("manager_id")}, {"_id": 0, "full_name": 1}) if member.get("manager_id") else None
    settings = await get_settings()
    return {**clean(member), "department_name": dept["name"] if dept else None, "manager_name": mgr["full_name"] if mgr else None,
            "monitoring_notice": settings["monitoring_notice"], "has_agent": bool(member.get("agent_token_hash"))}


@router.post("/me/acknowledge-notice")
async def ack_notice(member: dict = Depends(current_member)):
    await db.employees.update_one({"id": member["id"]}, {"$set": {"notice_acknowledged_at": now()}})
    await audit(member, "notice.acknowledged", "employee", member["id"])
    return {"ok": True}


# Departments
@router.get("/departments")
async def list_departments(member: dict = Depends(current_member)):
    depts = await db.departments.find({}, {"_id": 0}).sort("name", 1).to_list(5000)
    counts = {c["_id"]: c["n"] async for c in db.employees.aggregate([{"$match": {"status": {"$ne": "inactive"}}}, {"$group": {"_id": "$department_id", "n": {"$sum": 1}}}])}
    return [{**clean(d), "employee_count": counts.get(d["id"], 0)} for d in depts]


async def _validate_dept(body, exclude_id=None):
    if not CODE_RE.match(body.code.strip()):
        raise HTTPException(status_code=400, detail="Code may only contain letters, numbers, - and _ (max 20)")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    for field, val in (("code", body.code.strip()), ("name", body.name.strip())):
        q = {field: ci(val)}
        if exclude_id:
            q["id"] = {"$ne": exclude_id}
        if await db.departments.find_one(q):
            raise HTTPException(status_code=409, detail=f"A department with this {field} already exists")


@router.post("/departments")
async def create_department(body: DepartmentIn, admin: dict = Depends(require_role("admin"))):
    await _validate_dept(body)
    doc = {"id": new_id(), "code": body.code.strip().upper(), "name": body.name.strip(), "description": body.description.strip(), "created_at": now()}
    await db.departments.insert_one(dict(doc))
    await audit(admin, "department.created", "department", doc["id"], {"code": doc["code"]})
    return clean(doc)


@router.put("/departments/{dept_id}")
async def update_department(dept_id: str, body: DepartmentIn, admin: dict = Depends(require_role("admin"))):
    if not await db.departments.find_one({"id": dept_id}):
        raise HTTPException(status_code=404, detail="Department not found")
    await _validate_dept(body, dept_id)
    upd = {"code": body.code.strip().upper(), "name": body.name.strip(), "description": body.description.strip()}
    await db.departments.update_one({"id": dept_id}, {"$set": upd})
    await audit(admin, "department.updated", "department", dept_id, upd)
    return {"id": dept_id, **upd}


@router.delete("/departments/{dept_id}")
async def delete_department(dept_id: str, admin: dict = Depends(require_role("admin"))):
    if await db.employees.count_documents({"department_id": dept_id}):
        raise HTTPException(status_code=409, detail="Move or remove this department's employees first")
    res = await db.departments.delete_one({"id": dept_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Department not found")
    await audit(admin, "department.deleted", "department", dept_id)
    return {"ok": True}


# Employees
async def _enrich(emps):
    depts = {d["id"]: d["name"] for d in await db.departments.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(5000)}
    names = {e["id"]: e["full_name"] for e in await db.employees.find({}, {"_id": 0, "id": 1, "full_name": 1}).to_list(100000)}
    states = await live_states(emps)
    return [{**clean(e), "department_name": depts.get(e.get("department_id")), "manager_name": names.get(e.get("manager_id")),
             "has_agent": bool(e.get("agent_token_hash")), "live_status": states[e["id"]]["status"],
             "account_linked": bool(e.get("clerk_user_id"))} for e in emps]


@router.get("/employees")
async def list_employees(q: Optional[str] = None, department_id: Optional[str] = None, role: Optional[str] = None,
                         manager_id: Optional[str] = None, status: Optional[str] = None, member: dict = Depends(current_member)):
    ids = await visible_ids(member)
    query = {}
    if ids is not None:
        query["id"] = {"$in": ids}
    if department_id:
        query["department_id"] = department_id
    if role:
        query["role"] = role
    if manager_id:
        query["manager_id"] = manager_id
    if status:
        query["status"] = status
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"full_name": rx}, {"email": rx}, {"employee_id": rx}, {"designation": rx}]
    emps = await db.employees.find(query, {"_id": 0}).sort("full_name", 1).to_list(5000)
    return await _enrich(emps)


@router.get("/employees/{emp_id}")
async def get_employee(emp_id: str, member: dict = Depends(current_member)):
    await ensure_visible(member, emp_id)
    emp = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return (await _enrich([emp]))[0]


async def _validate_employee(body: EmployeeIn, exclude_id=None):
    email = body.email.strip().lower()
    if not EID_RE.match(body.employee_id.strip()):
        raise HTTPException(status_code=400, detail="Employee ID may only contain letters, numbers, . - _ (max 30)")
    if not body.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name is required")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid work email")
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if body.status not in ("active", "inactive"):
        raise HTTPException(status_code=400, detail="Invalid status")
    try:
        parse_schedule(body.working_schedule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Working schedule: {e}")
    try:
        ZoneInfo(body.timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="Unknown timezone")
    for field, val in (("employee_id", ci(body.employee_id.strip())), ("email", email)):
        q = {field: val}
        if exclude_id:
            q["id"] = {"$ne": exclude_id}
        if await db.employees.find_one(q):
            raise HTTPException(status_code=409, detail=f"Another employee already uses this {field.replace('_', ' ')}")
    if body.department_id and not await db.departments.find_one({"id": body.department_id}):
        raise HTTPException(status_code=400, detail="Department not found")
    if body.manager_id:
        if body.manager_id == exclude_id:
            raise HTTPException(status_code=400, detail="An employee cannot be their own manager")
        if not await db.employees.find_one({"id": body.manager_id}):
            raise HTTPException(status_code=400, detail="Manager not found")
    return {"employee_id": body.employee_id.strip(), "full_name": body.full_name.strip(), "email": email,
            "department_id": body.department_id or None, "designation": body.designation.strip(), "manager_id": body.manager_id or None,
            "working_schedule": body.working_schedule.strip(), "timezone": body.timezone, "role": body.role, "status": body.status}


@router.post("/employees")
async def create_employee(body: EmployeeIn, admin: dict = Depends(require_role("admin"))):
    data = await _validate_employee(body)
    doc = {"id": new_id(), **data, "screenshots_enabled": False, "clerk_user_id": None, "created_at": now()}
    await db.employees.insert_one(dict(doc))
    await audit(admin, "employee.created", "employee", doc["id"], {"employee_id": doc["employee_id"]})
    return (await _enrich([doc]))[0]


@router.put("/employees/{emp_id}")
async def update_employee(emp_id: str, body: EmployeeIn, admin: dict = Depends(require_role("admin"))):
    existing = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
    data = await _validate_employee(body, emp_id)
    if existing.get("role") == "admin" and (data["role"] != "admin" or data["status"] != "active"):
        if await db.employees.count_documents({"role": "admin", "status": "active"}) <= 1:
            raise HTTPException(status_code=409, detail="Keep at least one active admin")
    if data["email"] != existing.get("email"):
        data["clerk_user_id"] = None
    await db.employees.update_one({"id": emp_id}, {"$set": data})
    changed = {k: v for k, v in data.items() if existing.get(k) != v}
    await audit(admin, "employee.updated", "employee", emp_id, {"changed": list(changed.keys())})
    return await get_employee(emp_id, admin)


@router.patch("/employees/{emp_id}/screenshots")
async def toggle_screenshots(emp_id: str, body: ToggleIn, admin: dict = Depends(require_role("admin"))):
    res = await db.employees.update_one({"id": emp_id}, {"$set": {"screenshots_enabled": body.enabled}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    await audit(admin, "screenshots.enabled" if body.enabled else "screenshots.disabled", "employee", emp_id)
    return {"id": emp_id, "screenshots_enabled": body.enabled}


# Settings
@router.get("/settings")
async def read_settings(member: dict = Depends(current_member)):
    return await get_settings()


LIMITS = {"idle_threshold_min": (1, 120), "screenshot_interval_min": (5, 240), "screenshot_retention_days": (1, 365),
          "activity_retention_days": (30, 730), "offline_after_min": (2, 60), "auto_close_after_min": (10, 720)}


@router.put("/settings")
async def save_settings(body: SettingsIn, admin: dict = Depends(require_role("admin"))):
    data = body.model_dump()
    for k, (lo, hi) in LIMITS.items():
        if not lo <= data[k] <= hi:
            raise HTTPException(status_code=400, detail=f"{k} must be between {lo} and {hi}")
    if not 20 <= len(data["monitoring_notice"].strip()) <= 3000:
        raise HTTPException(status_code=400, detail="Monitoring notice must be 20-3000 characters")
    before = await get_settings()
    await db.settings.update_one({"id": "global"}, {"$set": {**data, "updated_at": now()}}, upsert=True)
    await audit(admin, "settings.updated", "settings", "global", {k: {"from": before[k], "to": v} for k, v in data.items() if before.get(k) != v and k != "monitoring_notice"})
    return {**DEFAULT_SETTINGS, **data}


# Audit logs
@router.get("/audit-logs")
async def audit_logs(action: Optional[str] = None, actor_id: Optional[str] = None, skip: int = 0, limit: int = 50,
                     admin: dict = Depends(require_role("admin"))):
    q = {}
    if action:
        q["action"] = {"$regex": f"^{re.escape(action)}"}
    if actor_id:
        q["actor_id"] = actor_id
    total = await db.audit_logs.count_documents(q)
    items = await db.audit_logs.find(q, {"_id": 0}).sort("ts", -1).skip(max(0, skip)).limit(min(max(1, limit), 200)).to_list(200)
    return {"total": total, "items": clean(items)}
