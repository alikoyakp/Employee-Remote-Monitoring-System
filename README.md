# ERM System – Employee Tracking & Monitoring

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
| Auth | Built-in email + password (bcrypt hashes, JWT in httpOnly cookies, brute-force lockout). Roles (admin / manager / employee) stored in MongoDB and enforced server-side |
| Screenshot storage | Emergent private object storage; images only served through an authorised, audit-logged backend endpoint |
| Background jobs | Platform cron `.emergent/crons.yml` → `POST /api/cron/maintenance` every 15 min (missed-logout auto-close, screenshot & activity retention) |
| Desktop agent | `backend/agent_dist/erm_agent.py` (download from the "Desktop agent" page) |

### Backend modules
- `core.py` – DB, role resolution (`current_member`, `require_role`, `visible_ids`), audit, storage helpers
- `validation.py` – pure CSV/XLSX parsing, import validation, schedule parsing (unit-tested)
- `routes_org.py` – me, departments, employees, settings, audit logs
- `importer.py` – templates, preview, commit, history
- `tracking.py` – clock in/out, breaks, heartbeats, agent API, screenshots, maintenance
- `reports.py` – dashboard, daily/weekly/monthly reports, CSV/XLSX export
- `seed.py` – idempotent sample data (4 departments, 12 example employees, ~4 working days of history)

## Access model
- No open sign-up. `ADMIN_EMAIL` accounts are created on startup with `ADMIN_PASSWORD` (only if they have no password yet).
  Everyone else gets a one-time login link (72 h) from an admin on the Employees page (key icon) to set their password;
  the same link resets a forgotten password.
- Admin: everything. Manager: themselves + direct reports (screenshots of direct reports only). Employee: own data only.
- Screenshots are **off by default per employee**; only admins can toggle them (Employees page).
- Every screenshot list/view, settings change, import, role/profile change and clock event is written to `audit_logs`.

## Features requiring the separately installed desktop agent
1. Full-desktop screenshots (browsers cannot capture the screen silently).
2. Mouse/click/key activity counts across all applications (the browser only sees activity inside the ERM System tab).
3. Tracking while the ERM System tab is closed.

Agent install: `pip install requests pynput mss pillow`, generate a token on the Desktop agent page, then
`python erm_agent.py --server https://<app-url> --token wpa_xxx --clock-in --clock-out-on-exit`.
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
python tests/test_users.py --tokens               # ensure TEST_ accounts and print API tokens
```

## Deployment
Environment templates: `backend/env.example` and `frontend/env.example` (copy to `.env` and fill in real values).

| Variable | Where | Purpose |
|---|---|---|
| MONGO_URL / DB_NAME | backend | MongoDB connection and database name |
| CORS_ORIGINS | backend | Comma-separated allowed frontend origins |
| JWT_SECRET | backend | Long random string used to sign login sessions |
| ADMIN_EMAIL / ADMIN_PASSWORD | backend | First admin account(s) (comma-separated emails) and their initial password |
| WEBHOOK_CRON_SECRET | backend | Bearer secret for POST /api/cron/maintenance (call it every 15 min) |
| EMERGENT_LLM_KEY | backend | Unlocks Emergent object storage for screenshots |
| REACT_APP_BACKEND_URL | frontend | Public URL of the backend (routes are under /api) |

Use the platform **Deploy** button.

### Self-hosting notes
- Set `CORS_ORIGINS` to the exact frontend address (e.g. `CORS_ORIGINS=https://erms.example.com`), never `*` in production: `*` turns off the cross-site request check. Both sites must use HTTPS (session cookies are Secure).
- Serve a production build (`yarn build`), not the development server (`yarn start`).
After starting, sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`, then change the password from the user menu.
