import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from core import (APP_NAME, agent_member, audit, aware, clean, current_member, db, ensure_visible, get_object,
                  get_settings, hash_token, logger, new_id, now, put_object, require_role, visible_ids)
from validation import in_schedule

router = APIRouter(prefix="/api")
AGENT_FILE = Path(__file__).parent / "agent_dist" / "workpulse_agent.py"


class Heartbeat(BaseModel):
    mouse: int = 0
    clicks: int = 0
    keys: int = 0
    last_interaction_at: Optional[str] = None
    device: Optional[str] = None


class ClockIn(BaseModel):
    device: Optional[str] = None


def within_schedule(emp, t=None):
    try:
        tz = ZoneInfo(emp.get("timezone") or "UTC")
    except Exception:
        tz = timezone.utc
    return in_schedule(emp.get("working_schedule"), (t or now()).astimezone(tz))


def compute_status(emp, session, brk, settings, t):
    if not session:
        return "signed_out"
    if brk:
        return "on_break"
    last_seen = aware(session.get("last_seen")) or aware(session["start"])
    if t - last_seen > timedelta(minutes=settings["offline_after_min"]):
        return "offline"
    li = aware(emp.get("last_interaction_at"))
    if not li or t - li > timedelta(minutes=settings["idle_threshold_min"]):
        return "idle"
    return "active"


async def live_states(emps):
    ids = [e["id"] for e in emps]
    settings, t = await get_settings(), now()
    sessions = {s["employee_id"]: s for s in await db.sessions.find({"employee_id": {"$in": ids}, "status": "open"}, {"_id": 0}).to_list(10000)}
    breaks = {b["employee_id"]: b for b in await db.breaks.find({"employee_id": {"$in": ids}, "end": None}, {"_id": 0}).to_list(10000)}
    out = {}
    for e in emps:
        s, b = sessions.get(e["id"]), breaks.get(e["id"])
        out[e["id"]] = {"status": compute_status(e, s, b, settings, t), "session": clean(s) if s else None,
                        "break": clean(b) if b else None}
    return out


async def open_session(emp_id):
    return await db.sessions.find_one({"employee_id": emp_id, "status": "open"}, {"_id": 0})


async def do_clock_in(emp, source, device=None):
    s = await open_session(emp["id"])
    t = now()
    dev = f"{source}:{device or 'default'}"
    if s:
        await db.sessions.update_one({"id": s["id"]}, {"$addToSet": {"devices": dev}, "$set": {"last_seen": t}})
        return await open_session(emp["id"])
    s = {"id": new_id(), "employee_id": emp["id"], "start": t, "end": None, "last_seen": t, "status": "open",
         "source": source, "devices": [dev], "auto_closed": False, "close_reason": None,
         "outside_schedule": not within_schedule(emp, t)}
    await db.sessions.insert_one(dict(s))
    await db.employees.update_one({"id": emp["id"]}, {"$set": {"last_interaction_at": t}})
    await audit(emp, "session.clock_in", "session", s["id"], {"source": source})
    return s


async def close_session(s, end, reason, auto=False):
    await db.breaks.update_many({"session_id": s["id"], "end": None}, {"$set": {"end": end}})
    await db.sessions.update_one({"id": s["id"]}, {"$set": {"status": "closed", "end": end, "close_reason": reason, "auto_closed": auto}})


async def do_clock_out(emp, source):
    s = await open_session(emp["id"])
    if not s:
        raise HTTPException(status_code=400, detail="You are not clocked in")
    await close_session(s, now(), f"{source}_logout")
    await audit(emp, "session.clock_out", "session", s["id"], {"source": source})
    return {"ok": True}


