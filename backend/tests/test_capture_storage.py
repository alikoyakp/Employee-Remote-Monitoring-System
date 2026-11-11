# Screenshot storage backends (local mode unit tests), 503 on storage failure, capture-status endpoint, agent E2E
import importlib
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
HERE = os.path.dirname(__file__)
BACKEND = os.path.join(HERE, "..")
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


# Local storage mode - runs core in a subprocess so STORAGE_BACKEND=local is read at import
LOCAL_SCRIPT = textwrap.dedent("""
    import os, sys
    sys.path.insert(0, %r)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(%r, '.env'))
    os.environ['STORAGE_BACKEND'] = 'local'
    os.environ['SCREENSHOT_DIR'] = %r
    import core
    assert core.STORAGE_BACKEND == 'local', core.STORAGE_BACKEND
    chk = core.storage_check()
    assert chk == {'backend': 'local', 'ok': True, 'error': ''}, chk
    p = 'workpulse/screenshots/e1/2026-01-01/a.png'
    assert core.put_object(p, b'PNGDATA', 'image/png') == {'path': p}
    assert os.path.isfile(os.path.join(%r, p))
    data, ct = core.get_object(p)
    assert data == b'PNGDATA' and ct == 'image/png', (data, ct)
    core.put_object('x/b.jpg', b'J', 'image/jpeg')
    assert core.get_object('x/b.jpg')[1] == 'image/jpeg'
    for bad in ['../evil.png', '../../etc/passwd', '/etc/passwd', 'a/../../evil.png', '']:
        try:
            core.put_object(bad, b'x', 'image/png'); print('TRAVERSAL_NOT_BLOCKED', repr(bad)); sys.exit(2)
        except (ValueError, IsADirectoryError, PermissionError) as e:
            pass
        try:
            core.get_object(bad); print('TRAVERSAL_GET_NOT_BLOCKED', repr(bad)); sys.exit(2)
        except (ValueError, IsADirectoryError, PermissionError):
            pass
    core.delete_local_object(p)
    assert not os.path.exists(os.path.join(%r, p))
    core.delete_local_object(p)  # missing ok
    try:
        core.delete_local_object('../outside.png'); sys.exit(3)
    except ValueError:
        pass
    print('LOCAL_OK')
""")


def test_local_storage_mode(tmp_path):
    d = str(tmp_path / "x")
    script = LOCAL_SCRIPT % (BACKEND, BACKEND, d, d, d)
    env = {k: v for k, v in os.environ.items()}
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=BACKEND, env=env)
    assert r.returncode == 0 and "LOCAL_OK" in r.stdout, r.stdout + r.stderr


def test_local_storage_check_unwritable(tmp_path):
    d = tmp_path / "ro"
    d.mkdir()
    (d / "f").write_text("")
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {BACKEND!r})
        from dotenv import load_dotenv; load_dotenv(os.path.join({BACKEND!r}, '.env'))
        os.environ['STORAGE_BACKEND'] = 'local'; os.environ['SCREENSHOT_DIR'] = {str(d / 'f' / 'sub')!r}
        import core
        c = core.storage_check(); print(c); assert c['ok'] is False and c['backend'] == 'local' and c['error']
        print('RO_OK')
    """)
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=BACKEND)
    assert "RO_OK" in r.stdout, r.stdout + r.stderr


def test_default_backend_selection():
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {BACKEND!r})
        from dotenv import load_dotenv; load_dotenv(os.path.join({BACKEND!r}, '.env'))
        os.environ.pop('STORAGE_BACKEND', None); os.environ.pop('EMERGENT_LLM_KEY', None)
        import core; print('B=' + core.STORAGE_BACKEND)
    """)
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=BACKEND,
                       env={k: v for k, v in os.environ.items() if k not in ("STORAGE_BACKEND", "EMERGENT_LLM_KEY")})
    assert "B=local" in r.stdout, r.stdout + r.stderr


