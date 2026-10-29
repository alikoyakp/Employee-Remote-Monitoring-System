import pytest
from datetime import datetime

from validation import (build_template, check_headers, in_schedule, parse_schedule, pick_sheets, read_table,
                        validate_departments, validate_employees)


def test_parse_schedule_range_and_list():
    days, start, end = parse_schedule("Mon-Fri 09:00-18:00")
    assert days == {0, 1, 2, 3, 4} and start == 540 and end == 1080
    assert parse_schedule("Mon,Wed,Fri 10:00-16:00")[0] == {0, 2, 4}
    with pytest.raises(ValueError):
        parse_schedule("weekdays 9-5")


def test_in_schedule_overnight():
    assert in_schedule("Mon-Fri 22:00-06:00", datetime(2026, 1, 6, 2, 0))  # Tue 02:00 belongs to Mon shift
    assert not in_schedule("Mon-Fri 09:00-18:00", datetime(2026, 1, 10, 10, 0))  # Saturday


def test_read_csv_and_headers():
    content = b"Department Code,Department Name\nENG,Engineering\n,\nMKT,Marketing\n"
    tables = read_table("d.csv", content)
    dept, emp = pick_sheets(tables, "departments")
    check_headers(dept, ["department_code", "department_name"], "Departments")
    assert [r["_row"] for r in dept[1]] == [2, 4]
    with pytest.raises(ValueError):
        read_table("d.txt", b"x")


def test_validate_departments_duplicates_and_existing():
    rows = [{"_row": 2, "department_code": "ENG", "department_name": "Engineering"},
            {"_row": 3, "department_code": "eng", "department_name": "Eng 2"},
            {"_row": 4, "department_code": "OPS", "department_name": "Ops"},
            {"_row": 5, "department_code": "", "department_name": "X"}]
    res = validate_departments(rows, {"ops": "id1"}, {"ops": "id1"})
    assert [r["status"] for r in res] == ["valid", "duplicate", "existing", "error"]


def test_validate_employees():
    codes, names = {"eng": "d1"}, {"engineering": "d1"}
    rows = [
        {"_row": 2, "employee_id": "E1", "full_name": "A", "work_email": "a@x.com", "department_code": "ENG", "manager": "E2"},
        {"_row": 3, "employee_id": "E2", "full_name": "B", "work_email": "b@x.com", "department_name": "Engineering"},
        {"_row": 4, "employee_id": "E2", "full_name": "C", "work_email": "c@x.com", "department_code": "ENG"},
        {"_row": 5, "employee_id": "E4", "full_name": "D", "work_email": "bad", "department_code": "NOPE"},
        {"_row": 6, "employee_id": "E5", "full_name": "E", "work_email": "old@x.com", "department_code": "ENG"},
        {"_row": 7, "employee_id": "E6", "full_name": "F", "work_email": "f@x.com", "department_code": "ENG", "working_schedule": "bad"},
    ]
    res = validate_employees(rows, codes, names, {"e5": "id5"}, {"old@x.com": "id5"}, {"e5", "old@x.com"})
    assert [r["status"] for r in res] == ["valid", "valid", "duplicate", "error", "existing", "error"]
    assert len(res[3]["errors"]) == 2


def test_templates():
    assert build_template("employees", "csv").startswith(b"employee_id,full_name,work_email")
    tables = read_table("t.xlsx", build_template("combined", "xlsx"))
    d, e = pick_sheets(tables, "combined")
    assert d[1][0]["department_code"] == "ENG" and e[1][0]["employee_id"] == "EMP100"
    with pytest.raises(ValueError):
        build_template("combined", "csv")