async def do_heartbeat(emp, hb: Heartbeat, source):
    s = await open_session(emp["id"])
    if not s:
        return {"tracking": False, "reason": "not_clocked_in"}
    settings, t = await get_settings(), now()
    li = None
    if hb.last_interaction_at:
        try:
            li = aware(datetime.fromisoformat(hb.last_interaction_at.replace("Z", "+00:00")))
            li = min(max(li, t - timedelta(hours=1)), t)
        except ValueError:
            li = None
    counts = {"mouse": max(0, min(hb.mouse, 100000)), "clicks": max(0, min(hb.clicks, 10000)), "keys": max(0, min(hb.keys, 20000))}
    if li is None and sum(counts.values()) > 0:
        li = t
    prev = aware(emp.get("last_interaction_at"))
    if li and (not prev or li > prev):
        prev = li
        await db.employees.update_one({"id": emp["id"]}, {"$set": {"last_interaction_at": li}})
    await db.sessions.update_one({"id": s["id"]}, {"$set": {"last_seen": t}})
    if await db.breaks.find_one({"employee_id": emp["id"], "end": None}):
        return {"tracking": False, "reason": "on_break"}
    active = bool(prev and t - prev <= timedelta(minutes=settings["idle_threshold_min"]))
    minute = t.replace(second=0, microsecond=0)
    await db.activity.update_one(
        {"employee_id": emp["id"], "minute": minute},
        {"$inc": counts, "$max": {"active": active}, "$addToSet": {"sources": source},
         "$setOnInsert": {"session_id": s["id"], "day": minute.date().isoformat()}},
        upsert=True)
    return {"tracking": True, "active": active}


async def today_minutes(emp_id):
    from reports import compute_days
    d = now().date()
    rows = await compute_days([emp_id], d, d)
    r = rows.get((emp_id, d.isoformat()))
    return r or {"worked_min": 0, "active_min": 0, "idle_min": 0, "break_min": 0}


# Web tracking (signed-in user)
@router.get("/tracking/me")
async def my_tracking(member: dict = Depends(current_member)):
    states = await live_states([member])
    settings = await get_settings()
    return {**states[member["id"]], "today": await today_minutes(member["id"]),
            "idle_threshold_min": settings["idle_threshold_min"],
            "screenshots_enabled": bool(member.get("screenshots_enabled")),
            "screenshot_interval_min": settings["screenshot_interval_min"],
            "within_schedule": within_schedule(member), "working_schedule": member.get("working_schedule")}


@router.post("/tracking/clock-in")
async def web_clock_in(body: ClockIn, member: dict = Depends(current_member)):
    return clean(await do_clock_in(member, "web", body.device))


@router.post("/tracking/clock-out")
async def web_clock_out(member: dict = Depends(current_member)):
    return await do_clock_out(member, "web")


@router.post("/tracking/break/start")
async def break_start(member: dict = Depends(current_member)):
    s = await open_session(member["id"])
    if not s:
        raise HTTPException(status_code=400, detail="Clock in before taking a break")
    if await db.breaks.find_one({"employee_id": member["id"], "end": None}):
        raise HTTPException(status_code=400, detail="You are already on a break")
    b = {"id": new_id(), "employee_id": member["id"], "session_id": s["id"], "start": now(), "end": None}
    await db.breaks.insert_one(dict(b))
    await audit(member, "session.break_start", "session", s["id"])
    return clean(b)


@router.post("/tracking/break/end")
async def break_end(member: dict = Depends(current_member)):
    res = await db.breaks.update_one({"employee_id": member["id"], "end": None}, {"$set": {"end": now()}})
    if res.modified_count == 0:
        raise HTTPException(status_code=400, detail="You are not on a break")
    await db.employees.update_one({"id": member["id"]}, {"$set": {"last_interaction_at": now()}})
    await audit(member, "session.break_end", "employee", member["id"])
    return {"ok": True}


@router.post("/tracking/heartbeat")
async def web_heartbeat(hb: Heartbeat, member: dict = Depends(current_member)):
    return await do_heartbeat(member, hb, "web")


