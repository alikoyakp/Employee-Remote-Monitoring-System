#!/usr/bin/env python3
"""ERM System desktop agent.

Runs on the employee's computer while they work. It:
  * counts mouse movements, clicks and key presses (never WHICH keys, never typed text or passwords)
  * sends a heartbeat every 60 s while the employee is clocked in and not on a break
  * captures a full-desktop screenshot at the interval set by the administrator, ONLY if screenshots are
    enabled for this employee, they are clocked in, not on a break and inside their working schedule

Install:   pip install requests pynput mss pillow
Run:       python erm_agent.py --server https://YOUR-APP-URL --token wpa_xxx [--clock-in] [--clock-out-on-exit]

Permissions: macOS needs Screen Recording + Accessibility (Input Monitoring) for the terminal/python.
Linux needs an X11 session (Wayland blocks global input hooks and screenshots).
"""
import argparse
import io
import platform
import sys
import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests pynput mss pillow")


class Counter:
    def __init__(self):
        self.lock = threading.Lock()
        self.mouse = self.clicks = self.keys = 0
        self.last = None
        self._last_move = 0.0

    def on_move(self, *_):
        t = time.time()
        if t - self._last_move >= 0.2:  # throttle: at most 5 movement events / second
            self._last_move = t
            self._bump("mouse")

    def on_click(self, *args):
        if len(args) >= 4 and args[3]:
            self._bump("clicks")

    def on_scroll(self, *_):
        self._bump("mouse")

    def on_key(self, _key):  # the key value is ignored on purpose
        self._bump("keys")

    def _bump(self, field):
        with self.lock:
            setattr(self, field, getattr(self, field) + 1)
            self.last = datetime.now(timezone.utc)

    def drain(self):
        with self.lock:
            out = {"mouse": self.mouse, "clicks": self.clicks, "keys": self.keys,
                   "last_interaction_at": self.last.isoformat() if self.last else None}
            self.mouse = self.clicks = self.keys = 0
            return out


def start_listeners(counter):
    try:
        from pynput import keyboard, mouse
    except ImportError:
        print("! pynput not installed - activity counting disabled (pip install pynput)")
        return
    mouse.Listener(on_move=counter.on_move, on_click=counter.on_click, on_scroll=counter.on_scroll).start()
    keyboard.Listener(on_press=counter.on_key).start()


def grab_screenshot():
    import mss
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])  # monitor 0 = all screens combined
        try:
            from PIL import Image
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            img.thumbnail((1920, 1920))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=70)
            return buf.getvalue(), "image/jpeg", "screenshot.jpg"
        except ImportError:
            return mss.tools.to_png(shot.rgb, shot.size), "image/png", "screenshot.png"


def main():
    p = argparse.ArgumentParser(description="ERM System desktop agent")
    p.add_argument("--server", required=True, help="ERM System web address, e.g. https://example.com")
    p.add_argument("--token", required=True, help="Agent token from the 'Desktop agent' page")
    p.add_argument("--clock-in", action="store_true", help="Clock in when the agent starts")
    p.add_argument("--clock-out-on-exit", action="store_true", help="Clock out when the agent stops")
    p.add_argument("--accept-notice", action="store_true", help="Skip the interactive monitoring notice prompt")
    a = p.parse_args()
    api = a.server.rstrip("/") + "/api/agent"
    s = requests.Session()
    s.headers.update({"X-Agent-Token": a.token, "User-Agent": f"ERMSystemAgent/1.0 ({platform.system()})"})
    device = platform.node() or "desktop"

    r = s.get(f"{api}/config", timeout=20)
    if r.status_code == 401:
        sys.exit("Invalid agent token. Generate a new one on the 'Desktop agent' page.")
    r.raise_for_status()
    cfg = r.json()
    print("=" * 70)
    print(f"ERM System agent for {cfg['employee']['full_name']} ({cfg['employee']['employee_id']})")
    print("MONITORING NOTICE:\n" + cfg["monitoring_notice"])
    print(f"Screenshots for your account: {'ENABLED' if cfg['screenshots_enabled'] else 'disabled'}")
    print("=" * 70)
    if not a.accept_notice and input("Type 'yes' to acknowledge and start: ").strip().lower() != "yes":
        sys.exit("Agent not started.")
    if a.clock_in:
        s.post(f"{api}/clock-in", json={"device": device}, timeout=20).raise_for_status()
        print("Clocked in.")

    counter = Counter()
    start_listeners(counter)
    last_shot = 0.0
    try:
        while True:
            try:
                cfg = s.get(f"{api}/config", timeout=20).json()
                payload = {**counter.drain(), "device": device}
                if cfg["clocked_in"] and not cfg["on_break"]:
                    s.post(f"{api}/heartbeat", json=payload, timeout=20)
                    print(f"[{datetime.now():%H:%M}] MONITORING ACTIVE - status {cfg['status']}")
                    interval = cfg["screenshot_interval_min"] * 60
                    if cfg["screenshots_enabled"] and cfg["within_schedule"] and time.time() - last_shot >= interval:
                        data, ctype, name = grab_screenshot()
                        resp = s.post(f"{api}/screenshot", files={"file": (name, data, ctype)}, timeout=60)
                        if resp.ok or resp.status_code == 429:
                            last_shot = time.time()
                        detail = "" if resp.ok else f" ({resp.json().get('detail', '') if 'json' in resp.headers.get('content-type', '') else resp.text[:120]})"
                        print(f"  screenshot -> {resp.status_code}{detail}")
                    elif not cfg["screenshots_enabled"]:
                        print("  screenshots are disabled for your account by the admin")
                    elif not cfg["within_schedule"]:
                        print("  outside your working schedule - no screenshot")
                else:
                    print(f"[{datetime.now():%H:%M}] monitoring paused ({'on break' if cfg['on_break'] else 'not clocked in'})")
            except requests.RequestException as e:
                print(f"  network error: {e} (will retry)")
            time.sleep(cfg.get("heartbeat_interval_sec", 60))
    except KeyboardInterrupt:
        if a.clock_out_on_exit:
            s.post(f"{api}/clock-out", timeout=20)
            print("Clocked out.")
        print("Agent stopped.")


if __name__ == "__main__":
    main()
