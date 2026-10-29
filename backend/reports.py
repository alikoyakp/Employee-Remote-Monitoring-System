import csv
import io
from datetime import date as date_cls, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from openpyxl import Workbook

from core import aware, clean, current_member, db, get_settings, now, require_role, visible_ids
from tracking import live_states

router = APIRouter(prefix="/api")
UTC = timezone.utc


def _blank():
    return {"session_min": 0.0, "break_min": 0.0, "active_min": 0, "mouse": 0, "clicks": 0, "keys": 0,
            "sessions": 0, "auto_closed": 0, "first_in": None, "last_out": None}


async def compute_days(ids, d0, d1):
    """Per (employee_id, day) attendance + activity metrics. ids=None means all employees."""
    settings, t = await get_settings(), now()
    rs = datetime.combine(d0, time.min, tzinfo=UTC)
    rend = datetime.combine(d1, time.min, tzinfo=UTC) + timedelta(days=1)
    idq = {"$in": ids} if ids is not None else {"$exists": True}
    out = {}

    def add(emp, start, end, field):
        cur, end = max(start, rs), min(end, rend)
        while cur < end:
            seg_end = min(end, datetime.combine(cur.date(), time.min, tzinfo=UTC) + timedelta(days=1))
            out.setdefault((emp, cur.date().isoformat()), _blank())[field] += (seg_end - cur).total_seconds() / 60
            cur = seg_end

    overlap = {"employee_id": idq, "start": {"$lt": rend}, "$or": [{"end": None}, {"end": {"$gte": rs}}]}
    async for s in db.sessions.find(overlap, {"_id": 0}):
        start = aware(s["start"])
        last_seen = aware(s.get("last_seen")) or start
        end = aware(s["end"]) or (t if t - last_seen <= timedelta(minutes=settings["offline_after_min"]) else last_seen)
        add(s["employee_id"], start, end, "session_min")
        if rs <= start < rend:
            r = out.setdefault((s["employee_id"], start.date().isoformat()), _blank())
            r["sessions"] += 1
            r["auto_closed"] += 1 if s.get("auto_closed") else 0
            r["first_in"] = min(r["first_in"] or start, start)
        if s.get("end") and rs <= end < rend:
            r = out.setdefault((s["employee_id"], end.date().isoformat()), _blank())
            r["last_out"] = max(r["last_out"] or end, end)
    async for b in db.breaks.find(overlap, {"_id": 0}):
        add(b["employee_id"], aware(b["start"]), aware(b["end"]) or t, "break_min")
    pipeline = [
        {"$match": {"employee_id": idq, "day": {"$gte": d0.isoformat(), "$lte": d1.isoformat()}}},
        {"$group": {"_id": {"e": "$employee_id", "d": "$day"}, "active": {"$sum": {"$cond": ["$active", 1, 0]}},
                    "mouse": {"$sum": "$mouse"}, "clicks": {"$sum": "$clicks"}, "keys": {"$sum": "$keys"}}},
    ]
    async for a in db.activity.aggregate(pipeline):
        r = out.setdefault((a["_id"]["e"], a["_id"]["d"]), _blank())
        r.update(active_min=a["active"], mouse=a["mouse"], clicks=a["clicks"], keys=a["keys"])
    for r in out.values():
        worked = max(0.0, r["session_min"] - r["break_min"])
        r["worked_min"] = round(worked)
        r["break_min"] = round(r["break_min"])
        r["active_min"] = min(r["active_min"], r["worked_min"])
        r["idle_min"] = r["worked_min"] - r["active_min"]
    return out


def _bucket(day_iso, period):
    d = date_cls.fromisoformat(day_iso)
    if period == "weekly":
        return (d - timedelta(days=d.weekday())).isoformat()
    if period == "monthly":
        return d.strftime("%Y-%m")
    return day_iso


async def _filtered_employees(member, employee_id, department_id, manager_id):
    ids = await visible_ids(member)
    q = {}
    if ids is not None:
        q["id"] = {"$in": ids}
    if department_id:
        q["department_id"] = department_id
    if manager_id:
        q["manager_id"] = manager_id
    emps = await db.employees.find(q, {"_id": 0, "agent_token_hash": 0}).to_list(10000)
    if employee_id:
        emps = [e for e in emps if e["id"] == employee_id]
    return emps


