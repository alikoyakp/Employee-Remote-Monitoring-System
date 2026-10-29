import { useEffect, useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty, PageHeader, Panel } from "@/components/Page";
import { ImportResults } from "@/components/ImportResults";
import { fmtDateTime, useApi } from "@/lib/api";

const fmtSum = (s) => (s ? `${s.created} created · ${s.updated} updated · ${s.skipped} skipped · ${s.duplicate} dup · ${s.failed} failed` : "—");
const STATUS_CLS = { completed: "text-emerald-300", preview: "text-amber-300", rejected: "text-red-300", processing: "text-blue-300" };

export default function ImportHistory() {
  const api = useApi();
  const [rows, setRows] = useState(null);
  const [detail, setDetail] = useState(null);
  useEffect(() => {
    api.get("/import/history").then((r) => setRows(r.data));
  }, [api]);
  const open = async (id) => setDetail((await api.get(`/import/${id}`)).data);
  return (
    <div data-testid="import-history-page">
      <PageHeader title="Import history" subtitle="Every upload, including rejected files and previews that were never confirmed." />
      <Panel>
        {rows && !rows.length && <Empty>No imports yet.</Empty>}
        {rows && rows.length > 0 && (
          <div className="overflow-x-auto scrollbar-thin">
            <Table data-testid="import-history-table">
              <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>File</TableHead><TableHead>Type</TableHead><TableHead>Administrator</TableHead><TableHead>Status</TableHead><TableHead>Departments</TableHead><TableHead>Employees</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id} className="cursor-pointer" onClick={() => open(r.id)} data-testid={`import-history-row-${r.id}`}>
                    <TableCell className="whitespace-nowrap text-xs">{fmtDateTime(r.created_at)}</TableCell>
                    <TableCell className="font-medium">{r.file_name}</TableCell>
                    <TableCell className="capitalize">{r.kind}</TableCell>
                    <TableCell>{r.admin_name}</TableCell>
                    <TableCell className={`font-mono text-xs capitalize ${STATUS_CLS[r.status] || ""}`}>{r.status === "preview" ? "not confirmed" : r.status}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.status === "rejected" ? r.error : fmtSum(r.summary?.departments)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.status === "rejected" ? "" : fmtSum(r.summary?.employees)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto" data-testid="import-detail-dialog">
          <DialogHeader><DialogTitle>{detail?.file_name}</DialogTitle></DialogHeader>
          {detail?.error && <p className="text-sm text-red-300">{detail.error}</p>}
          {detail?.results && <div className="space-y-4"><ImportResults departments={detail.results.departments} employees={detail.results.employees} showOutcome /></div>}
          {detail && !detail.results && !detail.error && <p className="text-sm text-muted-foreground">This preview was never confirmed, so nothing was imported.</p>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
