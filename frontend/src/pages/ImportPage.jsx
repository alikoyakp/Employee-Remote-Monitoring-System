import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Download, FileUp, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { PageHeader, Panel, StatCard } from "@/components/Page";
import { ImportResults } from "@/components/ImportResults";
import { blobError, downloadFile, errMsg, useApi } from "@/lib/api";

const KINDS = [
  ["departments", "Departments"],
  ["employees", "Employees"],
  ["combined", "Both (one .xlsx)"],
];

function Templates({ kind }) {
  const api = useApi();
  const dl = async (fmt) => {
    try {
      await downloadFile(api, `/import/template/${kind}`, { format: fmt }, `erm_system_${kind}_template.${fmt}`);
    } catch (e) {
      toast.error(await blobError(e));
    }
  };
  return (
    <div className="flex flex-wrap gap-2">
      {kind !== "combined" && <Button variant="outline" size="sm" onClick={() => dl("csv")} data-testid="download-template-csv"><Download className="mr-1 h-4 w-4" /> CSV template</Button>}
      <Button variant="outline" size="sm" onClick={() => dl("xlsx")} data-testid="download-template-xlsx"><Download className="mr-1 h-4 w-4" /> Excel template</Button>
    </div>
  );
}

function Summary({ s, label }) {
  if (!s) return null;
  return (
    <div>
      <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {Object.entries(s).map(([k, v]) => <StatCard key={k} label={k} value={v} testId={`summary-${label.toLowerCase()}-${k}`} />)}
      </div>
    </div>
  );
}

export default function ImportPage() {
  const api = useApi();
  const fileRef = useRef(null);
  const [kind, setKind] = useState("employees");
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [overwrite, setOverwrite] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const reset = () => {
    setPreview(null);
    setResult(null);
    setOverwrite(false);
    setError("");
    if (fileRef.current) fileRef.current.value = "";
  };

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    setError("");
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("file", file);
    try {
      const r = await api.post("/import/preview", fd);
      setPreview(r.data);
      setResult(null);
      setOverwrite(false);
    } catch (e) {
      setError(errMsg(e));
      if (fileRef.current) fileRef.current.value = "";
    } finally {
      setBusy(false);
    }
  };

  const commit = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/import/${preview.id}/commit`, { overwrite_existing: overwrite });
      setResult(r.data);
      toast.success("Import finished");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const sums = preview?.summary || {};
  const importable = ["departments", "employees"].reduce((n, k) => n + (sums[k]?.valid || 0) + (overwrite ? sums[k]?.existing || 0 : 0), 0);
  const existing = (sums.departments?.existing || 0) + (sums.employees?.existing || 0);
  const step = result ? 3 : preview ? 2 : 1;

  return (
    <div data-testid="import-page">
      <PageHeader title="Bulk import" subtitle="Import departments and employees from CSV or Excel. Nothing is written until you confirm.">
        <Button variant="outline" asChild data-testid="import-history-link"><Link to="/import/history">Import history</Link></Button>
      </PageHeader>
      <div className="mb-6 flex gap-2 font-mono text-xs">
        {["Upload", "Preview & validate", "Summary"].map((s, i) => (
          <span key={s} className={`rounded-full border px-3 py-1 ${step === i + 1 ? "border-indigo-500 bg-indigo-500/15 text-indigo-200" : "text-muted-foreground"}`}>{i + 1}. {s}</span>
        ))}
      </div>
      {step === 1 && (
        <Panel title="1. Choose what to import" testId="import-step-upload">
          <Tabs value={kind} onValueChange={setKind}>
            <TabsList className="h-auto flex-wrap">{KINDS.map(([k, l]) => <TabsTrigger key={k} value={k} data-testid={`import-kind-${k}`}>{l}</TabsTrigger>)}</TabsList>
          </Tabs>
          <p className="mt-3 text-sm text-muted-foreground">
            {kind === "departments" && "Columns: department_code, department_name, description."}
            {kind === "employees" && "Columns: employee_id, full_name, work_email, department_code or department_name, designation, manager (employee ID or email), working_schedule (e.g. Mon-Fri 09:00-18:00), role. Departments must exist already."}
            {kind === "combined" && "One .xlsx with a 'Departments' sheet and an 'Employees' sheet. Departments are imported first, then employees are mapped to them."}
          </p>
          <div className="mt-4"><Templates kind={kind} /></div>
          <label className="mt-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-10 text-center transition-colors hover:border-indigo-500/60 hover:bg-indigo-500/5" data-testid="import-dropzone">
            <FileUp className="h-8 w-8 text-indigo-300" />
            <span className="font-medium">{busy ? "Validating…" : "Click to choose a .csv or .xlsx file"}</span>
            <span className="text-xs text-muted-foreground">Max 5 MB, 5,000 rows</span>
            <input ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden" disabled={busy} onChange={(e) => upload(e.target.files[0])} data-testid="import-file-input" />
          </label>
          {error && <div className="mt-4 rounded-lg border border-red-500/40 bg-red-950/30 p-3 text-sm text-red-200" data-testid="import-file-error">{error}</div>}
        </Panel>
      )}
      {step === 2 && (
        <div className="space-y-6" data-testid="import-step-preview">
          <Panel title={`2. Preview - ${preview.file_name}`}>
            <div className="space-y-4">
              <Summary s={sums.departments} label="Departments" />
              <Summary s={sums.employees} label="Employees" />
            </div>
            {existing > 0 && (
              <label className="mt-5 flex items-start gap-3 rounded-lg border border-blue-500/40 bg-blue-950/30 p-3 text-sm">
                <Checkbox checked={overwrite} onCheckedChange={(v) => setOverwrite(!!v)} data-testid="overwrite-existing-checkbox" />
                <span>Update the {existing} existing record(s) with values from this file. Leave unchecked to skip them - existing records are never changed without this confirmation.</span>
              </label>
            )}
            <div className="mt-5 flex flex-wrap gap-2">
              <Button variant="outline" onClick={reset} data-testid="import-reupload-button"><RotateCcw className="mr-1 h-4 w-4" /> Upload corrected file</Button>
              <Button disabled={busy || importable === 0} onClick={() => (overwrite ? setConfirmOpen(true) : commit())} data-testid="import-confirm-button">
                {busy ? "Importing…" : `Import ${importable} record(s)`}
              </Button>
            </div>
          </Panel>
          <ImportResults departments={preview.departments} employees={preview.employees} />
        </div>
      )}
      {step === 3 && (
        <div className="space-y-6" data-testid="import-step-summary">
          <Panel title="3. Import complete">
            <div className="space-y-4">
              <Summary s={result.summary.departments} label="Departments" />
              <Summary s={result.summary.employees} label="Employees" />
            </div>
            <div className="mt-5 flex gap-2">
              <Button onClick={reset} data-testid="import-another-button">Import another file</Button>
              <Button variant="outline" asChild><Link to="/employees">View employees</Link></Button>
            </div>
          </Panel>
          <ImportResults departments={result.departments} employees={result.employees} showOutcome />
        </div>
      )}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent data-testid="overwrite-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Overwrite existing records?</AlertDialogTitle>
            <AlertDialogDescription>{existing} existing department/employee record(s) will be updated with the values in this file. This cannot be undone automatically.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="overwrite-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={commit} data-testid="overwrite-confirm">Yes, update them</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
