import { Link } from "react-router-dom";
import { Activity, Camera, Clock, Coffee, Moon, MonitorDown } from "lucide-react";
import { Panel, PageHeader, StatCard } from "@/components/Page";
import { ClockWidget } from "@/components/ClockWidget";
import { useMe } from "@/context/MeContext";
import { useTracker } from "@/context/TrackerContext";
import { fmtMin, fmtTime } from "@/lib/api";

function Info({ label, value, testId }) {
  return (
    <div className="flex justify-between gap-4 border-b py-2 text-sm last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right" data-testid={testId}>{value || "—"}</span>
    </div>
  );
}

export default function MyDay() {
  const { me } = useMe();
  const { state } = useTracker();
  const today = state?.today || {};
  return (
    <div data-testid="my-day-page">
      <PageHeader title={`Hello, ${me.full_name.split(" ")[0]}`} subtitle="Your attendance and activity for today." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Work session" className="lg:col-span-2" testId="session-panel">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm text-muted-foreground">{state?.session ? `Clocked in at ${fmtTime(state.session.start)}` : "You are not clocked in"}</div>
              <div className="mt-1 font-heading text-4xl font-semibold tabular-nums" data-testid="today-worked">{fmtMin(today.worked_min)}</div>
              <div className="text-xs text-muted-foreground">worked today · schedule {state?.working_schedule} {state && !state.within_schedule && "(outside schedule now)"}</div>
            </div>
            <ClockWidget />
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="Active" value={fmtMin(today.active_min)} icon={Activity} tone="text-emerald-300" testId="today-active" />
            <StatCard label="Idle" value={fmtMin(today.idle_min)} icon={Moon} tone="text-amber-300" testId="today-idle" />
            <StatCard label="Breaks" value={fmtMin(today.break_min)} icon={Coffee} tone="text-blue-300" testId="today-break" />
            <StatCard label="Idle after" value={`${state?.idle_threshold_min ?? "-"} min`} icon={Clock} testId="idle-threshold" />
          </div>
        </Panel>
        <Panel title="My profile" testId="profile-panel">
          <Info label="Employee ID" value={me.employee_id} testId="profile-employee-id" />
          <Info label="Email" value={me.email} />
          <Info label="Department" value={me.department_name} />
          <Info label="Designation" value={me.designation} />
          <Info label="Manager" value={me.manager_name} />
          <Info label="Schedule" value={`${me.working_schedule} (${me.timezone})`} />
        </Panel>
      </div>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Panel title="What is monitored" testId="monitoring-info-panel">
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li>• Only while you are clocked in and not on a break.</li>
            <li>• Counts of mouse movements, clicks and key presses - never which keys or what you type.</li>
            <li>• In the browser, only activity inside this ERM System tab is counted. Install the desktop agent to count activity across your whole computer.</li>
          </ul>
        </Panel>
        <Panel title="Screenshots" testId="screenshot-info-panel">
          <div className="flex items-start gap-3">
            <Camera className={me.screenshots_enabled ? "h-5 w-5 text-amber-300" : "h-5 w-5 text-muted-foreground"} />
            <p className="text-sm text-muted-foreground" data-testid="my-screenshot-status">
              {me.screenshots_enabled
                ? `Enabled for your account by an administrator: the desktop agent captures one full-desktop screenshot every ${state?.screenshot_interval_min ?? 60} minutes during working hours.`
                : "Disabled for your account. No screenshots are captured."}
            </p>
          </div>
          <Link to="/agent" className="mt-4 inline-flex items-center gap-2 text-sm text-indigo-300 hover:text-indigo-200" data-testid="my-day-agent-link"><MonitorDown className="h-4 w-4" /> Desktop agent setup</Link>
        </Panel>
      </div>
    </div>
  );
}
