import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { errMsg, useApi } from "@/lib/api";

const TrackerCtx = createContext(null);

function useBrowserActivity(enabled, api, onSent) {
  const counts = useRef({ mouse: 0, clicks: 0, keys: 0, last: null });
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    let lastMove = 0;
    const bump = (k) => {
      counts.current[k] += 1;
      counts.current.last = new Date().toISOString();
    };
    const onMove = () => {
      const t = Date.now();
      if (t - lastMove > 200) {
        lastMove = t;
        bump("mouse");
      }
    };
    const onClick = () => bump("clicks");
    // Only the fact that a key was pressed is counted; the key itself is never read.
    const onKey = () => bump("keys");
    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("wheel", onMove, { passive: true });
    window.addEventListener("click", onClick);
    window.addEventListener("keydown", onKey);
    const send = async () => {
      const c = counts.current;
      counts.current = { mouse: 0, clicks: 0, keys: 0, last: null };
      try {
        await api.post("/tracking/heartbeat", { mouse: c.mouse, clicks: c.clicks, keys: c.keys, last_interaction_at: c.last, device: "browser" });
        onSent();
      } catch {}
    };
    const first = setTimeout(send, 3000);
    const id = setInterval(send, 60000);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("wheel", onMove);
      window.removeEventListener("click", onClick);
      window.removeEventListener("keydown", onKey);
      clearTimeout(first);
      clearInterval(id);
    };
  }, [enabled, api, onSent]);
}

export function TrackerProvider({ children }) {
  const api = useApi();
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const r = await api.get("/tracking/me");
      setState(r.data);
    } catch {}
  }, [api]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, [refresh]);

  const monitoring = !!state?.session && !state?.break;
  useBrowserActivity(monitoring, api, refresh);

  const act = async (path, msg) => {
    setBusy(true);
    try {
      await api.post(path, path.endsWith("clock-in") ? { device: "browser" } : {});
      toast.success(msg);
      await refresh();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const value = {
    state, monitoring, busy, refresh,
    clockIn: () => act("/tracking/clock-in", "Clocked in - monitoring started"),
    clockOut: () => act("/tracking/clock-out", "Clocked out - monitoring stopped"),
    breakStart: () => act("/tracking/break/start", "Break started - monitoring paused"),
    breakEnd: () => act("/tracking/break/end", "Welcome back - monitoring resumed"),
  };
  return <TrackerCtx.Provider value={value}>{children}</TrackerCtx.Provider>;
}

export const useTracker = () => useContext(TrackerCtx);
