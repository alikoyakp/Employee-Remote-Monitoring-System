# Clerk config endpoint + key validation (placeholder keys -> invalid_keys)
import os
import subprocess
import sys
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

SNIPPET = "import sys; sys.path.insert(0,'/app/backend'); import clerk_auth, json; print(json.dumps(clerk_auth.clerk_config()))"


def _run(env_over):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLERK_")}
    env.update(env_over)
    out = subprocess.run([sys.executable, "-c", SNIPPET], env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    import json
    return json.loads(out.stdout.strip().splitlines()[-1])


class TestClerkConfigLive:
    def test_preview_config_enabled(self):
        r = requests.get(f"{BASE_URL}/api/clerk/config", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert d["proxy_url"] == ""
        assert d["publishable_key"].startswith("pk_test_")
        assert "reason" not in d

    def test_protected_api_401_without_token(self):
        r = requests.get(f"{BASE_URL}/api/me", timeout=20)
        assert r.status_code in (401, 403)


class TestClerkConfigUnit:
    def test_placeholder_live_keys(self):
        d = _run({"CLERK_PUBLISHABLE_KEY": "pk_live_...", "CLERK_SECRET_KEY": "sk_live_..."})
        assert d == {"enabled": False, "reason": "invalid_keys", "publishable_key": "", "proxy_url": ""}

    def test_placeholder_secret_only(self):
        d = _run({"CLERK_PUBLISHABLE_KEY": "pk_test_" + "a" * 40, "CLERK_SECRET_KEY": "sk_test_..."})
        assert d["reason"] == "invalid_keys" and d["enabled"] is False

    def test_only_pk_set(self):
        d = _run({"CLERK_PUBLISHABLE_KEY": "pk_live_..."})
        assert d["reason"] == "invalid_keys"

    def test_no_keys(self):
        d = _run({})
        assert d["enabled"] is False and "reason" not in d

    def test_valid_live_keys_proxy(self):
        d = _run({"CLERK_PUBLISHABLE_KEY": "pk_live_Y2xlcmsuZXhhbXBsZS5jb20k", "CLERK_SECRET_KEY": "sk_live_" + "A1" * 20})
        assert d["enabled"] is True and d["proxy_url"] == "/api/__clerk"

    def test_valid_live_keys_proxy_disabled(self):
        d = _run({"CLERK_PUBLISHABLE_KEY": "pk_live_Y2xlcmsuZXhhbXBsZS5jb20k", "CLERK_SECRET_KEY": "sk_live_" + "A1" * 20,
                  "CLERK_USE_PROXY": "false"})
        assert d["enabled"] is True and d["proxy_url"] == ""

    def test_valid_test_keys(self):
        d = _run({"CLERK_PUBLISHABLE_KEY": "pk_test_Y2xlcmsuZXhhbXBsZS5jb20k", "CLERK_SECRET_KEY": "sk_test_" + "b" * 40})
        assert d["enabled"] is True and d["proxy_url"] == ""
