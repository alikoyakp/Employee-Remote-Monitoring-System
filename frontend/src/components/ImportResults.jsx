import { useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import { Panel } from "@/components/Page";
import { StatusPill } from "@/components/StatusPill";

function ResultTable({ title, rows, cols, showOutcome, testId }) {
  const [onlyIssues, setOnlyIssues] = useState(false);
  if (!rows) return null;
  const shown = onlyIssues ? rows.filter((r) => r.status !== "valid") : rows;
  return (
    <Panel
      title={`${title} (${rows.length})`}
      testId={testId}
      action={<label className="flex items-center gap-2 text-xs text-muted-foreground"><Switch checked={onlyIssues} onCheckedChange={setOnlyIssues} data-testid={`${testId}-issues-only`} /> Only problems</label>}
    >
      <div className="max-h-[420px] overflow-auto scrollbar-thin">
        <Table>
          <TableHeader><TableRow>
            <TableHead className="w-14">Row</TableHead><TableHead>Status</TableHead>
            {showOutcome && <TableHead>Outcome</TableHead>}
            {cols.map(([k, l]) => <TableHead key={k} className="whitespace-nowrap">{l}</TableHead>)}
            <TableHead>Details</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {shown.map((r) => (
              <TableRow key={`${r.row}-${r.data[cols[0][0]]}`} data-testid={`${testId}-row-${r.row}`} className={r.status === "error" ? "bg-red-950/20" : ""}>
                <TableCell className="font-mono text-xs">{r.row}</TableCell>
                <TableCell><StatusPill status={r.status} /></TableCell>
                {showOutcome && <TableCell className="font-mono text-xs capitalize">{r.outcome}</TableCell>}
                {cols.map(([k]) => <TableCell key={k} className="whitespace-nowrap text-xs">{r.data[k] || "—"}</TableCell>)}
                <TableCell className="min-w-[220px] text-xs text-red-200">{r.errors.join("; ")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Panel>
  );
}

export function ImportResults({ departments, employees, showOutcome }) {
  return (
    <>
      <ResultTable title="Departments" rows={departments} showOutcome={showOutcome} testId="dept-results"
        cols={[["department_code", "Code"], ["department_name", "Name"]]} />
      <ResultTable title="Employees" rows={employees} showOutcome={showOutcome} testId="emp-results"
        cols={[["employee_id", "ID"], ["full_name", "Name"], ["work_email", "Email"], ["department_code", "Dept code"], ["department_name", "Dept"], ["manager", "Manager"], ["working_schedule", "Schedule"]]} />
    </>
  );
}
