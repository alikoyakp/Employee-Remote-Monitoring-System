import { useEffect, useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Empty, PageHeader, Panel } from "@/components/Page";
import { StatusPill } from "@/components/StatusPill";
import { PickSelect, empOptions } from "@/components/PickSelect";
import { useLookups, useMe } from "@/context/MeContext";
import { daysAgo, fmtDateTime, fmtMin, fmtTime, isoDay, useApi } from "@/lib/api";

export default function Attendance() {
  const api = useApi();
  const { me } = useMe();
  const { employees } = useLookups();
  const [start, setStart] = useState(daysAgo(6));
  const [end, setEnd] = useState(isoDay());
  const [emp, setEmp] = useState("");
  const [rows, setRows] = useState(null);
  useEffect(() => {
    api.get("/sessions", { params: { start, end, employee_id: emp || undefined } }).then((r) => setRows(r.data)).catch(() => setRows([]));
  }, [api, start, end, emp]);
  return (
    <div data-testid="attendance-page">
      <PageHeader title="Attendance sessions" subtitle="Login/logout times, duration and breaks. Sessions with no activity are closed automatically as missed logouts." />
      <Panel>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="sm:w-44" data-testid="attendance-start-date" />
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="sm:w-44" data-testid="attendance-end-date" />
          {me.role !== "employee" && <PickSelect value={emp} onChange={setEmp} options={empOptions(employees)} allLabel="All employees" testId="attendance-employee-filter" className="w-full sm:w-64" />}
        </div>
        {rows && !rows.length && <Empty testId="attendance-empty">No sessions in this range.</Empty>}
        {rows && rows.length > 0 && (
          <div className="overflow-x-auto scrollbar-thin">
            <Table data-testid="attendance-table">
              <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Login</TableHead><TableHead>Logout</TableHead><TableHead>Duration</TableHead><TableHead>Breaks</TableHead><TableHead>Worked</TableHead><TableHead className="hidden md:table-cell">Devices</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map((s) => (
                  <TableRow key={s.id} data-testid={`session-row-${s.id}`}>
                    <TableCell><div className="font-medium">{s.employee_name}</div><div className="font-mono text-[11px] text-muted-foreground">{s.employee_code}</div></TableCell>
                    <TableCell className="whitespace-nowrap text-xs">{fmtDateTime(s.start)}</TableCell>
                    <TableCell className="whitespace-nowrap text-xs">{s.end ? fmtTime(s.end) : "—"}</TableCell>
                    <TableCell className="font-mono text-xs">{fmtMin(s.duration_min)}</TableCell>
                    <TableCell className="font-mono text-xs">{fmtMin(s.break_min)}</TableCell>
                    <TableCell className="font-mono text-xs">{fmtMin(s.worked_min)}</TableCell>
                    <TableCell className="hidden font-mono text-[11px] text-muted-foreground md:table-cell">{(s.devices || []).join(", ")}</TableCell>
                    <TableCell><StatusPill status={s.auto_closed ? "missed" : s.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>
    </div>
  );
}
