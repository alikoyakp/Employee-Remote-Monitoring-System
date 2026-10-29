import { useCallback, useEffect, useState } from "react";
import { Activity, Building2, Coffee, Clock, Moon, UserCheck, Users, Wifi } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Empty, PageHeader, Panel, StatCard } from "@/components/Page";
import { StatusPill } from "@/components/StatusPill";
import { fmtMin, fmtTime, sinceText, useApi } from "@/lib/api";

function Kpis({ t }) {
  const cards = [
    ["Employees", t.employees, Users, "text-indigo-300", "kpi-employees"],
    ["Departments", t.departments, Building2, "text-indigo-300", "kpi-departments"],
    ["Logged in", t.logged_in, Wifi, "text-emerald-300", "kpi-logged-in"],
    ["Active", t.active, Activity, "text-emerald-300", "kpi-active"],
    ["Idle", t.idle, Moon, "text-amber-300", "kpi-idle"],
    ["On break", t.on_break, Coffee, "text-blue-300", "kpi-on-break"],
    ["Present today", `${t.present_today}/${t.employees}`, UserCheck, "text-cyan-300", "kpi-present"],
    ["Hours today", t.hours_today, Clock, "text-indigo-300", "kpi-hours"],
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
      {cards.map(([l, v, I, tone, id], i) => <StatCard key={id} label={l} value={v} icon={I} tone={tone} testId={id} delay={i * 40} />)}
    </div>
  );
}

function LiveBoard({ board }) {
  if (!board.length) return <Empty>No employees yet. Import or add employees to get started.</Empty>;
  return (
    <div className="max-h-[460px] overflow-auto scrollbar-thin">
      <Table data-testid="live-status-board">
        <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Status</TableHead><TableHead className="hidden md:table-cell">Department</TableHead><TableHead className="hidden sm:table-cell">Since</TableHead><TableHead className="hidden md:table-cell">Last input</TableHead><TableHead className="text-right">Today</TableHead></TableRow></TableHeader>
        <TableBody>
          {board.map((b) => (
            <TableRow key={b.id} data-testid={`board-row-${b.employee_id}`}>
              <TableCell><div className="font-medium">{b.full_name}</div><div className="text-xs text-muted-foreground">{b.designation}</div></TableCell>
              <TableCell><StatusPill status={b.status} /></TableCell>
              <TableCell className="hidden text-muted-foreground md:table-cell">{b.department || "—"}</TableCell>
              <TableCell className="hidden font-mono text-xs sm:table-cell">{fmtTime(b.session_start)}</TableCell>
              <TableCell className="hidden text-xs text-muted-foreground md:table-cell">{sinceText(b.last_interaction_at)}</TableCell>
              <TableCell className="text-right font-mono text-xs">{fmtMin(b.today_worked_min)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function Dashboard() {
  const api = useApi();
  const [data, setData] = useState(null);
  const load = useCallback(() => api.get("/dashboard").then((r) => setData(r.data)).catch(() => {}), [api]);
  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);
  if (!data) return <div className="h-40 animate-pulse rounded-xl bg-card" />;
  return (
    <div data-testid="dashboard-page">
      <PageHeader title="Workforce overview" subtitle="Live status refreshes every 30 seconds." />
      <Kpis t={data.totals} />
      <div className="mt-6 grid gap-6 xl:grid-cols-5">
        <Panel title="Live status board" className="xl:col-span-3" testId="live-board-panel"><LiveBoard board={data.board} /></Panel>
        <div className="flex flex-col gap-6 xl:col-span-2">
          <Panel title="Last 7 days - hours" testId="trend-panel">
            <div className="h-56">
              <ResponsiveContainer>
                <BarChart data={data.trend.map((d) => ({ ...d, day: d.day.slice(5) }))}>
                  <CartesianGrid stroke="hsl(217 19% 17%)" vertical={false} />
                  <XAxis dataKey="day" tickLine={false} axisLine={false} />
                  <YAxis tickLine={false} axisLine={false} width={30} />
                  <Tooltip cursor={{ fill: "hsl(217 19% 15%)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="active_h" name="Active h" stackId="a" fill="#10B981" />
                  <Bar dataKey="idle_h" name="Idle h" stackId="a" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel title="Departments today" testId="dept-panel">
            <div className="space-y-3">
              {data.departments.map((d) => (
                <div key={d.department} className="flex items-center justify-between text-sm">
                  <span>{d.department}</span>
                  <span className="font-mono text-xs text-muted-foreground">{d.online}/{d.employees} online · {d.worked_h}h</span>
                </div>
              ))}
              {!data.departments.length && <p className="text-sm text-muted-foreground">No departments yet.</p>}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
