# QA Bug Report — PH Payroll Calculator

## BUG-003 — Calculate Payroll returns HTTP 200 for a non-existent employee

Severity: Medium

Endpoint: `POST /api/calculate-payroll/`

### Steps to Reproduce

1. Send a POST request to `/api/calculate-payroll/`.
2. Use an employee ID that does not exist, such as `99999`.
3. Provide a valid payroll period.

### Request

```json id="gtc27g"
{
  "employee_id": 99999,
  "period_month": 9,
  "period_year": 2026
}
```

### Expected Result

The API should return HTTP 404 Not Found because the requested employee does not exist.

### Actual Result

The API returns HTTP 200 OK with:

```json id="qxwxkp"
{
  "error": "Employee with id=99999 does not exist."
}
```

### Evidence

The automated test `test_calculate_payroll_missing_employee_should_return_404` also fails because the API returns HTTP 200 instead of the expected HTTP 404.

---

## BUG-004 — Negative override salary is accepted and persisted

Severity: High

Endpoint: `POST /api/calculate-payroll/`

### Steps to Reproduce

1. Send a POST request to `/api/calculate-payroll/`.
2. Use a valid employee ID.
3. Provide a negative value for `override_salary`.

### Request

```json id="69lvxx"
{
  "employee_id": 1,
  "period_month": 10,
  "period_year": 2026,
  "override_salary": -1000.0
}
```

### Expected Result

The API should reject a negative salary with HTTP 400 Bad Request and should not create or update a payroll record using the invalid amount.

### Actual Result

The API returns HTTP 201 Created and accepts the negative salary.

The response includes:

```json id="q16v7z"
{
  "basic_salary": "-1000.00",
  "total_deductions": "0.00",
  "net_pay": "-1000.00"
}
```

The invalid payroll record is also persisted and appears in payroll history.

### Evidence

The automated test `test_negative_salary_should_be_rejected` fails because the API returns HTTP 201 instead of HTTP 400.

---

## BUG-005 — Invalid payroll history year causes HTTP 500 Internal Server Error

Severity: Medium

Endpoint: `GET /api/payroll-history/`

### Steps to Reproduce

1. Send a GET request to `/api/payroll-history/`.
2. Provide a non-numeric value for the `year` query parameter.

### Request

```text id="kfx47i"
GET /api/payroll-history/?year=abc
```

### Expected Result

The API should validate the query parameter and return a controlled HTTP 400 Bad Request response indicating that the year must be numeric.

### Actual Result

The API returns HTTP 500 Internal Server Error and exposes a Django debug error page.

### Evidence

The request with `year=abc` produced HTTP status 500 instead of a controlled client-error response.

---

# API and Boundary Testing Coverage

The following endpoints, validations, and boundary conditions were tested:

- GET `/api/employees/`
- POST `/api/employees/`
- GET `/api/employees/{id}/`
- POST `/api/calculate-payroll/`
- GET `/api/payroll-history/`
- GET `/api/payroll-history/?employee_id={id}`
- GET `/api/payroll-history/?year={year}`
- GET `/api/tax-brackets/`
- Missing required request fields
- Invalid salary format
- Invalid decimal precision
- Payroll month boundaries (0, 13)
- Payroll year boundaries (1999, 2101)
- SSS salary ceiling
- PhilHealth salary limits
- TRAIN tax boundary values

## Automated Test Results

The backend test suite contains 28 tests.

- 26 tests passed
- 2 tests failed

The two failures correspond to the confirmed defects documented above:

- BUG-003 — Incorrect HTTP status for non-existent employee
- BUG-004 — Negative salary accepted

These failures were intentionally retained as evidence of the application defects and were not caused by modifying the application logic.
