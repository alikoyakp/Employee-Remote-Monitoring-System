"""Helper for UI test: `setup` enables screenshots for TEST_EMP with token (signed out); `shot` clocks in + uploads; `cleanup` reverts."""
import json, os, subprocess, sys
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
HERE = os.path.dirname(__file__)
load_dotenv(os.path.join(HERE, "..", ".env")); load_dotenv(os.path.join(HERE, "..", "..", "frontend", ".env"))
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
out = subprocess.run([sys.executable, os.path.join(HERE, "test_users.py"), "--tokens"], capture_output=True, text=True, cwd=os.path.join(HERE, "..")).stdout
T = {j["employee_id"]: j["token"] for j in (json.loads(l) for l in out.strip().splitlines())}
A = {"Authorization": f"Bearer {T['TEST_ADM']}"}; E = {"Authorization": f"Bearer {T['TEST_EMP']}"}
emp_id = requests.get(f"{API}/me", headers=E).json()["id"]
TOKFILE = "/tmp/ui_agent_tok"
sys.path.insert(0, HERE); from test_capture_storage import PNG  # noqa
cmd = sys.argv[1]
if cmd == "setup":
    tok = requests.post(f"{API}/me/agent-token", headers=E).json()["token"]; open(TOKFILE, "w").write(tok)
    print(requests.patch(f"{API}/employees/{emp_id}/screenshots", json={"enabled": True}, headers=A).status_code)
elif cmd == "shot":
    h = {"X-Agent-Token": open(TOKFILE).read()}
    print(requests.post(f"{API}/agent/clock-in", json={"device": "ui"}, headers=h).status_code)
    mongo.screenshots.update_many({"employee_id": emp_id}, {"$set": {"taken_at": datetime.now(timezone.utc) - timedelta(hours=5)}})
    r = requests.post(f"{API}/agent/screenshot", files={"file": ("s.png", PNG, "image/png")}, headers=h); print(r.status_code, r.text)
elif cmd == "cleanup":
    h = {"X-Agent-Token": open(TOKFILE).read()}
    print(requests.patch(f"{API}/employees/{emp_id}/screenshots", json={"enabled": False}, headers=A).status_code)
    print(requests.post(f"{API}/agent/clock-out", headers=h).status_code)
    print(requests.delete(f"{API}/me/agent-token", headers=E).status_code)
