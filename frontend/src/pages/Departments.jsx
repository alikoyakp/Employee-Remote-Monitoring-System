import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, PageHeader, Panel } from "@/components/Page";
import { errMsg, useApi } from "@/lib/api";

export default function Departments() {
  const api = useApi();
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ code: "", name: "", description: "" });
  const load = useCallback(() => api.get("/departments").then((r) => setRows(r.data)), [api]);
  useEffect(() => {
    load();
  }, [load]);
  const openForm = (d) => {
    setEditing(d || {});
    setForm(d ? { code: d.code, name: d.name, description: d.description || "" } : { code: "", name: "", description: "" });
  };
  const save = async () => {
    try {
      if (editing.id) await api.put(`/departments/${editing.id}`, form);
      else await api.post("/departments", form);
      toast.success("Department saved");
      setEditing(null);
      load();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  const remove = async (d) => {
    if (!window.confirm(`Delete department ${d.name}?`)) return;
    try {
      await api.delete(`/departments/${d.id}`);
      toast.success("Department deleted");
      load();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <div data-testid="departments-page">
      <PageHeader title="Departments" subtitle="Department codes are used to map employees during import.">
        <Button onClick={() => openForm(null)} data-testid="add-department-button"><Plus className="mr-1 h-4 w-4" /> Add department</Button>
      </PageHeader>
      <Panel>
        {!rows.length ? <Empty>No departments yet.</Empty> : (
          <Table data-testid="departments-table">
            <TableHeader><TableRow><TableHead>Code</TableHead><TableHead>Name</TableHead><TableHead className="hidden md:table-cell">Description</TableHead><TableHead className="text-right">Employees</TableHead><TableHead /></TableRow></TableHeader>
            <TableBody>
              {rows.map((d) => (
                <TableRow key={d.id} data-testid={`department-row-${d.code}`}>
                  <TableCell className="font-mono text-xs">{d.code}</TableCell>
                  <TableCell className="font-medium">{d.name}</TableCell>
                  <TableCell className="hidden text-muted-foreground md:table-cell">{d.description}</TableCell>
                  <TableCell className="text-right font-mono">{d.employee_count}</TableCell>
                  <TableCell className="whitespace-nowrap text-right">
                    <Button size="icon" variant="ghost" onClick={() => openForm(d)} data-testid={`edit-department-${d.code}`}><Pencil className="h-4 w-4" /></Button>
                    <Button size="icon" variant="ghost" onClick={() => remove(d)} data-testid={`delete-department-${d.code}`}><Trash2 className="h-4 w-4 text-red-400" /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent data-testid="department-dialog">
          <DialogHeader><DialogTitle>{editing?.id ? "Edit department" : "Add department"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label>Code</Label><Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} data-testid="dept-form-code" /></div>
            <div className="space-y-1.5"><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="dept-form-name" /></div>
            <div className="space-y-1.5"><Label>Description</Label><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="dept-form-description" /></div>
          </div>
          <DialogFooter><Button onClick={save} data-testid="dept-form-save">Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