def _parse_range(start, end):
    try:
        d1 = date_cls.fromisoformat(end) if end else now().date()
        d0 = date_cls.fromisoformat(start) if start else d1 - timedelta(days=6)
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must be YYYY-MM-DD")
    if d0 > d1:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    if (d1 - d0).days > 366:
        raise HTTPException(status_code=400, detail="Date range cannot exceed one year")
    return d0, d1


async def build_report(member, period, start, end, employee_id, department_id, manager_id):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period must be daily, weekly or monthly")
    d0, d1 = _parse_range(start, end)
    emps = await _filtered_employees(member, employee_id, department_id, manager_id)
    by_id = {e["id"]: e for e in emps}
    depts = {d["id"]: d["name"] for d in await db.departments.find({}, {"_id": 0}).to_list(5000)}
    names = {e["id"]: e["full_name"] for e in await db.employees.find({}, {"_id": 0, "id": 1, "full_name": 1}).to_list(100000)}
    days = await compute_days(list(by_id.keys()), d0, d1) if by_id else {}
    agg = {}
    for (eid, day), r in days.items():
        key = (eid, _bucket(day, period))
        a = agg.setdefault(key, {"days_present": 0, "worked_min": 0, "active_min": 0, "idle_min": 0, "break_min": 0,
                                 "sessions": 0, "auto_closed": 0, "mouse": 0, "clicks": 0, "keys": 0, "first_in": None, "last_out": None})
        if r["worked_min"] > 0 or r["sessions"] > 0:
            a["days_present"] += 1
        for k in ("worked_min", "active_min", "idle_min", "break_min", "sessions", "auto_closed", "mouse", "clicks", "keys"):
            a[k] += r[k]
        if r["first_in"]:
            a["first_in"] = min(a["first_in"] or r["first_in"], r["first_in"])
        if r["last_out"]:
            a["last_out"] = max(a["last_out"] or r["last_out"], r["last_out"])
    rows = []
    for (eid, bucket), a in sorted(agg.items(), key=lambda x: (x[0][1], by_id[x[0][0]]["full_name"])):
        e = by_id[eid]
        rows.append({"period": bucket, "employee_ref": eid, "employee_id": e["employee_id"], "employee_name": e["full_name"],
                     "department": depts.get(e.get("department_id"), ""), "manager": names.get(e.get("manager_id"), ""),
                     **{k: a[k] for k in ("days_present", "sessions", "worked_min", "active_min", "idle_min", "break_min", "auto_closed", "mouse", "clicks", "keys")},
                     "productivity_pct": round(100 * a["active_min"] / a["worked_min"]) if a["worked_min"] else 0,
                     "first_in": clean(a["first_in"]), "last_out": clean(a["last_out"])})
    dept_rows = {}
    for r in rows:
        d = dept_rows.setdefault(r["department"] or "Unassigned", {"department": r["department"] or "Unassigned", "worked_min": 0, "active_min": 0, "idle_min": 0, "break_min": 0, "employees": set()})
        for k in ("worked_min", "active_min", "idle_min", "break_min"):
            d[k] += r[k]
        d["employees"].add(r["employee_ref"])
    departments = [{**d, "employees": len(d["employees"])} for d in dept_rows.values()]
    trend = {}
    for (eid, day), r in days.items():
        tr = trend.setdefault(day, {"day": day, "worked_min": 0, "active_min": 0, "idle_min": 0, "present": 0})
        for k in ("worked_min", "active_min", "idle_min"):
            tr[k] += r[k]
        tr["present"] += 1 if r["worked_min"] > 0 else 0
    totals = {k: sum(r[k] for r in rows) for k in ("worked_min", "active_min", "idle_min", "break_min", "sessions", "auto_closed")}
    totals["employees"] = len({r["employee_ref"] for r in rows})
    return {"period": period, "start": d0.isoformat(), "end": d1.isoformat(), "rows": rows, "departments": departments,
            "trend": sorted(trend.values(), key=lambda x: x["day"]), "totals": totals}


@router.get("/reports")
async def reports(period: str = "daily", start: Optional[str] = None, end: Optional[str] = None,
                  employee_id: Optional[str] = None, department_id: Optional[str] = None, manager_id: Optional[str] = None,
                  member: dict = Depends(current_member)):
    return await build_report(member, period, start, end, employee_id, department_id, manager_id)


EXPORT_COLS = [("period", "Period"), ("employee_id", "Employee ID"), ("employee_name", "Employee"), ("department", "Department"),
               ("manager", "Manager"), ("days_present", "Days present"), ("sessions", "Sessions"), ("worked_h", "Worked hours"),
               ("active_h", "Active hours"), ("idle_h", "Idle hours"), ("break_h", "Break hours"), ("productivity_pct", "Active %"),
               ("auto_closed", "Missed logouts"), ("first_in", "First login (UTC)"), ("last_out", "Last logout (UTC)")]


