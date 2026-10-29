"""Creates Clerk dev test users + matching employee records and prints session tokens / sign-in tickets.
Usage: python tests/clerk_test_users.py   (preview/dev instance only)"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
SK = os.environ["CLERK_SECRET_KEY"]
assert SK.startswith("sk_test_"), "dev instance only"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

USERS = [
    ("TEST_ADM", "Test Admin", "wp.admin+clerk_test@example.com", "admin", None),
    ("TEST_MGR", "Test Manager", "wp.manager+clerk_test@example.com", "manager", None),
    ("TEST_EMP", "Test Employee", "wp.employee+clerk_test@example.com", "employee", "TEST_MGR"),
]
PASSWORD = "WorkPulse-Test-2026!"


def bapi(path, body=None, method="POST"):
    req = urllib.request.Request("https://api.clerk.com/v1" + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers={"Authorization": "Bearer " + SK, "Content-Type": "application/json", "User-Agent": "emergent-test"})
    return json.load(urllib.request.urlopen(req))


def ensure(eid, name, email, role, mgr):
    found = bapi("/users?" + urllib.parse.urlencode({"email_address": email}), method="GET")
    user = found[0] if found else bapi("/users", {"email_address": [email], "password": PASSWORD, "skip_password_checks": True,
                                                  "first_name": name.split()[0], "last_name": name.split()[1]})
    eng = db.departments.find_one({"code": "ENG"})
    mgr_id = db.employees.find_one({"employee_id": mgr})["id"] if mgr else None
    db.employees.update_one({"employee_id": eid}, {"$set": {"full_name": name, "email": email, "role": role, "status": "active", "manager_id": mgr_id,
                                                             "clerk_user_id": user["id"], "env": "preview", "notice_acknowledged_at": datetime.now(timezone.utc)},
                                                    "$setOnInsert": {"id": f"test-{eid.lower()}", "employee_id": eid, "department_id": eng["id"] if eng else None,
                                                                     "designation": "QA account", "working_schedule": "Mon-Sun 00:00-23:59", "timezone": "UTC",
                                                                     "screenshots_enabled": False, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    return user


if __name__ == "__main__":
    for spec in USERS:
        u = ensure(*spec)
        if "--tokens" in sys.argv:
            s = bapi("/sessions", {"user_id": u["id"]})
            tok = bapi(f"/sessions/{s['id']}/tokens", {"expires_in_seconds": 3600})["jwt"]
            ticket = bapi("/sign_in_tokens", {"user_id": u["id"], "expires_in_seconds": 3600})["token"]
            print(json.dumps({"employee_id": spec[0], "role": spec[3], "token": tok, "ticket": ticket}))
        else:
            print(spec[0], spec[2], u["id"])
