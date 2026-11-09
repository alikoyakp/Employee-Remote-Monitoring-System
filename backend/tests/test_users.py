"""Ensures the TEST_ QA accounts exist with a known password; with --tokens prints a Bearer access token per account.
Usage: python tests/test_users.py [--tokens]   (preview only)"""
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from core import create_token, hash_password  # noqa: E402

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
PASSWORD = "WorkPulse-Test-2026!"
USERS = [
    ("TEST_ADM", "Test Admin", "wp.admin+clerk_test@example.com", "admin", None),
    ("TEST_MGR", "Test Manager", "wp.manager+clerk_test@example.com", "manager", None),
    ("TEST_EMP", "Test Employee", "wp.employee+clerk_test@example.com", "employee", "TEST_MGR"),
]


def ensure(eid, name, email, role, mgr):
    existing = db.employees.find_one({"employee_id": eid}) or {}
    eng = db.departments.find_one({"code": "ENG"})
    mgr_id = db.employees.find_one({"employee_id": mgr})["id"] if mgr else None
    upd = {"full_name": name, "email": email, "role": role, "status": "active", "manager_id": mgr_id,
           "notice_acknowledged_at": existing.get("notice_acknowledged_at") or datetime.now(timezone.utc)}
    if not existing.get("password_hash"):
        upd.update(password_hash=hash_password(PASSWORD), password_version=existing.get("password_version", 0) + 1)
    db.employees.update_one({"employee_id": eid}, {"$set": upd, "$setOnInsert": {
        "id": f"test-{eid.lower()}", "employee_id": eid, "department_id": eng["id"] if eng else None, "designation": "QA account",
        "working_schedule": "Mon-Sun 00:00-23:59", "timezone": "UTC", "screenshots_enabled": False,
        "created_at": datetime.now(timezone.utc)}}, upsert=True)
    return db.employees.find_one({"employee_id": eid}, {"_id": 0})


if __name__ == "__main__":
    for spec in USERS:
        emp = ensure(*spec)
        if "--tokens" in sys.argv:
            print(json.dumps({"employee_id": spec[0], "role": spec[3], "email": spec[2], "password": PASSWORD,
                              "token": create_token(emp, "access")}))
        else:
            print(spec[0], spec[2])
