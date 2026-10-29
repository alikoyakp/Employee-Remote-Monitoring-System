import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Search, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Empty, PageHeader, Panel } from "@/components/Page";
import { RoleBadge, StatusPill } from "@/components/StatusPill";
import { PickSelect, deptOptions } from "@/components/PickSelect";
import { EmployeeDialog } from "@/components/EmployeeDialog";
import { useMe } from "@/context/MeContext";
import { errMsg, useApi } from "@/lib/api";

export default function Employees() {
  const api = useApi();
  const { me } = useMe();
  const isAdmin = me.role === "admin";
  const [rows, setRows] = useState(null);
  const [all, setAll] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");
  const [role, setRole] = useState("");
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    const [f, a, d] = await Promise.all([
      api.get("/employees", { params: { q: q || undefined, department_id: dept || undefined, role: role || undefined } }),
      api.get("/employees"), api.get("/departments"),
    ]);
    setRows(f.data);
    setAll(a.data);
    setDepartments(d.data);
  }, [api, q, dept, role]);

  useEffect(() => {
    const t = setTimeout(() => load().catch((e) => toast.error(errMsg(e))), 250);
    return () => clearTimeout(t);
  }, [load]);

  const toggleShots = async (emp, enabled) => {
    try {
      await api.patch(`/employees/${emp.id}/screenshots`, { enabled });
      toast.success(`Screenshots ${enabled ? "enabled" : "disabled"} for ${emp.full_name}`);
      load();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <div data-testid="employees-page">
      <PageHeader title="Employees" subtitle={isAdmin ? "Manage profiles, managers, schedules and per-user screenshot capture." : "Your direct reports."}>
        {isAdmin && <Button variant="outline" asChild data-testid="employees-import-link"><Link to="/import"><Upload className="mr-1 h-4 w-4" /> Import</Link></Button>}
        {isAdmin && <Button onClick={() => { setEditing(null); setOpen(true); }} data-testid="add-employee-button"><Plus className="mr-1 h-4 w-4" /> Add employee</Button>}
      </PageHeader>
      <Panel>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search name, email, ID…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="employee-search-input" />
          </div>
          <PickSelect value={dept} onChange={setDept} options={deptOptions(departments)} allLabel="All departments" testId="employee-dept-filter" />
          <PickSelect value={role} onChange={setRole} options={[{ value: "admin", label: "Admin" }, { value: "manager", label: "Manager" }, { value: "employee", label: "Employee" }]} allLabel="All roles" testId="employee-role-filter" />
        </div>
        {rows && !rows.length && <Empty testId="employees-empty">No employees match these filters.</Empty>}
        {rows && rows.length > 0 && (
          <div className="overflow-x-auto scrollbar-thin">
            <Table data-testid="employees-table">
              <TableHeader><TableRow>
                <TableHead>Employee</TableHead><TableHead>Role</TableHead><TableHead className="hidden md:table-cell">Department</TableHead>
                <TableHead className="hidden lg:table-cell">Manager</TableHead><TableHead className="hidden lg:table-cell">Schedule</TableHead>
                <TableHead>Live</TableHead><TableHead>Screenshots</TableHead>{isAdmin && <TableHead />}
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((e) => (
                  <TableRow key={e.id} data-testid={`employee-row-${e.employee_id}`} className={e.status === "inactive" ? "opacity-50" : ""}>
                    <TableCell>
                      <div className="font-medium">{e.full_name}</div>
                      <div className="font-mono text-[11px] text-muted-foreground">{e.employee_id} · {e.email}</div>
                    </TableCell>
                    <TableCell><RoleBadge role={e.role} /></TableCell>
                    <TableCell className="hidden md:table-cell">{e.department_name || "—"}<div className="text-xs text-muted-foreground">{e.designation}</div></TableCell>
                    <TableCell className="hidden lg:table-cell">{e.manager_name || "—"}</TableCell>
                    <TableCell className="hidden font-mono text-xs lg:table-cell">{e.working_schedule}</TableCell>
                    <TableCell><StatusPill status={e.status === "inactive" ? "closed" : e.live_status} label={e.status === "inactive" ? "Inactive" : undefined} /></TableCell>
                    <TableCell>
                      <Switch checked={!!e.screenshots_enabled} disabled={!isAdmin} onCheckedChange={(v) => toggleShots(e, v)} data-testid={`screenshot-toggle-${e.employee_id}`} />
                    </TableCell>
                    {isAdmin && (
                      <TableCell><Button size="icon" variant="ghost" onClick={() => { setEditing(e); setOpen(true); }} data-testid={`edit-employee-${e.employee_id}`}><Pencil className="h-4 w-4" /></Button></TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>
      <EmployeeDialog open={open} onOpenChange={setOpen} employee={editing} employees={all} departments={departments} onSaved={load} />
    </div>
  );
}
