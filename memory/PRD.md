# WorkPulse – PRD

## Original problem statement
Build an Employee Tracking and Monitoring System — professional full-stack system for office and remote employees with a modern responsive dashboard.
1. Authentication & employee management: role-based login (Admin, Manager, Employee); employee profiles, departments, reporting managers, working schedules; login/logout time, session duration, daily hours; missed logouts and multiple sessions.
2. Bulk import of departments & employees (CSV + XLSX): templates, columns (department name/code, employee ID, full name, work email, department, designation, manager, working schedule), validation & duplicate checks (employee IDs, emails, dept codes), preview, row-numbered errors, re-upload, summary (successful/failed/skipped/duplicate), auto-map by dept code/name, departments-first or combined, import history (file, admin, date, results), never overwrite without explicit confirmation.
3. Activity monitoring: mouse/click/keyboard events during authorised hours, no keystrokes/passwords/content; active/idle with configurable threshold; breaks, offline, last interaction; clear "monitoring active" indicator.
4. Hourly screenshots (configurable interval) during authorised sessions, secure storage with employee/date/time/session, gallery only for authorised managers, audit logs, access control, configurable auto-deletion, desktop agent for full-desktop capture.
5. Dashboard & reports: totals, departments, logged-in, active/idle, breaks, attendance, hours; daily/weekly/monthly reports, activity summaries, department analytics, filters (employee, department, manager, date range), CSV & Excel export.
6. Stack requested: Next.js/React/TS + Node/PostgreSQL/Prisma (platform → React + FastAPI + MongoDB, user confirmed).
7. Security: HTTPS, secure auth, server-side access control, audit logs, retention policies, transparent monitoring notices; migrations, sample data, upload validation, error handling, automated tests, deployment instructions; identify desktop-agent features.

User choices: build on platform stack; email + password login; downloadable desktop agent + browser tracking; screenshot retention 30 days; admin enables/disables screenshots per user (default disabled).

## Architecture
React (CRA) + Tailwind/shadcn · FastAPI (`core`, `auth`, `validation`, `routes_org`, `importer`, `tracking`, `reports`, `seed`) · MongoDB · built-in email/password auth (bcrypt + JWT Bearer tokens, admin login links) · Emergent object storage for screenshots · platform cron (`/api/cron/maintenance`, every 15 min) · Python desktop agent (`backend/agent_dist/workpulse_agent.py`, X-Agent-Token).

## User personas
- Admin (HR/ops): manages org, imports, settings, sees everything.
- Manager: sees own direct reports' attendance/activity/screenshots.
- Employee: clocks in/out, breaks, sees own data, installs agent.

## Implemented (2026-10-29)
- Clerk auth; access only for registered employee emails or ADMIN_EMAIL (alikoyakp@gmail.com); role scoping server-side
- Departments CRUD, employees CRUD (role, manager, schedule, timezone, status), per-user screenshot toggle (default off)
- Bulk import wizard (CSV/XLSX, combined xlsx), templates, preview w/ row errors, overwrite confirmation, history incl. rejected files
- Clock in/out, breaks, browser heartbeat tracking (counts only), active/idle/offline status, monitoring banner, notice acknowledgement
- Desktop agent: token mgmt, config/heartbeat/screenshot API, interval + schedule + break enforcement
- Screenshot gallery (admin/manager scoped) with audit-logged views; retention cleanup (cron + manual)
- Dashboard (KPIs, live board, 7-day trend, departments), activity timeline, attendance sessions, reports daily/weekly/monthly + CSV/XLSX export, audit log viewer, settings
- Sample data seed; pytest suites (validation unit + API); README with deployment instructions

## Backlog
- P1: local-timezone day bucketing in reports; packaged agent installers (exe/dmg) with tray icon
- P1: shadcn date pickers, AlertDialog for department delete
- P2: email digests of daily attendance; per-department screenshot policies

## Next tasks
- User signs in with mishalmmofficial@gmail.com and imports real employees

## Changelog
- 2026-11-09: Al Arabia logo, renamed to ERM System, colour #6A5DA4, env templates; replaced Clerk with built-in login (ADMIN_EMAIL/ADMIN_PASSWORD seed, one-time login links, change password, per-email brute-force lock, Bearer tokens)
