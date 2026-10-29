import { useEffect, useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { PageHeader, Panel } from "@/components/Page";
import { PickSelect } from "@/components/PickSelect";
import { RoleBadge } from "@/components/StatusPill";
import { fmtDateTime, useApi } from "@/lib/api";

const ACTIONS = ["auth", "session", "employee", "department", "import", "screenshot", "screenshots", "settings", "agent", "notice", "maintenance"];
const PAGE = 50;

export default function AuditLogs() {
  const api = useApi();
  const [action, setAction] = useState("");
  const [skip, setSkip] = useState(0);
  const [data, setData] = useState({ total: 0, items: [] });
  useEffect(() => {
    api.get("/audit-logs", { params: { action: action || undefined, skip, limit: PAGE } }).then((r) => setData(r.data));
  }, [api, action, skip]);
  return (
    <div data-testid="audit-logs-page">
      <PageHeader title="Audit logs" subtitle="Who did what, and when - including every screenshot view.">
        <PickSelect value={action} onChange={(v) => { setAction(v); setSkip(0); }} options={ACTIONS.map((a) => ({ value: `${a}.`, label: a }))} allLabel="All actions" testId="audit-action-filter" />
      </PageHeader>
      <Panel>
        <div className="overflow-x-auto scrollbar-thin">
          <Table data-testid="audit-table">
            <TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Actor</TableHead><TableHead>Action</TableHead><TableHead className="hidden md:table-cell">Target</TableHead><TableHead className="hidden lg:table-cell">Details</TableHead></TableRow></TableHeader>
            <TableBody>
              {data.items.map((a) => (
                <TableRow key={a.id}>
                  <TableCell className="whitespace-nowrap text-xs">{fmtDateTime(a.ts)}</TableCell>
                  <TableCell className="whitespace-nowrap">{a.actor_name} <RoleBadge role={a.actor_role} /></TableCell>
                  <TableCell className="font-mono text-xs text-indigo-200">{a.action}</TableCell>
                  <TableCell className="hidden font-mono text-[11px] text-muted-foreground md:table-cell">{a.target_type} {a.target_id?.slice(0, 8)}</TableCell>
                  <TableCell className="hidden max-w-md truncate font-mono text-[11px] text-muted-foreground lg:table-cell">{JSON.stringify(a.details)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
          <span data-testid="audit-total">{data.total} entries</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE))} data-testid="audit-prev">Previous</Button>
            <Button size="sm" variant="outline" disabled={skip + PAGE >= data.total} onClick={() => setSkip(skip + PAGE)} data-testid="audit-next">Next</Button>
          </div>
        </div>
      </Panel>
    </div>
  );
}
