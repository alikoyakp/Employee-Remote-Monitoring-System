import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function PickSelect({ value, onChange, options, allLabel, placeholder, testId, className = "w-full sm:w-48" }) {
  return (
    <Select value={value || "all"} onValueChange={(v) => onChange(v === "all" ? "" : v)}>
      <SelectTrigger data-testid={testId} className={className}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {allLabel && <SelectItem value="all">{allLabel}</SelectItem>}
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export const empOptions = (employees) => employees.map((e) => ({ value: e.id, label: `${e.full_name} (${e.employee_id})` }));
export const deptOptions = (departments) => departments.map((d) => ({ value: d.id, label: d.name }));
export const mgrOptions = (employees) => employees.filter((e) => e.role !== "employee").map((e) => ({ value: e.id, label: e.full_name }));
