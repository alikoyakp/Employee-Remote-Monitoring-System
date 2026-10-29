import { Coffee, LogIn, LogOut, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTracker } from "@/context/TrackerContext";
import { StatusPill } from "@/components/StatusPill";

export function ClockWidget({ compact = false, prefix = "" }) {
  const { state, busy, clockIn, clockOut, breakStart, breakEnd } = useTracker();
  if (!state) return null;
  const inSession = !!state.session;
  return (
    <div className="flex items-center gap-2" data-testid={`${prefix}clock-widget`}>
      {!compact && <StatusPill status={state.status} testId={`${prefix}my-status-pill`} />}
      {!inSession && (
        <Button size="sm" disabled={busy} onClick={clockIn} data-testid={`${prefix}clock-in-button`} className="rounded-full bg-emerald-600 text-white hover:bg-emerald-500">
          <LogIn className="mr-1 h-4 w-4" /> Clock in
        </Button>
      )}
      {inSession && !state.break && (
        <Button size="sm" variant="secondary" disabled={busy} onClick={breakStart} data-testid={`${prefix}break-start-button`} className="rounded-full">
          <Coffee className="mr-1 h-4 w-4" /> Break
        </Button>
      )}
      {inSession && state.break && (
        <Button size="sm" disabled={busy} onClick={breakEnd} data-testid={`${prefix}break-end-button`} className="rounded-full bg-blue-600 text-white hover:bg-blue-500">
          <Play className="mr-1 h-4 w-4" /> Resume
        </Button>
      )}
      {inSession && (
        <Button size="sm" variant="outline" disabled={busy} onClick={clockOut} data-testid={`${prefix}clock-out-button`} className="rounded-full">
          <LogOut className="mr-1 h-4 w-4" /> Clock out
        </Button>
      )}
    </div>
  );
}

export function MonitoringBanner() {
  const { state } = useTracker();
  if (!state?.session) return null;
  if (state.break) {
    return (
      <div data-testid="monitoring-paused-banner" className="mb-6 flex items-center gap-3 rounded-xl border border-blue-500/40 bg-blue-950/40 px-4 py-2.5 text-sm text-blue-200">
        <Coffee className="h-4 w-4" /> On break - activity monitoring and screenshots are paused.
      </div>
    );
  }
  return (
    <div data-testid="monitoring-active-banner" className="mb-6 flex flex-col gap-1 rounded-xl border border-emerald-500/40 bg-emerald-950/30 px-4 py-2.5 text-sm text-emerald-200 sm:flex-row sm:items-center sm:justify-between">
      <span className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-emerald-400 pulse-dot" />
        <strong className="font-semibold">Monitoring active</strong> - counting mouse, click and key activity (no keystrokes or typed content are recorded).
      </span>
      <span className="font-mono text-xs text-emerald-300/80" data-testid="banner-screenshot-state">
        Screenshots: {state.screenshots_enabled ? `on, every ${state.screenshot_interval_min} min (desktop agent)` : "off"}
      </span>
    </div>
  );
}
