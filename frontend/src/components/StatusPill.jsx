import { cn } from "@/lib/utils";

const STYLES = {
  active: ["Active", "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", "bg-emerald-400"],
  idle: ["Idle", "bg-amber-500/15 text-amber-300 border-amber-500/30", "bg-amber-400"],
  on_break: ["On break", "bg-blue-500/15 text-blue-300 border-blue-500/30", "bg-blue-400"],
  offline: ["Offline", "bg-slate-500/15 text-slate-300 border-slate-500/30", "bg-slate-400"],
  signed_out: ["Not clocked in", "bg-slate-800/60 text-slate-400 border-slate-700", "bg-slate-600"],
  open: ["Open", "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", "bg-emerald-400"],
  closed: ["Closed", "bg-slate-500/15 text-slate-300 border-slate-500/30", "bg-slate-400"],
  missed: ["Missed logout", "bg-orange-500/15 text-orange-300 border-orange-500/30", "bg-orange-400"],
  valid: ["Valid", "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", "bg-emerald-400"],
  error: ["Error", "bg-red-500/15 text-red-300 border-red-500/30", "bg-red-400"],
  duplicate: ["Duplicate", "bg-orange-500/15 text-orange-300 border-orange-500/30", "bg-orange-400"],
  existing: ["Exists", "bg-blue-500/15 text-blue-300 border-blue-500/30", "bg-blue-400"],
};

export const STATUS_LABEL = Object.fromEntries(Object.entries(STYLES).map(([k, v]) => [k, v[0]]));

export function StatusPill({ status, label, testId }) {
  const [text, cls, dot] = STYLES[status] || [status, "bg-slate-800 text-slate-300 border-slate-700", "bg-slate-500"];
  return (
    <span data-testid={testId} className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium", cls)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", dot, status === "active" && "pulse-dot")} />
      {label || text}
    </span>
  );
}

export function RoleBadge({ role }) {
  const cls = { admin: "text-indigo-300 border-indigo-500/40 bg-indigo-500/10", manager: "text-cyan-300 border-cyan-500/40 bg-cyan-500/10" }[role] || "text-slate-300 border-slate-600 bg-slate-800/50";
  return <span className={cn("rounded-md border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider", cls)}>{role}</span>;
}
