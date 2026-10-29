from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from core import audit, clean, db, new_id, now, require_role
from validation import (DEPT_REQUIRED, EMP_REQUIRED, build_template, check_headers, pick_sheets, read_table,
                        summarize, validate_departments, validate_employees)

router = APIRouter(prefix="/api/import")
KINDS = ("departments", "employees", "combined")


class CommitIn(BaseModel):
    overwrite_existing: bool = False


async def _db_state():
    depts = await db.departments.find({}, {"_id": 0}).to_list(10000)
    emps = await db.employees.find({}, {"_id": 0, "id": 1, "employee_id": 1, "email": 1}).to_list(100000)
    return depts, emps


def _validate(dept_rows, emp_rows, depts, emps):
    codes = {d["code"].lower(): d["id"] for d in depts}
    names = {d["name"].lower(): d["id"] for d in depts}
    dept_res = validate_departments(dept_rows, codes, names) if dept_rows is not None else None
    if dept_res:
        for r in dept_res:
            if r["status"] == "valid":
                codes[r["data"]["department_code"].lower()] = "new"
                names[r["data"]["department_name"].lower()] = "new"
    eids = {e["employee_id"].lower(): e["id"] for e in emps}
    emails = {e["email"].lower(): e["id"] for e in emps}
    emp_res = validate_employees(emp_rows, codes, names, eids, emails, set(eids) | set(emails)) if emp_rows is not None else None
    return dept_res, emp_res


