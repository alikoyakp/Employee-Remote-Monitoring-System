# Built-in email+password auth: login/cookies, refresh, logout, brute force, password links, change password, inactive
import uuid

import pytest
import requests

from conftest import BASE_URL

PW = "WorkPulse-Test-2026!"
ADMIN_EMAIL = "wp.admin+clerk_test@example.com"
ORIGIN = BASE_URL


def new_session():
    s = requests.Session()
    s.headers.update({"Origin": ORIGIN})
    return s


def bearer(s, r):
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return r


@pytest.fixture(scope="module")
def throwaway(admin, mongo):
    """TEST_ employee created via API; removed (by id) with its tokens/attempts afterwards."""
    tag = uuid.uuid4().hex[:6]
    email = f"test_auth_{tag}@example.com"
    r = admin.post(f"{BASE_URL}/api/employees", json={"employee_id": f"TEST_AUTH_{tag}", "full_name": f"TEST_Auth {tag}",
                                                      "email": email, "role": "employee", "status": "active"})
    assert r.status_code == 200, r.text
    emp = r.json()
    yield emp
    mongo.employees.delete_one({"id": emp["id"]})
    mongo.password_tokens.delete_many({"employee_id": emp["id"]})
    mongo.login_attempts.delete_many({"identifier": {"$regex": f"test_auth_{tag}"}})
    mongo.audit_logs.delete_many({"target_id": emp["id"]})


class TestLogin:
    def test_bcrypt_hash_format(self, mongo, tokens):
        doc = mongo.employees.find_one({"email": ADMIN_EMAIL}, {"password_hash": 1})
        assert doc["password_hash"].startswith("$2b$")

    def test_login_returns_tokens_no_cookies(self, tokens):
        s = new_session()
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": PW})
        assert r.status_code == 200 and r.json()["ok"] is True and r.json()["access_token"] and r.json()["refresh_token"]
        assert "access_token=" not in r.headers.get("set-cookie", "")
        assert s.get(f"{BASE_URL}/api/me").status_code == 401
        bearer(s, r)
        me = s.get(f"{BASE_URL}/api/me")
        assert me.status_code == 200 and me.json()["email"] == ADMIN_EMAIL
        assert "password_hash" not in me.json()

    def test_email_case_insensitive(self, tokens):
        r = new_session().post(f"{BASE_URL}/api/auth/login", json={"email": "  WP.Admin+clerk_test@EXAMPLE.com ", "password": PW})
        assert r.status_code == 200

    def test_me_unauthenticated(self):
        assert requests.get(f"{BASE_URL}/api/me").status_code == 401

    def test_wrong_password_generic(self, throwaway, mongo):
        r = new_session().post(f"{BASE_URL}/api/auth/login", json={"email": throwaway["email"], "password": "nope-1234"})
        assert r.status_code == 401 and "Invalid email or password" in r.json()["detail"]
        r2 = new_session().post(f"{BASE_URL}/api/auth/login", json={"email": "nobody_x@example.com", "password": "nope-1234"})
        assert r2.status_code == 401 and r2.json()["detail"] == r.json()["detail"]
        mongo.login_attempts.delete_many({"identifier": {"$regex": "nobody_x@example.com"}})

    def test_brute_force_lock(self, throwaway, mongo):
        email = throwaway["email"]
        mongo.login_attempts.delete_many({"identifier": {"$regex": email.replace("+", "\\+")}})
        codes = [new_session().post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "bad-pass-1"}).status_code
                 for _ in range(5)]
        assert codes == [401] * 5
        r = new_session().post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "bad-pass-1"})
        assert r.status_code == 429, r.text
        mongo.login_attempts.delete_many({"identifier": {"$regex": email}})


class TestRefreshLogout:
    def test_refresh_and_logout(self, tokens):
        s = new_session()
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": PW})
        assert r.status_code == 200
        s2 = new_session()
        r2 = s2.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": r.json()["refresh_token"]})
        assert r2.status_code == 200 and r2.json()["access_token"]
        bearer(s2, r2)
        assert s2.get(f"{BASE_URL}/api/me").status_code == 200
        assert s.post(f"{BASE_URL}/api/auth/logout").status_code == 200

    def test_refresh_without_token(self):
        assert requests.post(f"{BASE_URL}/api/auth/refresh").status_code == 401

    def test_access_token_cannot_refresh(self, tokens):
        r = new_session().post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": tokens["TEST_ADM"]["token"]})
        assert r.status_code == 401


