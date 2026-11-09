"""WorkPulse API regression tests (roles, import, tracking, agent, screenshots, reports, settings)."""
import io
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from openpyxl import Workbook, load_workbook

from conftest import BASE_URL

sys.path.insert(0, os.path.dirname(__file__))
API = BASE_URL + "/api"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


@pytest.fixture(scope="module")
def ids(admin, manager, employee):
    return {k: c.get(f"{API}/me").json()["id"] for k, c in (("adm", admin), ("mgr", manager), ("emp", employee))}


# ---------- Auth / roles ----------
class TestRoles:
    def test_no_token_401(self):
        for p in ("/me", "/employees", "/dashboard", "/sessions"):
            assert requests.get(API + p).status_code == 401, p

    def test_me_roles(self, admin, manager, employee):
        assert admin.get(f"{API}/me").json()["role"] == "admin"
        assert manager.get(f"{API}/me").json()["role"] == "manager"
        me = employee.get(f"{API}/me").json()
        assert me["role"] == "employee" and "agent_token_hash" not in me and "_id" not in me

    def test_employee_forbidden(self, employee, ids):
        for m, p in (("get", "/dashboard"), ("get", "/screenshots"), ("get", "/import/history"),
                     ("get", "/import/template/employees"), ("get", "/audit-logs")):
            r = getattr(employee, m)(API + p)
            assert r.status_code == 403, (p, r.status_code)
        r = employee.put(f"{API}/settings", json={"idle_threshold_min": 5, "screenshot_interval_min": 60, "screenshot_retention_days": 30,
                                                  "activity_retention_days": 180, "offline_after_min": 5, "auto_close_after_min": 30,
                                                  "monitoring_notice": "x" * 40})
        assert r.status_code == 403
        files = {"file": ("a.csv", b"employee_id,full_name,work_email\n", "text/csv")}
        assert employee.post(f"{API}/import/preview", data={"kind": "employees"}, files=files).status_code == 403

    def test_employee_sees_only_self(self, employee, ids):
        emps = employee.get(f"{API}/employees").json()
        assert [e["id"] for e in emps] == [ids["emp"]]
        assert employee.get(f"{API}/employees/{ids['adm']}").status_code == 404

    def test_manager_scope(self, manager, ids, mongo):
        expected = {ids["mgr"]} | {e["id"] for e in mongo.employees.find({"manager_id": ids["mgr"]})}
        got = {e["id"] for e in manager.get(f"{API}/employees").json()}
        assert got == expected and ids["emp"] in got and ids["adm"] not in got
        sess = manager.get(f"{API}/sessions").json()
        assert all(s["employee_id"] in expected for s in sess)
        assert manager.get(f"{API}/dashboard").status_code == 200
        assert manager.get(f"{API}/audit-logs").status_code == 403

    def test_invalid_token_401(self):
        r = requests.get(f"{API}/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert r.status_code == 401


# ---------- Import ----------
def _csv(rows):
    return ("\n".join(",".join(r) for r in rows) + "\n").encode()


class TestImport:
    created_emp_ids = []

    def test_templates(self, admin):
        r = admin.get(f"{API}/import/template/employees?format=csv")
        assert r.status_code == 200 and r.text.startswith("employee_id,full_name,work_email")
        r = admin.get(f"{API}/import/template/combined?format=xlsx")
        wb = load_workbook(io.BytesIO(r.content))
        assert r.status_code == 200 and [s.title for s in wb.worksheets] == ["Departments", "Employees"]
        assert admin.get(f"{API}/import/template/combined?format=csv").status_code == 400

    def test_invalid_file_rejected(self, admin):
        name = f"TEST_bad_{uuid.uuid4().hex[:5]}.txt"
        r = admin.post(f"{API}/import/preview", data={"kind": "employees"}, files={"file": (name, b"hello", "text/plain")})
        assert r.status_code == 400
        hist = admin.get(f"{API}/import/history").json()
        h = next(h for h in hist if h["file_name"] == name)
        assert h["status"] == "rejected" and h["error"]

    def test_employee_csv_flow(self, admin, mongo):
        sfx = uuid.uuid4().hex[:4].upper()
        a, b = f"TEST_I{sfx}A", f"TEST_I{sfx}B"
        rows = [["employee_id", "full_name", "work_email", "department_code", "manager"],
                [a, "Test Imp A", f"test_{sfx}a@example.com", "ENG", ""],
                [b, "Test Imp B", f"test_{sfx}b@example.com", "ENG", a],
                [a, "Dup A", f"test_{sfx}c@example.com", "ENG", ""],
                ["TEST_X", "", "bademail", "NOPE", ""],
                ["EMP001", "Existing", mongo.employees.find_one({"employee_id": "EMP001"})["email"], "ENG", ""]]
        r = admin.post(f"{API}/import/preview", data={"kind": "employees"}, files={"file": ("TEST_emp.csv", _csv(rows), "text/csv")})
        assert r.status_code == 200, r.text
        p = r.json()
        st = {e["row"]: e["status"] for e in p["employees"]}
        assert st == {2: "valid", 3: "valid", 4: "duplicate", 5: "error", 6: "existing"}, st
        err = next(e for e in p["employees"] if e["row"] == 5)["errors"]
        assert any("full_name" in x for x in err) and any("email" in x for x in err) and any("NOPE" in x for x in err)
        c = admin.post(f"{API}/import/{p['id']}/commit", json={"overwrite_existing": False})
        assert c.status_code == 200
        s = c.json()["summary"]["employees"]
        assert s["created"] == 2 and s["skipped"] == 1 and s["duplicate"] == 1 and s["failed"] == 1 and s["updated"] == 0
        assert mongo.employees.find_one({"employee_id": "EMP001"})["full_name"] != "Existing"
        ea, eb = mongo.employees.find_one({"employee_id": a}), mongo.employees.find_one({"employee_id": b})
        TestImport.created_emp_ids += [ea["id"], eb["id"]]
        assert eb["manager_id"] == ea["id"] and ea["role"] == "manager"
        assert admin.post(f"{API}/import/{p['id']}/commit", json={"overwrite_existing": False}).status_code == 409
        d = admin.get(f"{API}/import/{p['id']}").json()
        assert d["status"] == "completed" and d["summary"]["employees"]["created"] == 2

    def test_overwrite(self, admin, mongo):
        emp = mongo.employees.find_one({"id": TestImport.created_emp_ids[0]})
        rows = [["employee_id", "full_name", "work_email", "department_code"],
                [emp["employee_id"], "Test Overwritten", emp["email"], "ENG"]]
        p = admin.post(f"{API}/import/preview", data={"kind": "employees"}, files={"file": ("TEST_ow.csv", _csv(rows), "text/csv")}).json()
        assert p["employees"][0]["status"] == "existing"
        c = admin.post(f"{API}/import/{p['id']}/commit", json={"overwrite_existing": True}).json()
        assert c["summary"]["employees"]["updated"] == 1
        assert mongo.employees.find_one({"id": emp["id"]})["full_name"] == "Test Overwritten"

    def test_combined_xlsx(self, admin, mongo):
        sfx = uuid.uuid4().hex[:4].upper()
        wb = Workbook()
        ws = wb.active
        ws.title = "Departments"
        ws.append(["department_code", "department_name", "description"])
        ws.append([f"TST{sfx}", f"TEST Dept {sfx}", "tmp"])
        ws2 = wb.create_sheet("Employees")
        ws2.append(["employee_id", "full_name", "work_email", "department_code", "manager"])
        ws2.append([f"TEST_C{sfx}", "Test Comb", f"test_c{sfx}@example.com", f"TST{sfx}", "EMP001"])
        buf = io.BytesIO()
        wb.save(buf)
        p = admin.post(f"{API}/import/preview", data={"kind": "combined"},
                       files={"file": ("TEST_comb.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert p.status_code == 200, p.text
        p = p.json()
        assert p["departments"][0]["status"] == "valid" and p["employees"][0]["status"] == "valid", p
        c = admin.post(f"{API}/import/{p['id']}/commit", json={"overwrite_existing": False}).json()
        assert c["summary"]["departments"]["created"] == 1 and c["summary"]["employees"]["created"] == 1
        dept = mongo.departments.find_one({"code": f"TST{sfx}"})
        e = mongo.employees.find_one({"employee_id": f"TEST_C{sfx}"})
        assert e["department_id"] == dept["id"]
        assert e["manager_id"] == mongo.employees.find_one({"employee_id": "EMP001"})["id"]
        TestImport.created_emp_ids.append(e["id"])
        TestImport.dept_id = dept["id"]

    def test_cleanup(self, mongo):
        emp002 = mongo.employees.find_one({"employee_id": "EMP002"})
        mongo.employees.delete_many({"id": {"$in": TestImport.created_emp_ids}})
        if getattr(TestImport, "dept_id", None):
            mongo.departments.delete_one({"id": TestImport.dept_id})
        # EMP002 may have been promoted to manager by the import - report state
        print("EMP002 role after import:", emp002.get("role"))


# ---------- Tracking ----------
class TestTracking:
    def test_flow(self, employee):
        employee.post(f"{API}/tracking/clock-out")
        assert employee.get(f"{API}/tracking/me").json()["status"] == "signed_out"
        r = employee.post(f"{API}/tracking/clock-in", json={"device": "pytest"})
        assert r.status_code == 200 and r.json()["status"] == "open"
        hb = employee.post(f"{API}/tracking/heartbeat", json={"mouse": 10, "clicks": 2, "keys": 5}).json()
        assert hb == {"tracking": True, "active": True}
        assert employee.get(f"{API}/tracking/me").json()["status"] == "active"
        assert employee.post(f"{API}/tracking/break/start").status_code == 200
        assert employee.post(f"{API}/tracking/break/start").status_code == 400
        me = employee.get(f"{API}/tracking/me").json()
        assert me["status"] == "on_break" and me["break"]
        assert employee.post(f"{API}/tracking/heartbeat", json={"mouse": 1}).json()["reason"] == "on_break"
        assert employee.post(f"{API}/tracking/break/end").status_code == 200
        assert employee.post(f"{API}/tracking/break/end").status_code == 400
        assert employee.post(f"{API}/tracking/clock-out").status_code == 200
        assert employee.get(f"{API}/tracking/me").json()["status"] == "signed_out"
        assert employee.post(f"{API}/tracking/clock-out").status_code == 400

    def test_missed_logout(self, employee, admin, mongo, ids):
        employee.post(f"{API}/tracking/clock-in", json={})
        mongo.sessions.update_one({"employee_id": ids["emp"], "status": "open"},
                                  {"$set": {"last_seen": datetime.now(timezone.utc) - timedelta(hours=3)}})
        sid = mongo.sessions.find_one({"employee_id": ids["emp"], "status": "open"})["id"]
        r = admin.post(f"{API}/admin/maintenance")
        assert r.status_code == 200 and r.json()["sessions_auto_closed"] >= 1
        s = mongo.sessions.find_one({"id": sid})
        assert s["status"] == "closed" and s["close_reason"] == "missed_logout" and s["auto_closed"]
        assert employee.post(f"{API}/admin/maintenance").status_code == 403


# ---------- Agent + screenshots ----------
class TestAgent:
    def test_agent_and_screenshots(self, employee, admin, manager, mongo, ids):
        admin.patch(f"{API}/employees/{ids['emp']}/screenshots", json={"enabled": False})
        tok = employee.post(f"{API}/me/agent-token").json()["token"]
        h = {"X-Agent-Token": tok}
        assert requests.get(f"{API}/agent/config").status_code == 401
        assert requests.get(f"{API}/agent/config", headers={"X-Agent-Token": "bad"}).status_code == 401
        cfg = requests.get(f"{API}/agent/config", headers=h).json()
        assert cfg["employee"]["employee_id"] == "TEST_EMP" and cfg["screenshots_enabled"] is False
        assert requests.post(f"{API}/agent/clock-in", json={"device": "pytest"}, headers=h).status_code == 200
        hb = requests.post(f"{API}/agent/heartbeat", json={"mouse": 5, "clicks": 1, "keys": 1}, headers=h).json()
        assert hb["tracking"] is True
        files = {"file": ("s.png", PNG, "image/png")}
        assert requests.post(f"{API}/agent/screenshot", files=files, headers=h).status_code == 403
        r = admin.patch(f"{API}/employees/{ids['emp']}/screenshots", json={"enabled": True})
        assert r.status_code == 200 and r.json()["screenshots_enabled"] is True
        try:
            # push existing shots back so interval gate passes
            mongo.screenshots.update_many({"employee_id": ids["emp"]}, {"$set": {"taken_at": datetime.now(timezone.utc) - timedelta(hours=5)}})
            r = requests.post(f"{API}/agent/screenshot", files={"file": ("s.png", PNG, "image/png")}, headers=h)
            assert r.status_code == 200, r.text
            shot_id = r.json()["id"]
            r2 = requests.post(f"{API}/agent/screenshot", files={"file": ("s.png", PNG, "image/png")}, headers=h)
            assert r2.status_code == 429
            assert any(s["id"] == shot_id for s in admin.get(f"{API}/screenshots").json())
            assert any(s["id"] == shot_id for s in manager.get(f"{API}/screenshots").json())
            before = mongo.audit_logs.count_documents({"action": "screenshot.view", "target_id": shot_id})
            ra = admin.get(f"{API}/screenshots/{shot_id}/image")
            assert ra.status_code == 200 and ra.content[:4] == b"\x89PNG"
            assert manager.get(f"{API}/screenshots/{shot_id}/image").status_code == 200
            assert employee.get(f"{API}/screenshots/{shot_id}/image").status_code == 403
            assert mongo.audit_logs.count_documents({"action": "screenshot.view", "target_id": shot_id}) == before + 2
        finally:
            admin.patch(f"{API}/employees/{ids['emp']}/screenshots", json={"enabled": False})
            requests.post(f"{API}/agent/clock-out", headers=h)


# ---------- Reports / settings / audit ----------
class TestReports:
    @pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
    def test_periods(self, admin, period):
        r = admin.get(f"{API}/reports", params={"period": period})
        assert r.status_code == 200
        d = r.json()
        assert d["period"] == period and isinstance(d["rows"], list) and "totals" in d

    def test_filters_and_scope(self, admin, employee, ids):
        r = admin.get(f"{API}/reports", params={"employee_id": ids["emp"]}).json()
        assert all(x["employee_ref"] == ids["emp"] for x in r["rows"])
        r = employee.get(f"{API}/reports").json()
        assert all(x["employee_ref"] == ids["emp"] for x in r["rows"])
        assert admin.get(f"{API}/reports", params={"period": "yearly"}).status_code == 400
        assert admin.get(f"{API}/reports", params={"start": "2026-02-10", "end": "2026-01-01"}).status_code == 400
        assert admin.get(f"{API}/reports", params={"start": "bad"}).status_code == 400

    def test_export(self, admin):
        r = admin.get(f"{API}/reports/export", params={"format": "csv", "period": "weekly"})
        assert r.status_code == 200 and r.text.startswith("Period,Employee ID")
        r = admin.get(f"{API}/reports/export", params={"format": "xlsx"})
        assert r.status_code == 200 and load_workbook(io.BytesIO(r.content)).active.title == "Report"
        assert admin.get(f"{API}/reports/export", params={"format": "pdf"}).status_code == 400

    def test_settings_validation(self, admin):
        cur = admin.get(f"{API}/settings").json()
        assert admin.put(f"{API}/settings", json={**cur, "idle_threshold_min": 0}).status_code == 400
        assert admin.put(f"{API}/settings", json={**cur, "screenshot_interval_min": 1000}).status_code == 400
        assert admin.put(f"{API}/settings", json={**cur, "monitoring_notice": "short"}).status_code == 400
        r = admin.put(f"{API}/settings", json=cur)
        assert r.status_code == 200 and r.json()["idle_threshold_min"] == cur["idle_threshold_min"]

    def test_audit_paging(self, admin):
        a = admin.get(f"{API}/audit-logs", params={"limit": 5}).json()
        b = admin.get(f"{API}/audit-logs", params={"limit": 5, "skip": 5}).json()
        assert a["total"] >= 10 and len(a["items"]) == 5 and a["items"][0]["id"] != b["items"][0]["id"]
        f = admin.get(f"{API}/audit-logs", params={"action": "screenshot.view"}).json()
        assert all(i["action"] == "screenshot.view" for i in f["items"])

    def test_dashboard(self, admin):
        d = admin.get(f"{API}/dashboard").json()
        assert d["totals"]["employees"] >= 15 and len(d["trend"]) == 7 and d["board"]

    def test_bad_inputs_no_500(self, admin, ids):
        r1 = admin.get(f"{API}/sessions", params={"start": "notadate"})
        r2 = admin.get(f"{API}/activity/timeline", params={"employee_id": ids["emp"], "date": "notadate"})
        assert r1.status_code < 500 and r2.status_code < 500, (r1.status_code, r2.status_code)