@router.get("/template/{kind}")
async def template(kind: str, format: str = "csv", admin: dict = Depends(require_role("admin"))):
    if kind not in KINDS or format not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="Unknown template")
    try:
        data = build_template(kind, format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    media = "text/csv" if format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="workpulse_{kind}_template.{format}"'})


@router.post("/preview")
async def preview(kind: str = Form(...), file: UploadFile = File(...), admin: dict = Depends(require_role("admin"))):
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail="kind must be departments, employees or combined")
    content = await file.read()
    base = {"id": new_id(), "file_name": file.filename, "kind": kind, "created_at": now(),
            "admin_id": admin["id"], "admin_name": admin["full_name"]}
    try:
        tables = read_table(file.filename, content)
        dept_t, emp_t = pick_sheets(tables, kind)
        if dept_t is not None:
            check_headers(dept_t, DEPT_REQUIRED, "Departments")
        if emp_t is not None:
            check_headers(emp_t, EMP_REQUIRED, "Employees")
    except ValueError as e:
        await db.imports.insert_one({**base, "status": "rejected", "error": str(e)})
        await audit(admin, "import.rejected", "import", base["id"], {"file": file.filename, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    dept_rows = dept_t[1] if dept_t is not None else None
    emp_rows = emp_t[1] if emp_t is not None else None
    depts, emps = await _db_state()
    dept_res, emp_res = _validate(dept_rows, emp_rows, depts, emps)
    doc = {**base, "status": "preview", "raw": {"departments": dept_rows, "employees": emp_rows},
           "preview": {"departments": summarize(dept_res) if dept_res is not None else None,
                       "employees": summarize(emp_res) if emp_res is not None else None}}
    await db.imports.insert_one(dict(doc))
    await audit(admin, "import.previewed", "import", doc["id"], {"file": file.filename, "kind": kind})
    return {"id": doc["id"], "file_name": file.filename, "kind": kind, "summary": doc["preview"],
            "departments": dept_res, "employees": emp_res}


def _count(outcomes):
    out = {"created": 0, "updated": 0, "failed": 0, "skipped": 0, "duplicate": 0}
    for o in outcomes:
        out[o] += 1
    return out


@router.post("/{import_id}/commit")
async def commit(import_id: str, body: CommitIn, admin: dict = Depends(require_role("admin"))):
    imp = await db.imports.find_one_and_update({"id": import_id, "status": "preview"}, {"$set": {"status": "processing"}})
    if not imp:
        raise HTTPException(status_code=409, detail="This import was already processed or does not exist")
    raw, t = imp["raw"], now()
    overwrite = body.overwrite_existing
    depts, emps = await _db_state()
    dept_res, _ = _validate(raw["departments"], None, depts, emps)
    dept_out = []
    for r in dept_res or []:
        d, outcome = r["data"], {"valid": "created", "error": "failed", "duplicate": "duplicate", "existing": "skipped"}[r["status"]]
        if r["status"] == "valid":
            await db.departments.insert_one({"id": new_id(), "code": d["department_code"].upper(), "name": d["department_name"],
                                             "description": d["description"], "created_at": t, "import_id": import_id})
        elif r["status"] == "existing" and overwrite:
            await db.departments.update_one({"code": {"$regex": f"^{d['department_code']}$", "$options": "i"}},
                                            {"$set": {"name": d["department_name"], "description": d["description"]}})
            outcome = "updated"
        r["outcome"] = outcome
        dept_out.append(outcome)
    emp_out = []
    emp_res = None
    if raw["employees"] is not None:
        depts, emps = await _db_state()
        _, emp_res = _validate(None, raw["employees"], depts, emps)
        codes = {d["code"].lower(): d["id"] for d in depts}
        names = {d["name"].lower(): d["id"] for d in depts}
        by_eid = {e["employee_id"].lower(): e["id"] for e in emps}
        for r in emp_res:
            d, outcome = r["data"], {"valid": "created", "error": "failed", "duplicate": "duplicate", "existing": "skipped"}[r["status"]]
            dept_id = codes.get(d["department_code"].lower()) if d["department_code"] else names.get(d["department_name"].lower())
            fields = {"employee_id": d["employee_id"], "full_name": d["full_name"], "email": d["work_email"], "department_id": dept_id,
                      "designation": d["designation"], "working_schedule": d["working_schedule"]}
            if r["status"] == "valid":
                await db.employees.insert_one({"id": new_id(), **fields, "manager_id": None, "timezone": "UTC",
                                               "role": d["role"] or "employee", "status": "active", "screenshots_enabled": False,
                                               "clerk_user_id": None, "created_at": t, "import_id": import_id})
            elif r["status"] == "existing" and overwrite:
                if d["role"]:
                    fields["role"] = d["role"]
                await db.employees.update_one({"id": by_eid[d["employee_id"].lower()]}, {"$set": {**fields, "updated_at": t}})
                outcome = "updated"
            r["outcome"] = outcome
            emp_out.append(outcome)
        _, emps = await _db_state()
        keys = {}
        for e in emps:
            keys[e["employee_id"].lower()] = e["id"]
            keys[e["email"].lower()] = e["id"]
        manager_ids = set()
        for r in emp_res:
            if r["outcome"] in ("created", "updated") and r["data"]["manager"]:
                mid = keys.get(r["data"]["manager"].lower())
                if mid:
                    await db.employees.update_one({"id": keys[r["data"]["employee_id"].lower()]}, {"$set": {"manager_id": mid}})
                    manager_ids.add(mid)
        if manager_ids:
            await db.employees.update_many({"id": {"$in": list(manager_ids)}, "role": "employee"}, {"$set": {"role": "manager"}})
    summary = {"departments": _count(dept_out) if dept_res is not None else None,
               "employees": _count(emp_out) if emp_res is not None else None, "overwrite_existing": overwrite}
    await db.imports.update_one({"id": import_id}, {"$set": {"status": "completed", "completed_at": now(), "summary": summary,
                                                             "results": {"departments": dept_res, "employees": emp_res}}})
    await audit(admin, "import.completed", "import", import_id, summary)
    return {"id": import_id, "summary": summary, "departments": dept_res, "employees": emp_res}


@router.get("/history")
async def history(admin: dict = Depends(require_role("admin"))):
    items = await db.imports.find({}, {"_id": 0, "raw": 0, "results": 0}).sort("created_at", -1).to_list(500)
    return clean(items)


@router.get("/{import_id}")
async def import_detail(import_id: str, admin: dict = Depends(require_role("admin"))):
    item = await db.imports.find_one({"id": import_id}, {"_id": 0, "raw": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Import not found")
    return clean(item)
