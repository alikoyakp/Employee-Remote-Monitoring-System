# Iteration 4 auth fixes: XFF brute-force bypass, per-email lock, TTL index, link-info deleted employee, Bearer-token login/refresh
import uuid

import pytest
import requests

from conftest import BASE_URL

PW = "WorkPulse-Test-2026!"
ADMIN_EMAIL = "wp.admin+clerk_test@example.com"


@pytest.fixture(scope="module")
def victim(admin, mongo):
    tag = uuid.uuid4().hex[:6]
    email = f"test_fix_{tag}@example.com"
    r = admin.post(f"{BASE_URL}/api/employees", json={"employee_id": f"TEST_FIX_{tag}", "full_name": f"TEST_Fix {tag}",
                                                      "email": email, "role": "employee", "status": "active"})
    assert r.status_code == 200, r.text
    emp = r.json()
    yield emp
    mongo.employees.delete_one({"id": emp["id"]})
    mongo.password_tokens.delete_many({"employee_id": emp["id"]})
    mongo.login_attempts.delete_many({"identifier": {"$regex": f"test_fix_{tag}"}})
    mongo.audit_logs.delete_many({"target_id": emp["id"]})


class TestBruteForceFixes:
    def test_xff_spoof_does_not_bypass_lock(self, victim, mongo):
        email = victim["email"]
        mongo.login_attempts.delete_many({"identifier": {"$regex": email}})
        codes = [requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "bad-pass-1"},
                               headers={"X-Forwarded-For": f"10.9.9.{i}"}).status_code for i in range(7)]
        assert codes[:5] == [401] * 5, codes
        assert codes[5] == 429 and codes[6] == 429, codes
        # email-level lock row exists
        row = mongo.login_attempts.find_one({"identifier": f"email:{email}"})
        assert row and row.get("locked_until")
        # even correct password is refused while locked (account has no password anyway -> still 429)
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PW})
        assert r.status_code == 429 and "Too many" in r.json()["detail"]
        mongo.login_attempts.delete_many({"identifier": {"$regex": email}})

    def test_ttl_index_on_updated_at(self, mongo):
        idx = mongo.login_attempts.index_information()
        ttl = [v for v in idx.values() if v.get("key") == [("updated_at", 1)] and "expireAfterSeconds" in v]
        assert ttl, idx


class TestLinkInfoDeleted:
    def test_link_info_deleted_employee_returns_400(self, admin, mongo):
        tag = uuid.uuid4().hex[:6]
        r = admin.post(f"{BASE_URL}/api/employees", json={"employee_id": f"TEST_DEL_{tag}", "full_name": f"TEST_Del {tag}",
                                                          "email": f"test_del_{tag}@example.com", "role": "employee", "status": "active"})
        assert r.status_code == 200
        emp_id = r.json()["id"]
        try:
            tok = admin.post(f"{BASE_URL}/api/auth/password-link/{emp_id}").json()["path"].split("token=")[1]
            mongo.employees.delete_one({"id": emp_id})
            info = requests.get(f"{BASE_URL}/api/auth/link-info", params={"token": tok})
            assert info.status_code == 400, info.text
            sp = requests.post(f"{BASE_URL}/api/auth/set-password", json={"token": tok, "password": "Valid-pass-1"})
            assert sp.status_code == 400, sp.text
        finally:
            mongo.employees.delete_one({"id": emp_id})
            mongo.password_tokens.delete_many({"employee_id": emp_id})
            mongo.audit_logs.delete_many({"target_id": emp_id})


class TestBearerTokens:
    def test_login_bearer_and_refresh_body(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": PW})
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["access_token"], str) and isinstance(d["refresh_token"], str)
        me = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {d['access_token']}"})
        assert me.status_code == 200 and me.json()["email"] == ADMIN_EMAIL
        assert requests.get(f"{BASE_URL}/api/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
        rf = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": d["refresh_token"]})
        assert rf.status_code == 200 and rf.json()["access_token"]
        assert requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {rf.json()['access_token']}"}).status_code == 200

    def test_refresh_body_rejects_access_token_and_garbage(self):
        d = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": PW}).json()
        assert requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": d["access_token"]}).status_code == 401
        assert requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": "garbage"}).status_code == 401
        assert requests.post(f"{BASE_URL}/api/auth/refresh", json={}).status_code == 401

    def test_cors_preflight_foreign_frontend_host(self):
        origin = "https://1c87bdcc-198e-4d66-8e2f-0b8ea6ff4b1e.preview.emergentagent.com"
        r = requests.options(f"{BASE_URL}/api/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                                      "Access-Control-Request-Headers": "content-type,authorization"})
        print("preflight", r.status_code, dict(r.headers))
        assert r.status_code in (200, 204)
        assert r.headers.get("access-control-allow-origin") in ("*", origin)
