import { cn } from "@/lib/utils";

export function PageHeader({ title, subtitle, children, testId }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between rise" data-testid={testId}>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Panel({ title, action, children, className, testId }) {
  return (
    <section data-testid={testId} className={cn("rounded-xl border bg-card p-5 transition-colors duration-200 hover:border-slate-700 rise", className)}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-2">
          {title && <h3 className="text-base font-semibold tracking-tight">{title}</h3>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint, icon: Icon, tone = "text-indigo-300", testId, delay = 0 }) {
  return (
    <div data-testid={testId} style={{ animationDelay: `${delay}ms` }} className="rise rounded-xl border bg-card p-4 transition-colors duration-200 hover:border-slate-700">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
        {Icon && <Icon className={cn("h-4 w-4", tone)} />}
      </div>
      <div className="mt-2 font-heading text-2xl font-semibold tabular-nums sm:text-3xl">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

export function Empty({ children, testId }) {
  return <div data-testid={testId} className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">{children}</div>;
}
