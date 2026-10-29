import { useEffect, useState } from "react";
import { ImageOff, ShieldAlert } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Empty, PageHeader, Panel } from "@/components/Page";
import { PickSelect, empOptions } from "@/components/PickSelect";
import { useLookups, useMe } from "@/context/MeContext";
import { fmtDateTime, isoDay, useApi } from "@/lib/api";

function useShotUrl(id) {
  const api = useApi();
  const [url, setUrl] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let href;
    let alive = true;
    api.get(`/screenshots/${id}/image`, { responseType: "blob" })
      .then((r) => { href = URL.createObjectURL(r.data); if (alive) setUrl(href); })
      .catch(() => alive && setFailed(true));
    return () => { alive = false; if (href) URL.revokeObjectURL(href); };
  }, [api, id]);
  return { url, failed };
}

function Shot({ id, className }) {
  const { url, failed } = useShotUrl(id);
  if (failed) return <div className={`grid place-items-center bg-background ${className}`}><ImageOff className="h-5 w-5 text-muted-foreground" /></div>;
  if (!url) return <div className={`animate-pulse bg-secondary ${className}`} />;
  return <img src={url} alt="screenshot" className={`object-cover ${className}`} />;
}

export default function Screenshots() {
  const api = useApi();
  const { me } = useMe();
  const { employees, departments } = useLookups();
  const [emp, setEmp] = useState("");
  const [date, setDate] = useState(isoDay());
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(null);
  const [retention, setRetention] = useState(30);
  useEffect(() => {
    api.get("/settings").then((r) => setRetention(r.data.screenshot_retention_days));
  }, [api]);
  useEffect(() => {
    api.get("/screenshots", { params: { employee_id: emp || undefined, date: date || undefined } }).then((r) => setRows(r.data)).catch(() => setRows([]));
  }, [api, emp, date]);
  const visibleEmps = employees.filter((e) => e.id !== me.id || me.role === "admin");
  void departments;
  return (
    <div data-testid="screenshots-page">
      <PageHeader title="Screenshots" subtitle={me.role === "admin" ? "All employees with screenshots enabled." : "Your direct reports only."} />
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-950/20 px-4 py-3 text-sm text-amber-200" data-testid="screenshot-retention-banner">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
        <span>Restricted area. Every list and image view is recorded in the audit log. Screenshots are deleted automatically after {retention} days and are only captured for employees an admin has enabled.</span>
      </div>
      <Panel>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          <PickSelect value={emp} onChange={setEmp} options={empOptions(visibleEmps)} allLabel="All employees" testId="screenshots-employee-filter" className="w-full sm:w-72" />
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="sm:w-44" data-testid="screenshots-date-filter" />
        </div>
        {rows && !rows.length && <Empty testId="screenshots-empty">No screenshots for this filter. Screenshots come from the desktop agent for employees with screenshots enabled.</Empty>}
        {rows && rows.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" data-testid="screenshots-grid">
            {rows.map((s) => (
              <button key={s.id} onClick={() => setOpen(s)} className="group overflow-hidden rounded-xl border bg-background text-left transition-colors hover:border-indigo-500/60" data-testid={`screenshot-card-${s.id}`}>
                <Shot id={s.id} className="aspect-video w-full" />
                <div className="p-3 text-xs">
                  <div className="font-medium text-foreground">{s.employee_name} <span className="font-mono text-muted-foreground">{s.employee_code}</span></div>
                  <div className="text-muted-foreground">{fmtDateTime(s.taken_at)}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>
      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent className="max-w-5xl" data-testid="screenshot-lightbox">
          <DialogHeader><DialogTitle>{open?.employee_name} · {fmtDateTime(open?.taken_at)}</DialogTitle></DialogHeader>
          {open && <Shot id={open.id} className="w-full rounded-lg object-contain" />}
          <p className="font-mono text-[11px] text-muted-foreground">Session {open?.session_id}</p>
        </DialogContent>
      </Dialog>
    </div>
  );
}
