import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Panel } from "@/components/Page";
import { StatusPill } from "@/components/StatusPill";
import { fmtDateTime, sinceText, useApi } from "@/lib/api";

function reason(r) {
  if (!r.has_agent_token) return "Desktop agent not set up (no agent token)";
  if (!r.agent_last_used_at || Date.now() - new Date(r.agent_last_used_at).getTime() > 10 * 60000) return "Desktop agent not running";
  if (r.status === "signed_out") return "Not clocked in";
  if (r.status === "on_break") return "On break";
  if (!r.within_schedule) return `Outside schedule (${r.working_schedule}, ${r.timezone})`;
  return "Capturing";
}

export function CaptureStatus() {
  const api = useApi();
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/admin/capture-status").then((r) => setData(r.data)).catch(() => {});
  }, [api]);
  if (!data) return null;
  const s = data.storage;
  return (
    <Panel title="Capture status" className="mb-6" testId="capture-status-panel">
      <div className={`mb-4 flex items-start gap-2 text-sm ${s.ok ? "text-emerald-300" : "text-red-300"}`} data-testid="storage-status">
        {s.ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0" />}
        <span>Screenshot storage ({s.backend === "local" ? "server disk" : "Emergent cloud"}): {s.ok ? "working" : `not working - ${s.error}`}</span>
      </div>
      {!data.employees.length ? (
        <p className="text-sm text-muted-foreground">No employee has screenshots enabled. Turn them on per person on the Employees page.</p>
      ) : (
        <div className="overflow-x-auto scrollbar-thin">
          <Table>
            <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Status</TableHead><TableHead>Agent last seen</TableHead><TableHead>Last screenshot</TableHead><TableHead>Why / why not</TableHead></TableRow></TableHeader>
            <TableBody>
              {data.employees.map((r) => (
                <TableRow key={r.id} data-testid={`capture-row-${r.employee_id}`}>
                  <TableCell className="whitespace-nowrap">{r.full_name}</TableCell>
                  <TableCell><StatusPill status={r.status} /></TableCell>
                  <TableCell className="whitespace-nowrap text-xs">{sinceText(r.agent_last_used_at)}</TableCell>
                  <TableCell className="whitespace-nowrap text-xs">{fmtDateTime(r.last_screenshot_at)}</TableCell>
                  <TableCell className="text-xs text-amber-200" data-testid={`capture-reason-${r.employee_id}`}>{reason(r)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </Panel>
  );
}
