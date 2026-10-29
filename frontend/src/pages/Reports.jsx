import { useCallback, useEffect, useState } from "react";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Empty, PageHeader, Panel, StatCard } from "@/components/Page";
import { PickSelect, deptOptions, empOptions, mgrOptions } from "@/components/PickSelect";
import { useLookups, useMe } from "@/context/MeContext";
import { blobError, daysAgo, downloadFile, errMsg, fmtMin, fmtTime, isoDay, useApi } from "@/lib/api";

export default function Reports() {
  const api = useApi();
  const { me } = useMe();
  const { employees, departments } = useLookups();
  const [f, setF] = useState({ period: "daily", start: daysAgo(6), end: isoDay(), employee_id: "", department_id: "", manager_id: "" });
  const [data, setData] = useState(null);
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v?.target ? v.target.value : v }));
  const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v));
  const load = useCallback(() => {
    api.get("/reports", { params }).then((r) => setData(r.data)).catch((e) => toast.error(errMsg(e)));
  }, [api, JSON.stringify(params)]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    load();
  }, [load]);
  const exp = async (format) => {
    try {
      await downloadFile(api, "/reports/export", { ...params, format }, `workpulse_${f.period}_${f.start}_${f.end}.${format}`);
      toast.success(`Exported ${format.toUpperCase()}`);
    } catch (e) {
      toast.error(await blobError(e));
    }
  };
  const t = data?.totals || {};
  return (
    <div data-testid="reports-page">
      <PageHeader title="Reports" subtitle="Attendance and activity summaries. Days are grouped in UTC.">
        <Button variant="outline" onClick={() => exp("csv")} data-testid="export-csv-button"><Download className="mr-1 h-4 w-4" /> CSV</Button>
        <Button variant="outline" onClick={() => exp("xlsx")} data-testid="export-xlsx-button"><Download className="mr-1 h-4 w-4" /> Excel</Button>
      </PageHeader>
      <Panel className="mb-6">
        <div className="flex flex-col flex-wrap gap-2 md:flex-row">
          <Tabs value={f.period} onValueChange={set("period")}>
            <TabsList>{["daily", "weekly", "monthly"].map((p) => <TabsTrigger key={p} value={p} className="capitalize" data-testid={`period-${p}`}>{p}</TabsTrigger>)}</TabsList>
          </Tabs>
          <Input type="date" value={f.start} onChange={set("start")} className="md:w-40" data-testid="report-start-date" />
          <Input type="date" value={f.end} onChange={set("end")} className="md:w-40" data-testid="report-end-date" />
          {me.role !== "employee" && (
            <>
              <PickSelect value={f.employee_id} onChange={set("employee_id")} options={empOptions(employees)} allLabel="All employees" testId="report-employee-filter" />
              <PickSelect value={f.department_id} onChange={set("department_id")} options={deptOptions(departments)} allLabel="All departments" testId="report-department-filter" />
              <PickSelect value={f.manager_id} onChange={set("manager_id")} options={mgrOptions(employees)} allLabel="All managers" testId="report-manager-filter" />
            </>
          )}
        </div>
      </Panel>
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatCard label="Employees" value={t.employees} testId="report-total-employees" />
            <StatCard label="Worked" value={fmtMin(t.worked_min)} testId="report-total-worked" />
            <StatCard label="Active" value={fmtMin(t.active_min)} tone="text-emerald-300" testId="report-total-active" />
            <StatCard label="Idle" value={fmtMin(t.idle_min)} testId="report-total-idle" />
            <StatCard label="Missed logouts" value={t.auto_closed} testId="report-total-missed" />
          </div>
          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            <Panel title="Daily trend (hours)" className="xl:col-span-2">
              <div className="h-64">
                <ResponsiveContainer>
                  <BarChart data={data.trend.map((d) => ({ day: d.day.slice(5), active: +(d.active_min / 60).toFixed(1), idle: +(d.idle_min / 60).toFixed(1) }))}>
                    <CartesianGrid stroke="hsl(217 19% 17%)" vertical={false} />
                    <XAxis dataKey="day" tickLine={false} axisLine={false} />
                    <YAxis tickLine={false} axisLine={false} width={30} />
                    <Tooltip cursor={{ fill: "hsl(217 19% 15%)" }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="active" name="Active h" stackId="a" fill="#10B981" />
                    <Bar dataKey="idle" name="Idle h" stackId="a" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            <Panel title="By department" testId="report-departments">
              {data.departments.map((d) => (
                <div key={d.department} className="flex justify-between border-b py-2 text-sm last:border-0">
                  <span>{d.department} <span className="text-xs text-muted-foreground">({d.employees})</span></span>
                  <span className="font-mono text-xs">{fmtMin(d.worked_min)} · {d.worked_min ? Math.round((100 * d.active_min) / d.worked_min) : 0}% active</span>
                </div>
              ))}
              {!data.departments.length && <p className="text-sm text-muted-foreground">No data.</p>}
            </Panel>
          </div>
          <Panel title="Employee summary" className="mt-6">
            {!data.rows.length ? <Empty testId="report-empty">No activity in this range.</Empty> : (
              <div className="max-h-[520px] overflow-auto scrollbar-thin">
                <Table data-testid="report-table">
                  <TableHeader><TableRow>
                    <TableHead>Period</TableHead><TableHead>Employee</TableHead><TableHead className="hidden md:table-cell">Department</TableHead>
                    <TableHead>Days</TableHead><TableHead>Worked</TableHead><TableHead>Active</TableHead><TableHead>Idle</TableHead><TableHead>Breaks</TableHead>
                    <TableHead>Active %</TableHead>{f.period === "daily" && <TableHead>In / Out</TableHead>}
                  </TableRow></TableHeader>
                  <TableBody>
                    {data.rows.map((r) => (
                      <TableRow key={`${r.period}-${r.employee_ref}`}>
                        <TableCell className="whitespace-nowrap font-mono text-xs">{r.period}</TableCell>
                        <TableCell className="whitespace-nowrap">{r.employee_name}</TableCell>
                        <TableCell className="hidden text-muted-foreground md:table-cell">{r.department}</TableCell>
                        <TableCell className="font-mono text-xs">{r.days_present}</TableCell>
                        <TableCell className="font-mono text-xs">{fmtMin(r.worked_min)}</TableCell>
                        <TableCell className="font-mono text-xs text-emerald-300">{fmtMin(r.active_min)}</TableCell>
                        <TableCell className="font-mono text-xs text-amber-300">{fmtMin(r.idle_min)}</TableCell>
                        <TableCell className="font-mono text-xs">{fmtMin(r.break_min)}</TableCell>
                        <TableCell className="font-mono text-xs">{r.productivity_pct}%</TableCell>
                        {f.period === "daily" && <TableCell className="whitespace-nowrap font-mono text-xs">{fmtTime(r.first_in)} / {r.last_out ? fmtTime(r.last_out) : "—"}</TableCell>}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
