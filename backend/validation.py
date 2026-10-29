"""Pure (DB-free) parsing and validation for imports and work schedules."""
import csv
import io
import re
from openpyxl import Workbook, load_workbook

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")
CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,20}$")
EID_RE = re.compile(r"^[A-Za-z0-9_\-\.]{1,30}$")
ROLES = ["admin", "manager", "employee"]
DEFAULT_SCHEDULE = "Mon-Fri 09:00-18:00"
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000

DEPT_COLUMNS = ["department_code", "department_name", "description"]
DEPT_REQUIRED = ["department_code", "department_name"]
EMP_COLUMNS = ["employee_id", "full_name", "work_email", "department_code", "department_name",
               "designation", "manager", "working_schedule", "role"]
EMP_REQUIRED = ["employee_id", "full_name", "work_email"]

ALIASES = {
    "email": "work_email", "name": "full_name", "employee_name": "full_name",
    "department": "department_name", "dept_code": "department_code", "dept_name": "department_name",
    "schedule": "working_schedule", "work_schedule": "working_schedule",
    "manager_id": "manager", "manager_employee_id": "manager", "manager_email": "manager",
    "reporting_manager": "manager", "emp_id": "employee_id",
}


def parse_schedule(text):
    m = re.fullmatch(r"\s*([A-Za-z,\-\s]+?)\s+(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*", text or "")
    if not m:
        raise ValueError("Use a format like 'Mon-Fri 09:00-18:00'")
    days = set()
    for part in m.group(1).replace(" ", "").lower().split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            if a[:3] not in DAYS or b[:3] not in DAYS:
                raise ValueError(f"Unknown day range '{part}'")
            i, j = DAYS.index(a[:3]), DAYS.index(b[:3])
            k = i
            while True:
                days.add(k)
                if k == j:
                    break
                k = (k + 1) % 7
        else:
            if part[:3] not in DAYS:
                raise ValueError(f"Unknown day '{part}'")
            days.add(DAYS.index(part[:3]))
    h1, m1, h2, m2 = (int(m.group(i)) for i in range(2, 6))
    if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59:
        raise ValueError("Invalid time in schedule")
    start, end = h1 * 60 + m1, h2 * 60 + m2
    if not days or start == end:
        raise ValueError("Schedule needs at least one day and a non-empty time range")
    return days, start, end


def in_schedule(text, local_dt):
    try:
        days, start, end = parse_schedule(text or DEFAULT_SCHEDULE)
    except ValueError:
        return True
    wd, mins = local_dt.weekday(), local_dt.hour * 60 + local_dt.minute
    if start < end:
        return wd in days and start <= mins < end
    return (wd in days and mins >= start) or (((wd - 1) % 7) in days and mins < end)


def normalize_header(h):
    key = re.sub(r"[\s\-]+", "_", str(h or "").strip().lower())
    return ALIASES.get(key, key)


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _rows_from_matrix(matrix):
    if not matrix:
        return [], []
    headers = [normalize_header(h) for h in matrix[0]]
    rows = []
    for idx, raw in enumerate(matrix[1:], start=2):
        values = [_cell(v) for v in raw]
        if not any(values):
            continue
        rows.append({"_row": idx, **{h: (values[i] if i < len(values) else "") for i, h in enumerate(headers) if h}})
    return [h for h in headers if h], rows


def read_table(filename, content):
    """Return {sheet_name_lower: (headers, rows)}. CSV yields a single '_csv' sheet."""
    name = (filename or "").lower()
    if len(content) == 0:
        raise ValueError("The file is empty")
    if len(content) > MAX_BYTES:
        raise ValueError("File is larger than 5 MB")
    if name.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("CSV must be UTF-8 encoded")
        matrix = list(csv.reader(io.StringIO(text)))
        return {"_csv": _rows_from_matrix(matrix)}
    if name.endswith(".xlsx"):
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:
            raise ValueError("Could not read the Excel file. Make sure it is a valid .xlsx")
        out = {}
        for ws in wb.worksheets:
            out[ws.title.strip().lower()] = _rows_from_matrix([list(r) for r in ws.iter_rows(values_only=True)])
        return out
    raise ValueError("Only .csv and .xlsx files are supported")


def pick_sheets(tables, kind):
    """Map parsed sheets to (dept_table, emp_table) for the chosen import kind."""
    def find(*names):
        for n in names:
            if n in tables:
                return tables[n]
        return None
    if "_csv" in tables:
        if kind == "combined":
            raise ValueError("Combined imports need an .xlsx file with 'Departments' and 'Employees' sheets")
        return (tables["_csv"], None) if kind == "departments" else (None, tables["_csv"])
    first = next(iter(tables.values()), ([], []))
    if kind == "departments":
        return find("departments") or first, None
    if kind == "employees":
        return None, find("employees") or first
    d, e = find("departments"), find("employees")
    if d is None or e is None:
        raise ValueError("Combined .xlsx must contain sheets named 'Departments' and 'Employees'")
    return d, e


def check_headers(table, required, label):
    headers, rows = table
    missing = [c for c in required if c not in headers]
    if missing:
        raise ValueError(f"{label}: missing required column(s): {', '.join(missing)}")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"{label}: more than {MAX_ROWS} rows")
    if not rows:
        raise ValueError(f"{label}: no data rows found")