# Desktop agent tokens
@router.get("/me/agent")
async def my_agent(member: dict = Depends(current_member)):
    return {"has_token": bool(member.get("agent_token_hash")), "created_at": clean(member.get("agent_token_created_at")),
            "last_used_at": clean(member.get("agent_last_used_at")), "screenshots_enabled": bool(member.get("screenshots_enabled"))}


@router.post("/me/agent-token")
async def create_agent_token(member: dict = Depends(current_member)):
    token = "wpa_" + secrets.token_urlsafe(32)
    await db.employees.update_one({"id": member["id"]}, {"$set": {"agent_token_hash": hash_token(token), "agent_token_created_at": now()}})
    await audit(member, "agent.token_created", "employee", member["id"])
    return {"token": token}


@router.delete("/me/agent-token")
async def revoke_my_agent_token(member: dict = Depends(current_member)):
    await db.employees.update_one({"id": member["id"]}, {"$unset": {"agent_token_hash": "", "agent_token_created_at": ""}})
    await audit(member, "agent.token_revoked", "employee", member["id"])
    return {"ok": True}


@router.delete("/employees/{emp_id}/agent-token")
async def admin_revoke_agent(emp_id: str, admin: dict = Depends(require_role("admin"))):
    res = await db.employees.update_one({"id": emp_id}, {"$unset": {"agent_token_hash": "", "agent_token_created_at": ""}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    await audit(admin, "agent.token_revoked", "employee", emp_id)
    return {"ok": True}


@router.get("/agent/download")
async def download_agent():
    return FileResponse(AGENT_FILE, filename="workpulse_agent.py", media_type="text/x-python")


# Desktop agent API (X-Agent-Token)
@router.get("/agent/config")
async def agent_config(emp: dict = Depends(agent_member)):
    settings = await get_settings()
    state = (await live_states([emp]))[emp["id"]]
    return {"employee": {"employee_id": emp["employee_id"], "full_name": emp["full_name"]},
            "status": state["status"], "clocked_in": state["session"] is not None, "on_break": state["break"] is not None,
            "within_schedule": within_schedule(emp), "screenshots_enabled": bool(emp.get("screenshots_enabled")),
            "screenshot_interval_min": settings["screenshot_interval_min"], "idle_threshold_min": settings["idle_threshold_min"],
            "heartbeat_interval_sec": 60, "monitoring_notice": settings["monitoring_notice"]}


@router.post("/agent/clock-in")
async def agent_clock_in(body: ClockIn, emp: dict = Depends(agent_member)):
    return clean(await do_clock_in(emp, "agent", body.device))


@router.post("/agent/clock-out")
async def agent_clock_out(emp: dict = Depends(agent_member)):
    return await do_clock_out(emp, "agent")


@router.post("/agent/heartbeat")
async def agent_heartbeat(hb: Heartbeat, emp: dict = Depends(agent_member)):
    return await do_heartbeat(emp, hb, "agent")


@router.post("/agent/screenshot")
async def agent_screenshot(file: UploadFile = File(...), emp: dict = Depends(agent_member)):
    if not emp.get("screenshots_enabled"):
        raise HTTPException(status_code=403, detail="Screenshots are disabled for this employee")
    s = await open_session(emp["id"])
    if not s:
        raise HTTPException(status_code=409, detail="Not clocked in")
    if await db.breaks.find_one({"employee_id": emp["id"], "end": None}):
        raise HTTPException(status_code=409, detail="On break")
    if not within_schedule(emp):
        raise HTTPException(status_code=409, detail="Outside working schedule")
    settings = await get_settings()
    last = await db.screenshots.find_one({"employee_id": emp["id"], "is_deleted": False}, sort=[("taken_at", -1)])
    if last and now() - aware(last["taken_at"]) < timedelta(minutes=settings["screenshot_interval_min"] * 0.8):
        raise HTTPException(status_code=429, detail="Screenshot interval not reached")
    ctype = file.content_type or ""
    if ctype not in ("image/png", "image/jpeg"):
        raise HTTPException(status_code=400, detail="Only PNG or JPEG screenshots are accepted")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024 or len(data) == 0:
        raise HTTPException(status_code=400, detail="Screenshot must be between 1 byte and 8 MB")
    t = now()
    ext = "png" if ctype == "image/png" else "jpg"
    path = f"{APP_NAME}/screenshots/{emp['id']}/{t.date().isoformat()}/{uuid.uuid4()}.{ext}"
    result = await run_in_threadpool(put_object, path, data, ctype)
    doc = {"id": new_id(), "employee_id": emp["id"], "employee_code": emp["employee_id"], "session_id": s["id"],
           "storage_path": result["path"], "content_type": ctype, "size": len(data), "taken_at": t,
           "day": t.date().isoformat(), "is_deleted": False}
    await db.screenshots.insert_one(dict(doc))
    return {"id": doc["id"], "taken_at": t.isoformat()}


# Screenshot gallery (admins + managers of the employee)
@router.get("/screenshots")
async def list_screenshots(employee_id: Optional[str] = None, date: Optional[str] = None,
                           member: dict = Depends(require_role("admin", "manager"))):
    ids = await visible_ids(member)
    if ids is not None:
        ids = [i for i in ids if i != member["id"]]
    q = {"is_deleted": False}
    if employee_id:
        if ids is not None and employee_id not in ids:
            raise HTTPException(status_code=404, detail="Employee not found")
        q["employee_id"] = employee_id
    elif ids is not None:
        q["employee_id"] = {"$in": ids}
    if date:
        q["day"] = date
    shots = await db.screenshots.find(q, {"_id": 0, "storage_path": 0}).sort("taken_at", -1).to_list(500)
    names = {e["id"]: e["full_name"] for e in await db.employees.find({"id": {"$in": list({s["employee_id"] for s in shots})}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(5000)}
    await audit(member, "screenshot.list", "employee", employee_id or "", {"date": date, "count": len(shots)})
    return [{**clean(s), "employee_name": names.get(s["employee_id"], "")} for s in shots]


@router.get("/screenshots/{shot_id}/image")
async def screenshot_image(shot_id: str, member: dict = Depends(require_role("admin", "manager"))):
    shot = await db.screenshots.find_one({"id": shot_id, "is_deleted": False}, {"_id": 0})
    if not shot or (member["role"] != "admin" and shot["employee_id"] == member["id"]):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    await ensure_visible(member, shot["employee_id"])
    data, ctype = await run_in_threadpool(get_object, shot["storage_path"])
    await audit(member, "screenshot.view", "screenshot", shot_id, {"employee_id": shot["employee_id"]})
    return Response(content=data, media_type=shot.get("content_type", ctype), headers={"Cache-Control": "no-store"})


# Attendance sessions + activity timeline
@router.get("/sessions")
async def list_sessions(employee_id: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None,
                        department_id: Optional[str] = None, member: dict = Depends(current_member)):
    ids = await visible_ids(member)
    emp_q = {}
    if ids is not None:
        emp_q["id"] = {"$in": ids}
    if department_id:
        emp_q["department_id"] = department_id
    emps = {e["id"]: e for e in await db.employees.find(emp_q, {"_id": 0, "id": 1, "full_name": 1, "employee_id": 1}).to_list(10000)}
    allowed = list(emps.keys())
    if employee_id:
        allowed = [employee_id] if employee_id in emps else []
    q = {"employee_id": {"$in": allowed}}
    if start:
        q.setdefault("start", {})["$gte"] = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    if end:
        q.setdefault("start", {})["$lt"] = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) + timedelta(days=1)
    sessions = await db.sessions.find(q, {"_id": 0}).sort("start", -1).to_list(1000)
    sids = [s["id"] for s in sessions]
    br = {}
    for b in await db.breaks.find({"session_id": {"$in": sids}}, {"_id": 0}).to_list(20000):
        e = aware(b["end"]) or now()
        br[b["session_id"]] = br.get(b["session_id"], 0) + (e - aware(b["start"])).total_seconds() / 60
    out = []
    for s in sessions:
        endt = aware(s["end"]) or now()
        dur = (endt - aware(s["start"])).total_seconds() / 60
        out.append({**clean(s), "employee_name": emps[s["employee_id"]]["full_name"], "employee_code": emps[s["employee_id"]]["employee_id"],
                    "duration_min": round(dur), "break_min": round(br.get(s["id"], 0)), "worked_min": round(dur - br.get(s["id"], 0))})
    return out


@router.get("/activity/timeline")
async def timeline(employee_id: str, date: str, member: dict = Depends(current_member)):
    await ensure_visible(member, employee_id)
    day_start = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    minutes = await db.activity.find({"employee_id": employee_id, "day": date}, {"_id": 0, "employee_id": 0}).sort("minute", 1).to_list(2000)
    sessions = await db.sessions.find({"employee_id": employee_id, "start": {"$lt": day_end}, "$or": [{"end": None}, {"end": {"$gte": day_start}}]}, {"_id": 0}).to_list(100)
    breaks = await db.breaks.find({"employee_id": employee_id, "start": {"$lt": day_end}, "$or": [{"end": None}, {"end": {"$gte": day_start}}]}, {"_id": 0}).to_list(200)
    hours = [{"hour": h, "active": 0, "idle": 0, "mouse": 0, "clicks": 0, "keys": 0} for h in range(24)]
    for m in minutes:
        h = hours[aware(m["minute"]).hour]
        h["active" if m.get("active") else "idle"] += 1
        for k in ("mouse", "clicks", "keys"):
            h[k] += m.get(k, 0)
    shots = await db.screenshots.count_documents({"employee_id": employee_id, "day": date, "is_deleted": False})
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0, "last_interaction_at": 1, "full_name": 1})
    return {"hours": hours, "sessions": clean(sessions), "breaks": clean(breaks), "screenshot_count": shots,
            "minutes": [{"minute": clean(m["minute"]), "active": m.get("active", False)} for m in minutes],
            "last_interaction_at": clean(emp.get("last_interaction_at")) if emp else None}


# Maintenance: missed logouts + retention
async def run_maintenance():
    settings, t = await get_settings(), now()
    cutoff = t - timedelta(minutes=settings["auto_close_after_min"])
    closed = 0
    async for s in db.sessions.find({"status": "open", "last_seen": {"$lt": cutoff}}, {"_id": 0}):
        await close_session(s, aware(s["last_seen"]), "missed_logout", auto=True)
        closed += 1
    shot_cut = t - timedelta(days=settings["screenshot_retention_days"])
    shots = await db.screenshots.update_many({"is_deleted": False, "taken_at": {"$lt": shot_cut}}, {"$set": {"is_deleted": True, "deleted_at": t, "deleted_reason": "retention"}})
    act = await db.activity.delete_many({"minute": {"$lt": t - timedelta(days=settings["activity_retention_days"])}})
    result = {"sessions_auto_closed": closed, "screenshots_expired": shots.modified_count, "activity_purged": act.deleted_count}
    if closed or shots.modified_count or act.deleted_count:
        await audit(None, "maintenance.run", "system", "", result)
    logger.info("maintenance %s", result)
    return result


@router.post("/cron/maintenance")
async def cron_maintenance(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("authorization", "")
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not secret or not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("x-webhook-id") or new_id()
    if await db.cron_runs.find_one({"run_id": run_id}):
        return {"accepted": True, "duplicate": True}
    await db.cron_runs.insert_one({"run_id": run_id, "ts": now()})
    background.add_task(run_maintenance)
    return {"accepted": True}


@router.post("/admin/maintenance")
async def admin_maintenance(admin: dict = Depends(require_role("admin"))):
    result = await run_maintenance()
    await audit(admin, "maintenance.manual_run", "system", "", result)
    return result