class TestPasswordLinks:
    def test_link_flow(self, admin, employee, throwaway):
        assert employee.post(f"{BASE_URL}/api/auth/password-link/{throwaway['id']}").status_code == 403
        r1 = admin.post(f"{BASE_URL}/api/auth/password-link/{throwaway['id']}")
        assert r1.status_code == 200 and r1.json()["path"].startswith("/set-password?token=")
        tok1 = r1.json()["path"].split("token=")[1]
        info = requests.get(f"{BASE_URL}/api/auth/link-info", params={"token": tok1})
        assert info.status_code == 200 and info.json()["email"] == throwaway["email"]
        # new link invalidates old one
        tok2 = admin.post(f"{BASE_URL}/api/auth/password-link/{throwaway['id']}").json()["path"].split("token=")[1]
        assert requests.get(f"{BASE_URL}/api/auth/link-info", params={"token": tok1}).status_code == 400
        assert requests.post(f"{BASE_URL}/api/auth/set-password", json={"token": tok1, "password": "Valid-pass-1"}).status_code == 400
        # weak password rejected, link not consumed
        assert requests.post(f"{BASE_URL}/api/auth/set-password", json={"token": tok2, "password": "short"}).status_code == 400
        s = new_session()
        r = s.post(f"{BASE_URL}/api/auth/set-password", json={"token": tok2, "password": "Valid-pass-1"})
        assert r.status_code == 200
        bearer(s, r)
        assert s.get(f"{BASE_URL}/api/me").json()["email"] == throwaway["email"]
        # reuse
        assert requests.post(f"{BASE_URL}/api/auth/set-password", json={"token": tok2, "password": "Valid-pass-2"}).status_code == 400
        # can login with new password
        assert new_session().post(f"{BASE_URL}/api/auth/login", json={"email": throwaway["email"], "password": "Valid-pass-1"}).status_code == 200

    def test_link_unknown_employee(self, admin):
        assert admin.post(f"{BASE_URL}/api/auth/password-link/does-not-exist").status_code == 404

    def test_link_info_bad_token(self):
        assert requests.get(f"{BASE_URL}/api/auth/link-info", params={"token": "garbage"}).status_code == 400


class TestChangePassword:
    def test_change_password(self, admin, throwaway, mongo):
        # ensure password exists (from link flow or set directly via a fresh link)
        tok = admin.post(f"{BASE_URL}/api/auth/password-link/{throwaway['id']}").json()["path"].split("token=")[1]
        s = new_session()
        sp = s.post(f"{BASE_URL}/api/auth/set-password", json={"token": tok, "password": "Valid-pass-1"})
        assert sp.status_code == 200
        bearer(s, sp)
        old_access = sp.json()["access_token"]
        old_refresh = sp.json()["refresh_token"]
        bad = s.post(f"{BASE_URL}/api/auth/change-password", json={"current_password": "wrong-1", "new_password": "Another-pass-2"})
        assert bad.status_code == 400
        weak = s.post(f"{BASE_URL}/api/auth/change-password", json={"current_password": "Valid-pass-1", "new_password": "abcdefgh"})
        assert weak.status_code == 400
        ok = s.post(f"{BASE_URL}/api/auth/change-password", json={"current_password": "Valid-pass-1", "new_password": "Another-pass-2"})
        assert ok.status_code == 200
        bearer(s, ok)
        assert s.get(f"{BASE_URL}/api/me").status_code == 200
        assert requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {old_access}"}).status_code == 401
        assert requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401
        assert new_session().post(f"{BASE_URL}/api/auth/login", json={"email": throwaway["email"], "password": "Another-pass-2"}).status_code == 200


class TestInactive:
    def test_inactive_cannot_login(self, admin, throwaway, mongo):
        # self-contained: give the throwaway a password via a fresh link (classes may run on different xdist workers)
        tok = admin.post(f"{BASE_URL}/api/auth/password-link/{throwaway['id']}").json()["path"].split("token=")[1]
        assert requests.post(f"{BASE_URL}/api/auth/set-password", json={"token": tok, "password": "Another-pass-2"}).status_code == 200
        s = new_session()
        lr = s.post(f"{BASE_URL}/api/auth/login", json={"email": throwaway["email"], "password": "Another-pass-2"})
        assert lr.status_code == 200
        bearer(s, lr)
        body = {k: throwaway[k] for k in ("employee_id", "full_name", "email")}
        body.update(role="employee", status="inactive")
        assert admin.put(f"{BASE_URL}/api/employees/{throwaway['id']}", json=body).status_code == 200
        assert s.get(f"{BASE_URL}/api/me").status_code == 401  # existing session killed
        r = new_session().post(f"{BASE_URL}/api/auth/login", json={"email": throwaway["email"], "password": "Another-pass-2"})
        assert r.status_code == 401
        assert admin.post(f"{BASE_URL}/api/auth/password-link/{throwaway['id']}").status_code == 400
        mongo.login_attempts.delete_many({"identifier": {"$regex": throwaway["email"]}})