def validate_departments(rows, existing_codes, existing_names):
    """existing_codes/names: lowercase code/name -> existing department id."""
    seen, results = set(), []
    for r in rows:
        data = {c: r.get(c, "") for c in DEPT_COLUMNS}
        errors, status = [], "valid"
        code, name = data["department_code"], data["department_name"]
        if not code:
            errors.append("department_code is required")
        elif not CODE_RE.match(code):
            errors.append("department_code may only contain letters, numbers, - and _ (max 20)")
        if not name:
            errors.append("department_name is required")
        elif len(name) > 100:
            errors.append("department_name is longer than 100 characters")
        if errors:
            status = "error"
        elif code.lower() in seen:
            status, errors = "duplicate", [f"department_code '{code}' appears earlier in this file"]
        elif code.lower() in existing_codes:
            status, errors = "existing", [f"Department '{code}' already exists"]
        elif name.lower() in existing_names:
            status, errors = "error", [f"Another department is already named '{name}'"]
        if code:
            seen.add(code.lower())
        results.append({"row": r["_row"], "data": data, "status": status, "errors": errors})
    return results


def validate_employees(rows, dept_codes, dept_names, existing_eids, existing_emails, existing_manager_keys):
    """dept_codes/dept_names: lowercase -> dept ref. existing_eids/emails: lowercase -> employee doc id.
    existing_manager_keys: lowercase employee_id/email of employees already in the DB."""
    file_keys = set()
    for r in rows:
        if r.get("employee_id"):
            file_keys.add(r["employee_id"].lower())
        if r.get("work_email"):
            file_keys.add(r["work_email"].lower())
    seen_eids, seen_emails, results = set(), set(), []
    for r in rows:
        data = {c: r.get(c, "") for c in EMP_COLUMNS}
        data["work_email"] = data["work_email"].lower()
        errors = []
        eid, email = data["employee_id"], data["work_email"]
        if not eid:
            errors.append("employee_id is required")
        elif not EID_RE.match(eid):
            errors.append("employee_id may only contain letters, numbers, . - _ (max 30)")
        if not data["full_name"]:
            errors.append("full_name is required")
        if not email:
            errors.append("work_email is required")
        elif not EMAIL_RE.match(email):
            errors.append(f"work_email '{email}' is not a valid email address")
        dc, dn = data["department_code"].lower(), data["department_name"].lower()
        if not dc and not dn:
            errors.append("department_code or department_name is required")
        elif dc and dc not in dept_codes:
            errors.append(f"Department code '{data['department_code']}' not found")
        elif not dc and dn not in dept_names:
            errors.append(f"Department '{data['department_name']}' not found")
        mgr = data["manager"].lower()
        if mgr:
            if mgr in (eid.lower(), email):
                errors.append("An employee cannot be their own manager")
            elif mgr not in file_keys and mgr not in existing_manager_keys:
                errors.append(f"Manager '{data['manager']}' not found (use the manager's employee_id or work email)")
        sched = data["working_schedule"] or DEFAULT_SCHEDULE
        try:
            parse_schedule(sched)
        except ValueError as e:
            errors.append(f"working_schedule: {e}")
        data["working_schedule"] = sched
        if data["role"] and data["role"].lower() not in ROLES:
            errors.append("role must be admin, manager or employee")
        data["role"] = data["role"].lower()
        status = "error" if errors else "valid"
        if status == "valid":
            if eid.lower() in seen_eids:
                status, errors = "duplicate", [f"employee_id '{eid}' appears earlier in this file"]
            elif email in seen_emails:
                status, errors = "duplicate", [f"work_email '{email}' appears earlier in this file"]
            elif eid.lower() in existing_eids:
                owner = existing_emails.get(email)
                if owner and owner != existing_eids[eid.lower()]:
                    status, errors = "error", [f"work_email '{email}' belongs to a different existing employee"]
                else:
                    status, errors = "existing", [f"Employee '{eid}' already exists (will only be updated if you confirm overwrite)"]
            elif email in existing_emails:
                status, errors = "error", [f"work_email '{email}' is already used by another employee"]
        if eid:
            seen_eids.add(eid.lower())
        if email:
            seen_emails.add(email)
        results.append({"row": r["_row"], "data": data, "status": status, "errors": errors})
    return results


def summarize(results):
    out = {"total": len(results), "valid": 0, "error": 0, "duplicate": 0, "existing": 0}
    for r in results:
        out[r["status"]] += 1
    return out


DEPT_SAMPLE = ["ENG", "Engineering", "Product engineering team"]
EMP_SAMPLE = ["EMP100", "Jane Doe", "jane.doe@yourcompany.com", "ENG", "Engineering",
              "Software Engineer", "EMP001", "Mon-Fri 09:00-18:00", "employee"]


def build_template(kind, fmt):
    if fmt == "csv":
        if kind == "combined":
            raise ValueError("Combined template is only available as .xlsx")
        buf = io.StringIO()
        w = csv.writer(buf)
        cols, sample = (DEPT_COLUMNS, DEPT_SAMPLE) if kind == "departments" else (EMP_COLUMNS, EMP_SAMPLE)
        w.writerow(cols)
        w.writerow(sample)
        return buf.getvalue().encode("utf-8")
    wb = Workbook()
    ws = wb.active
    sheets = []
    if kind in ("departments", "combined"):
        sheets.append(("Departments", DEPT_COLUMNS, DEPT_SAMPLE))
    if kind in ("employees", "combined"):
        sheets.append(("Employees", EMP_COLUMNS, EMP_SAMPLE))
    for i, (title, cols, sample) in enumerate(sheets):
        sheet = ws if i == 0 else wb.create_sheet()
        sheet.title = title
        sheet.append(cols)
        sheet.append(sample)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