@router.get("/reports/export")
async def export_report(format: str = "csv", period: str = "daily", start: Optional[str] = None, end: Optional[str] = None,
                        employee_id: Optional[str] = None, department_id: Optional[str] = None, manager_id: Optional[str] = None,
                        member: dict = Depends(current_member)):
    rep = await build_report(member, period, start, end, employee_id, department_id, manager_id)
    data = []
    for r in rep["rows"]:
        r = {**r, "worked_h": round(r["worked_min"] / 60, 2), "active_h": round(r["active_min"] / 60, 2),
             "idle_h": round(r["idle_min"] / 60, 2), "break_h": round(r["break_min"] / 60, 2)}
        data.append([r.get(k) if r.get(k) is not None else "" for k, _ in EXPORT_COLS])
    fname = f"workpulse_{period}_{rep['start']}_{rep['end']}"
    if format == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        ws.append([h for _, h in EXPORT_COLS])
        for row in data:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.xlsx"'})
    if format != "csv":
        raise HTTPException(status_code=400, detail="format must be csv or xlsx")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for _, h in EXPORT_COLS])
    w.writerows(data)
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})


@router.get("/dashboard")
async def dashboard(member: dict = Depends(require_role("admin", "manager"))):
    ids = await visible_ids(member)
    q = {"status": {"$ne": "inactive"}}
    if ids is not None:
        q["id"] = {"$in": ids}
    emps = await db.employees.find(q, {"_id": 0, "agent_token_hash": 0}).to_list(10000)
    states = await live_states(emps)
    today = now().date()
    emp_ids = [e["id"] for e in emps]
    week = await compute_days(emp_ids, today - timedelta(days=6), today) if emp_ids else {}
    depts = await db.departments.find({}, {"_id": 0}).to_list(5000)
    dname = {d["id"]: d["name"] for d in depts}
    counts = {"active": 0, "idle": 0, "on_break": 0, "offline": 0, "signed_out": 0}
    board = []
    for e in emps:
        st = states[e["id"]]
        counts[st["status"]] += 1
        td = week.get((e["id"], today.isoformat()), {})
        board.append({"id": e["id"], "employee_id": e["employee_id"], "full_name": e["full_name"], "designation": e.get("designation", ""),
                      "department": dname.get(e.get("department_id"), ""), "status": st["status"],
                      "session_start": st["session"]["start"] if st["session"] else None,
                      "last_interaction_at": clean(e.get("last_interaction_at")),
                      "today_worked_min": td.get("worked_min", 0), "today_active_min": td.get("active_min", 0)})
    trend = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        rows = [r for (eid, day), r in week.items() if day == d]
        trend.append({"day": d, "worked_h": round(sum(r["worked_min"] for r in rows) / 60, 1),
                      "active_h": round(sum(r["active_min"] for r in rows) / 60, 1),
                      "idle_h": round(sum(r["idle_min"] for r in rows) / 60, 1),
                      "present": sum(1 for r in rows if r["worked_min"] > 0)})
    today_rows = [r for (eid, day), r in week.items() if day == today.isoformat()]
    present = sum(1 for r in today_rows if r["worked_min"] > 0 or r["sessions"] > 0)
    worked_today = sum(r["worked_min"] for r in today_rows)
    dept_stats = []
    for d in depts:
        members = [b for b in board if b["department"] == d["name"]]
        if ids is not None and not members:
            continue
        dept_stats.append({"department": d["name"], "employees": len(members),
                           "online": sum(1 for b in members if b["status"] in ("active", "idle", "on_break")),
                           "worked_h": round(sum(b["today_worked_min"] for b in members) / 60, 1)})
    return {"totals": {"employees": len(emps), "departments": len(depts) if ids is None else len(dept_stats),
                       "logged_in": counts["active"] + counts["idle"] + counts["on_break"], **counts,
                       "present_today": present, "absent_today": len(emps) - present,
                       "hours_today": round(worked_today / 60, 1),
                       "avg_hours_today": round(worked_today / 60 / present, 1) if present else 0},
            "board": sorted(board, key=lambda b: ["active", "idle", "on_break", "offline", "signed_out"].index(b["status"])),
            "trend": trend, "departments": dept_stats}
