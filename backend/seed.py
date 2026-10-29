"""Idempotent sample data: 4 departments, 12 example employees and ~6 days of activity history."""
import random
from datetime import datetime, time, timedelta, timezone

from core import db, logger, new_id, now

DEPTS = [("ENG", "Engineering"), ("PRD", "Product"), ("MKT", "Marketing"), ("SLS", "Sales")]
PEOPLE = [
    ("EMP001", "Elena Rostova", "ENG", "Engineering Lead", None, "manager"),
    ("EMP002", "David Chen", "ENG", "Senior Frontend Developer", "EMP001", "employee"),
    ("EMP003", "Priya Nair", "ENG", "Backend Developer", "EMP001", "employee"),
    ("EMP004", "Tomás García", "ENG", "QA Engineer", "EMP001", "employee"),
    ("EMP005", "Marcus Vance", "PRD", "Product Manager", None, "manager"),
    ("EMP006", "Aiko Tanaka", "PRD", "Product Designer", "EMP005", "employee"),
    ("EMP007", "Liam O'Connor", "PRD", "UX Researcher", "EMP005", "employee"),
    ("EMP008", "Sarah Jenkins", "MKT", "Marketing Manager", None, "manager"),
    ("EMP009", "Noah Williams", "MKT", "Content Strategist", "EMP008", "employee"),
    ("EMP010", "Fatima Zahra", "SLS", "Sales Manager", None, "manager"),
    ("EMP011", "Lucas Martin", "SLS", "Account Executive", "EMP010", "employee"),
    ("EMP012", "Grace Kim", "SLS", "Sales Development Rep", "EMP010", "employee"),
]


async def seed_sample_data():
    if await db.meta.find_one({"id": "sample_seed"}):
        return
    if await db.departments.count_documents({}) or await db.employees.count_documents({"role": {"$ne": "admin"}}):
        await db.meta.insert_one({"id": "sample_seed", "skipped": True})
        return
    rnd = random.Random(42)
    t = now()
    dept_ids = {}
    for code, name in DEPTS:
        dept_ids[code] = new_id()
        await db.departments.insert_one({"id": dept_ids[code], "code": code, "name": name, "description": f"{name} team (sample)", "created_at": t, "is_sample": True})
    emp_ids = {}
    for eid, name, dept, title, mgr, role in PEOPLE:
        emp_ids[eid] = new_id()
    for eid, name, dept, title, mgr, role in PEOPLE:
        email = name.lower().replace("'", "").replace("á", "a").replace(" ", ".") + "@example.com"
        await db.employees.insert_one({
            "id": emp_ids[eid], "employee_id": eid, "full_name": name, "email": email, "department_id": dept_ids[dept],
            "designation": title, "manager_id": emp_ids.get(mgr), "working_schedule": "Mon-Fri 09:00-18:00", "timezone": "UTC",
            "role": role, "status": "active", "screenshots_enabled": False, "clerk_user_id": None, "created_at": t, "is_sample": True})
    sessions, breaks, activity = [], [], []
    today = t.date()
    for offset in range(6, 0, -1):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        for eid, *_ in PEOPLE:
            if rnd.random() < 0.08:
                continue
            emp = emp_ids[eid]
            start = datetime.combine(day, time(8, 30), tzinfo=timezone.utc) + timedelta(minutes=rnd.randint(0, 75))
            end = start + timedelta(minutes=rnd.randint(420, 560))
            auto = rnd.random() < 0.06
            sid = new_id()
            sessions.append({"id": sid, "employee_id": emp, "start": start, "end": end, "last_seen": end, "status": "closed",
                             "source": "agent", "devices": ["agent:sample"], "auto_closed": auto,
                             "close_reason": "missed_logout" if auto else "agent_logout", "outside_schedule": False, "is_sample": True})
            bstart = start + timedelta(minutes=rnd.randint(180, 260))
            bend = bstart + timedelta(minutes=rnd.randint(20, 50))
            breaks.append({"id": new_id(), "employee_id": emp, "session_id": sid, "start": bstart, "end": bend, "is_sample": True})
            level = rnd.uniform(0.55, 0.92)
            m = start
            while m < end:
                if not (bstart <= m < bend):
                    act = rnd.random() < level
                    activity.append({"employee_id": emp, "minute": m.replace(second=0, microsecond=0), "day": day.isoformat(),
                                     "session_id": sid, "active": act, "sources": ["agent"],
                                     "mouse": rnd.randint(20, 300) if act else 0, "clicks": rnd.randint(2, 40) if act else 0,
                                     "keys": rnd.randint(10, 200) if act else 0})
                m += timedelta(minutes=1)
    if sessions:
        await db.sessions.insert_many(sessions)
        await db.breaks.insert_many(breaks)
        await db.activity.insert_many(activity)
    await db.meta.insert_one({"id": "sample_seed", "seeded_at": t})
    logger.info("Seeded sample data: %d sessions, %d activity minutes", len(sessions), len(activity))
