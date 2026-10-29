# WorkPulse – Employee Tracking & Monitoring

Full-stack employee attendance, activity monitoring and reporting for office and remote teams.

> **Stack note:** the original brief asked for Next.js + PostgreSQL + Prisma. This platform runs
> **React (CRA) + FastAPI (Python) + MongoDB**, so the same features are implemented on that stack.
> The frontend is JavaScript (JSX), not TypeScript.

## Architecture
| Layer | Tech |
|---|---|
| Frontend | React 19, React Router, Tailwind, shadcn/ui, Recharts (`/app/frontend`) |
| Backend | FastAPI (`/app/backend`), all routes under `/api` |
| Database | MongoDB (collections: departments, employees, sessions, breaks, activity, screenshots, imports, audit_logs, settings) |
| Auth | Emergent-managed Clerk (email + password). Roles (admin / manager / employee) stored in MongoDB and enforced server-side |
| Screenshot storage | Emergent private object storage; images only served through an authorised, audit-logged backend endpoint |
| Background jobs | Platform cron `.emergent/crons.yml` → `POST /api/cron/maintenance` every 15 min (missed-logout auto-close, screenshot & activity retention) |
| Desktop agent | `backend/agent_dist/workpulse_agent.py` (download from the "Desktop agent" page) |

### Backend modules
- `core.py` – DB, role resolution (`current_member`, `require_role`, `visible_ids`), audit, storage helpers
- `validation.py` – pure CSV/XLSX parsing, import validation, schedule parsing (unit-tested)
- `routes_org.py` – me, departments, employees, settings, audit logs
- `importer.py` – templates, preview, commit, history
- `tracking.py` – clock in/out, breaks, heartbeats, agent API, screenshots, maintenance
- `reports.py` – dashboard, daily/weekly/monthly reports, CSV/XLSX export
- `seed.py` – idempotent sample data (4 departments, 12 example employees, ~4 working days of history)

## Access model
- Nobody can self-register into the app: a signed-in Clerk user only gets access if their **verified email** matches an
  employee record (created manually or by import), or is listed in `ADMIN_EMAIL` (first admin bootstrap).
- Admin: everything. Manager: themselves + direct reports (screenshots of direct reports only). Employee: own data only.
- Screenshots are **off by default per employee**; only admins can toggle them (Employees page).
- Every screenshot list/view, settings change, import, role/profile change and clock event is written to `audit_logs`.

## Features requiring the separately installed desktop agent
1. Full-desktop screenshots (browsers cannot capture the screen silently).
2. Mouse/click/key activity counts across all applications (the browser only sees activity inside the WorkPulse tab).
3. Tracking while the WorkPulse tab is closed.

Agent install: `pip install requests pynput mss pillow`, generate a token on the Desktop agent page, then
`python workpulse_agent.py --server https://<app-url> --token wpa_xxx --clock-in --clock-out-on-exit`.
The agent never records which keys are pressed – only counts. It only sends data while the employee is clocked in and not on a break,
and screenshots only when enabled for that employee **and** inside their working schedule.

## Monitoring rules
- Active vs idle: a minute is *active* if the last interaction is within the configurable idle threshold (default 5 min).
- Offline: no heartbeat for `offline_after_min` (default 5). Missed logout: open session with no heartbeat for
  `auto_close_after_min` (default 30) is closed at the last-seen time and flagged.
- Multiple devices (browser + agent) share one open session; multiple sessions per day are summed.
- Reports group days in UTC.

## Import
Templates (CSV/XLSX) from the Bulk import page. Columns:
- Departments: `department_code, department_name, description`
- Employees: `employee_id, full_name, work_email, department_code | department_name, designation, manager (employee_id or email), working_schedule (e.g. "Mon-Fri 09:00-18:00"), role`
- Combined: one .xlsx with `Departments` + `Employees` sheets (departments are created first).
Preview shows row-level status (valid / error / duplicate / exists). Existing records are only updated after an explicit
overwrite confirmation. Each upload (including rejected files) appears in Import history.

## Tests
```
cd backend && python -m pytest -q tests          # validation unit tests
python tests/clerk_test_users.py --tokens         # create dev test users and print API tokens
```

## Deployment
Use the platform **Deploy** button. Production gets HTTPS, a production Clerk instance and the cron schedule automatically.
Required backend env: `MONGO_URL`, `DB_NAME`, `CLERK_*` (managed), `ADMIN_EMAIL`, `WEBHOOK_CRON_SECRET`, `EMERGENT_LLM_KEY` (object storage).
After deploying, the first admin signs up on the live app with the `ADMIN_EMAIL` address.
