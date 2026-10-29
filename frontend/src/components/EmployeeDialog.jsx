import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PickSelect, deptOptions } from "@/components/PickSelect";
import { errMsg, useApi } from "@/lib/api";

const BLANK = { employee_id: "", full_name: "", email: "", department_id: "", designation: "", manager_id: "", working_schedule: "Mon-Fri 09:00-18:00", timezone: "UTC", role: "employee", status: "active" };

function Field({ label, children }) {
  return <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">{label}</Label>{children}</div>;
}

export function EmployeeDialog({ open, onOpenChange, employee, employees, departments, onSaved }) {
  const api = useApi();
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open) {
      setForm(employee ? { ...BLANK, ...Object.fromEntries(Object.keys(BLANK).map((k) => [k, employee[k] ?? ""])) } : BLANK);
    }
  }, [open, employee]);
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v?.target ? v.target.value : v }));
  const save = async () => {
    setSaving(true);
    try {
      const body = { ...form, department_id: form.department_id || null, manager_id: form.manager_id || null };
      if (employee) await api.put(`/employees/${employee.id}`, body);
      else await api.post("/employees", body);
      toast.success(employee ? "Employee updated" : "Employee added");
      onOpenChange(false);
      onSaved();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSaving(false);
    }
  };
  const managers = employees.filter((e) => e.id !== employee?.id && e.status !== "inactive").map((e) => ({ value: e.id, label: `${e.full_name} (${e.employee_id})` }));
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" data-testid="employee-dialog">
        <DialogHeader><DialogTitle>{employee ? "Edit employee" : "Add employee"}</DialogTitle></DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Employee ID"><Input value={form.employee_id} onChange={set("employee_id")} data-testid="emp-form-employee-id" /></Field>
          <Field label="Full name"><Input value={form.full_name} onChange={set("full_name")} data-testid="emp-form-full-name" /></Field>
          <Field label="Work email (used to sign in)"><Input type="email" value={form.email} onChange={set("email")} data-testid="emp-form-email" /></Field>
          <Field label="Designation"><Input value={form.designation} onChange={set("designation")} data-testid="emp-form-designation" /></Field>
          <Field label="Department"><PickSelect value={form.department_id} onChange={set("department_id")} options={deptOptions(departments)} allLabel="No department" testId="emp-form-department" className="w-full" /></Field>
          <Field label="Reporting manager"><PickSelect value={form.manager_id} onChange={set("manager_id")} options={managers} allLabel="No manager" testId="emp-form-manager" className="w-full" /></Field>
          <Field label="Working schedule"><Input value={form.working_schedule} onChange={set("working_schedule")} placeholder="Mon-Fri 09:00-18:00" data-testid="emp-form-schedule" /></Field>
          <Field label="Timezone (IANA)"><Input value={form.timezone} onChange={set("timezone")} placeholder="Asia/Kolkata" data-testid="emp-form-timezone" /></Field>
          <Field label="Role"><PickSelect value={form.role} onChange={(v) => set("role")(v || "employee")} options={[{ value: "admin", label: "Admin" }, { value: "manager", label: "Manager" }, { value: "employee", label: "Employee" }]} testId="emp-form-role" className="w-full" /></Field>
          <Field label="Status"><PickSelect value={form.status} onChange={(v) => set("status")(v || "active")} options={[{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive (cannot sign in)" }]} testId="emp-form-status" className="w-full" /></Field>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="emp-form-cancel">Cancel</Button>
          <Button onClick={save} disabled={saving} data-testid="emp-form-save">{saving ? "Saving…" : "Save"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
