import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Input } from "@/components/ui/input";
import { Empty, PageHeader, Panel, StatCard } from "@/components/Page";
import { PickSelect, empOptions } from "@/components/PickSelect";
import { useLookups, useMe } from "@/context/MeContext";
import { fmtMin, fmtTime, isoDay, sinceText, useApi } from "@/lib/api";

export default function ActivityPage() {
  const api = useApi();
  const { me } = useMe();
  const { employees } = useLookups();
  const [emp, setEmp] = useState(me.id);
  const [date, setDate] = useState(isoDay());
  const [data, setData] = useState(null);
  useEffect(() => {
    if (emp) api.get("/activity/timeline", { params: { employee_id: emp, date } }).then((r) => setData(r.data)).catch(() => setData(null));
  }, [api, emp, date]);
  const active = data ? data.hours.reduce((n, h) => n + h.active, 0) : 0;
  const idle = data ? data.hours.reduce((n, h) => n + h.idle, 0) : 0;
  const totals = data ? data.hours.reduce((a, h) => ({ mouse: a.mouse + h.mouse, clicks: a.clicks + h.clicks, keys: a.keys + h.keys }), { mouse: 0, clicks: 0, keys: 0 }) : {};
  const hours = data ? data.hours.filter((h) => h.active + h.idle > 0 || (h.hour >= 7 && h.hour <= 19)).map((h) => ({ ...h, label: `${String(h.hour).padStart(2, "0")}:00` })) : [];
  return (
    <div data-testid="activity-page">
      <PageHeader title="Activity timeline" subtitle="Active vs idle minutes per hour (UTC), from activity event counts only." />
      <div className="mb-6 flex flex-col gap-2 sm:flex-row">
        {me.role !== "employee" && <PickSelect value={emp} onChange={(v) => setEmp(v || me.id)} options={empOptions(employees)} testId="activity-employee-select" className="w-full sm:w-72" />}
        <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="sm:w-44" data-testid="activity-date-input" />
      </div>
      {!data ? <Empty>No data.</Empty> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="Active" value={fmtMin(active)} tone="text-emerald-300" testId="activity-active-total" />
            <StatCard label="Idle" value={fmtMin(idle)} tone="text-amber-300" testId="activity-idle-total" />
            <StatCard label="Mouse / clicks / keys" value={<span className="text-lg">{totals.mouse} / {totals.clicks} / {totals.keys}</span>} testId="activity-event-totals" />
            <StatCard label="Last interaction" value={<span className="text-lg">{sinceText(data.last_interaction_at)}</span>} hint={`${data.screenshot_count} screenshot(s) that day`} testId="activity-last-interaction" />
          </div>
          <Panel title="Hourly activity" className="mt-6" testId="activity-chart-panel">
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={hours}>
                  <CartesianGrid stroke="hsl(217 19% 17%)" vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} />
                  <YAxis tickLine={false} axisLine={false} width={30} domain={[0, 60]} />
                  <Tooltip cursor={{ fill: "hsl(217 19% 15%)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="active" name="Active min" stackId="a" fill="#10B981" />
                  <Bar dataKey="idle" name="Idle min" stackId="a" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <Panel title="Sessions">
              {data.sessions.length ? data.sessions.map((s) => (
                <div key={s.id} className="flex justify-between border-b py-2 text-sm last:border-0">
                  <span>{fmtTime(s.start)} – {s.end ? fmtTime(s.end) : "now"}</span>
                  <span className="font-mono text-xs text-muted-foreground">{s.auto_closed ? "missed logout" : s.status}</span>
                </div>
              )) : <p className="text-sm text-muted-foreground">No sessions.</p>}
            </Panel>
            <Panel title="Breaks">
              {data.breaks.length ? data.breaks.map((b) => (
                <div key={b.id} className="flex justify-between border-b py-2 text-sm last:border-0">
                  <span>{fmtTime(b.start)} – {b.end ? fmtTime(b.end) : "ongoing"}</span>
                </div>
              )) : <p className="text-sm text-muted-foreground">No breaks.</p>}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