# Capture status endpoint (role gating + shape)
class TestCaptureStatus:
    def test_roles(self, admin, manager, employee):
        assert requests.get(f"{API}/admin/capture-status").status_code == 401
        assert manager.get(f"{API}/admin/capture-status").status_code == 403
        assert employee.get(f"{API}/admin/capture-status").status_code == 403
        r = admin.get(f"{API}/admin/capture-status")
        assert r.status_code == 200
        d = r.json()
        assert d["storage"]["backend"] == "emergent" and d["storage"]["ok"] is True and d["storage"]["error"] == ""
        assert isinstance(d["employees"], list)
        for row in d["employees"]:
            for k in ("has_agent_token", "agent_last_used_at", "status", "within_schedule", "last_screenshot_at"):
                assert k in row
            assert "agent_token_hash" not in row


# Full agent flow: token -> enable -> clock in -> upload -> gallery + capture status; cleanup
class TestAgentE2E:
    def test_flow(self, admin, employee, mongo):
        emp_uuid = employee.get(f"{API}/me").json()["id"]
        tok = employee.post(f"{API}/me/agent-token").json()["token"]
        h = {"X-Agent-Token": tok}
        try:
            r = admin.patch(f"{API}/employees/{emp_uuid}/screenshots", json={"enabled": True})
            assert r.status_code == 200 and r.json()["screenshots_enabled"] is True
            row = next(x for x in admin.get(f"{API}/admin/capture-status").json()["employees"] if x["employee_id"] == "TEST_EMP")
            assert row["has_agent_token"] is True and row["status"] == "signed_out"
            assert requests.post(f"{API}/agent/clock-in", json={"device": "pytest"}, headers=h).status_code == 200
            mongo.screenshots.update_many({"employee_id": emp_uuid}, {"$set": {"taken_at": datetime.now(timezone.utc) - timedelta(hours=5)}})
            r = requests.post(f"{API}/agent/screenshot", files={"file": ("s.png", PNG, "image/png")}, headers=h)
            assert r.status_code == 200, r.text
            sid = r.json()["id"]
            assert any(s["id"] == sid for s in admin.get(f"{API}/screenshots").json())
            img = admin.get(f"{API}/screenshots/{sid}/image")
            assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
            row = next(x for x in admin.get(f"{API}/admin/capture-status").json()["employees"] if x["employee_id"] == "TEST_EMP")
            assert row["last_screenshot_at"] and row["agent_last_used_at"] and row["status"] in ("active", "idle")
            assert row["within_schedule"] is True
        finally:
            admin.patch(f"{API}/employees/{emp_uuid}/screenshots", json={"enabled": False})
            requests.post(f"{API}/agent/clock-out", headers=h)
            employee.delete(f"{API}/me/agent-token")
        assert requests.get(f"{API}/agent/config", headers=h).status_code == 401
        assert not any(x["employee_id"] == "TEST_EMP" for x in admin.get(f"{API}/admin/capture-status").json()["employees"])


# 503 when storage put fails (in-process TestClient with put_object patched)
def test_screenshot_503_on_storage_failure(monkeypatch):
    sys.path.insert(0, BACKEND)
    from fastapi.testclient import TestClient
    import server
    import tracking
    import core

    async def fake_open(_id):
        return {"id": "TEST_fake_session"}

    def boom(*a, **k):
        raise RuntimeError("storage down")

    monkeypatch.setattr(tracking, "open_session", fake_open)
    monkeypatch.setattr(tracking, "within_schedule", lambda *a, **k: True)
    monkeypatch.setattr(tracking, "put_object", boom)
    server.app.dependency_overrides[core.agent_member] = lambda: {
        "id": "TEST_nonexistent_503", "employee_id": "TEST_503", "full_name": "x", "screenshots_enabled": True}
    try:
        c = TestClient(server.app, raise_server_exceptions=False)  # no context manager: skip startup (seeding)
        if True:
            r = c.post("/api/agent/screenshot", files={"file": ("s.png", PNG, "image/png")})
        assert r.status_code == 503, r.text
        assert "storage" in r.json()["detail"].lower()
    finally:
        server.app.dependency_overrides.clear()
