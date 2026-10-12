# ASSESSMENT_NOTES

App name: AlphaCapMatch (Django app `reconciliation`).

## 1. Setup from a fresh clone

Prerequisites: Python 3.12+, a local PostgreSQL 14+ server, Node 18+.
The commands below are Windows PowerShell; on macOS/Linux use `cp`
instead of `copy` and `export` instead of `$env:`.

```powershell
# 1. Create the database (defaults: user postgres, host localhost, port 5432)
psql -U postgres -c "CREATE DATABASE recon;"
(If it says `database "recon" already exists`, that is fine — continue.)

# 1b. Point Django at Postgres (every new shell needs this).
# PowerShell: $env:POSTGRES_PASSWORD="your-password"
# macOS/Linux: export POSTGRES_PASSWORD="your-password"
# (See .env.example for all variables; only set the ones that differ.)

# 2. Backend
pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py seed_demo     # safe to run twice; creates northwind + bluebird
python manage.py runserver     # API on http://localhost:8000

# 3. Frontend (new shell)
cd frontend
npm install
npm run dev                    # page on http://localhost:5173
```

Settings read plain environment variables with local-first defaults
(`POSTGRES_DB=recon`, `POSTGRES_USER=postgres`, empty password,
`localhost:5432`). `.env.example` lists every variable: only set them
if your Postgres differs, e.g. `$env:POSTGRES_PASSWORD="secret"`.
No `.env` loader is required. The frontend talks to
`http://localhost:8000` unless `VITE_API_URL` is set.

## 2. Test command (single command, backend dir)

```powershell
cd backend
python -m pytest apps/reconciliation/tests/ -q
```

72 tests, all passing: CSV validation, matcher unit tests, the spec's
8 required cases, reject/ignore behaviour, a two-thread concurrent
approval test, a full sample-CSV import checked row by row, `assertNumQueries`
guards on list endpoints, audit log tracking, dry-run preview, un-ignore,
CSV export, rule tags, data health checks, and the Airtable bonus sync tests.

## 3. Data model

| Table | Key fields |
|---|---|
| `Organization` | `slug` unique (carried by `X-Organization`), `name` |
| `Investor` | `organization` FK, `name`; unique `(organization, name)` |
| `CapitalCall` | `organization` FK, `name`, `call_date`, `due_date`; unique `(organization, name)` |
| `LineItem` | `organization`/`investor`/`capital_call` FKs, `reference` (CC-1001…), `amount_called`, `amount_funded`, `status` (open / partially_funded / funded); unique `(organization, reference)`; `CheckConstraint 0 <= amount_funded <= amount_called`; money is `Decimal(14,2)` everywhere |
| `BankTransaction` | `organization` FK, `date`, `description`, `bank_reference`, `amount`, `type` (credit/debit), `status` (suggested / needs_review / reconciled / ignored), `reason`, `airtable_record_id`, `airtable_sync_status` (not_synced / synced / sync_failed); unique `(organization, bank_reference)`; `CheckConstraint amount != 0` |
| `Match` | `transaction` FK, `line_item` FK, `status` (proposed / approved / rejected), `reason`, `rule` (reference / name_amount) |
| `ActivityLog` | `organization` FK, `transaction` FK, `match` FK (nullable), `action` (imported / suggested / needs_review / approved / rejected / ignored / unignored), `message`, `created_at` |

Seed data (`seed_demo`): northwind (Northwind Ventures) has CALL-N1
(call 2026-03-25, due 2026-04-10) with CC-1001 Haller Capital LLC
27,500.00, CC-1002 Rahul Shah Trust 25,000.00, CC-1003 Patel Family Trust
12,500.00, CC-1004 Meridian Partners LP 15,000.00, CC-1005 Oakridge
Holdings LLC 15,000.00, plus CALL-N2 (call 2026-04-01, due 2026-04-20)
with CC-1006 Oakridge Holdings LLC 15,000.00. Bluebird (Bluebird
Capital) has CALL-B1 (call 2026-04-01, due 2026-04-15) with CC-2001
Cedar Grove Fund LP 40,000.00.

## 4. API endpoints

Every request needs `X-Organization: <slug>` (missing → 400
`missing_organization`, unknown → 404 `unknown_organization`).
Errors always look like `{"error": {"code": "...", "message": "..."}}`.
Single-object reads filter by organization, so cross-org access is 404.

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/api/imports/` (multipart `file`) | 201 `{imported, duplicates, errors: [{line, message}], by_status}` | 400 missing column / no file |
| POST | `/api/imports/preview/` (multipart `file`) | 200 `{would_import, duplicates, errors, by_status}` | 400 missing column / no file |
| GET | `/api/transactions/` (newest first, matches + reasons) | 200 list | 400/404 org |
| GET | `/api/transactions/export/?status=...` (streamed CSV) | 200 `text/csv` attachment | 400 invalid status |
| POST | `/api/transactions/{id}/ignore/` | 200 transaction | 404, 409 already reconciled/ignored |
| POST | `/api/transactions/{id}/unignore/` | 200 transaction | 404, 409 not ignored or debit |
| GET | `/api/transactions/{id}/history/` | 200 list of activity log entries | 404 tx |
| POST | `/api/matches/{id}/approve/` | 200 `{transaction, match, line_item}` | 404, 409 stale/insufficient funds |
| POST | `/api/matches/{id}/reject/` | 200 `{id, status, transaction, transaction_status}` | 404, 409 not proposed |
| GET | `/api/line-items/` (called, funded, remaining, status) | 200 list | 400/404 org |
| GET | `/api/health/` | 200 `{status: "ok", errors: []}` | 503 on data inconsistency |

Sample flow: upload `sample_bank_statement.csv` with
`X-Organization: northwind`, then approve suggestion ids from
`GET /api/transactions/`.

## 5. Assumptions (spec was unclear here)

- CSV header is `date,description,amount,type,reference` (the reference
  column is also accepted as `bank_reference`, `bank_ref` or `ref`;
  case-insensitive, surrounding spaces allowed). Column order does not
  matter. No other alias guessing.
- `X-Organization` carries the organization `slug`
  (`northwind`, `bluebird`).
- The reference check searches the normalized description **and** the
  normalized bank reference. The expected table forces this: line 2's
  bank reference is `FT20260403A` while `CC-1002` appears in its
  description, yet it must match as a reference suggestion.
- Line 8's description contains the full investor name
  ("Oakridge Holdings investment") so both CC-1005 and CC-1006 match
  on name + exact amount.
- Suggestions are frozen at import; later funding changes never
  re-run matching. The approve-time remaining recheck (409) handles
  stale suggestions instead.
- There is no auth layer: the header is tenancy, not security.
- Name + amount matching uses exact `remaining == amount`, no tolerance.
- One import is a single atomic bulk write: a crash imports nothing
  rather than half a file.

## 6. Trade-offs

- Denormalized `organization` FK on `LineItem` (duplicates the call's
  org) to keep every queryset scoped by one uniform filter.
- Small custom CORS middleware instead of django-cors-headers: one
  less dependency for a dev-only need.
- No pagination on list endpoints: fine for a reconciliation inbox of
  a few thousand rows; easy to add later.
- Frontend refetches after every action instead of websockets or a
  store: simplest correct behaviour for one page.

## 7. Optional Bonus: Airtable Sync (Built)

Implemented in `services/airtable.py`:
- Syncs `needs_review` transactions to an Airtable table via Personal Access Token (`AIRTABLE_PERSONAL_ACCESS_TOKEN`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`).
- Stores `airtable_record_id` and `airtable_sync_status` (`not_synced`, `synced`, `sync_failed`).
- Any network or Airtable failure is caught and logged, setting `sync_failed` without breaking the import.
- Easy to fake in tests via client injection and unit-tested in `test_airtable.py`.

## 8. Next steps (not built)

Real authentication (header is tenancy, not security), pagination on
lists for >10,000 rows, idempotency keys on approve for retries, and
background processing (Celery/RQ) for very large imports.

## 9. Integrity line

Integrity: this is my own work for this assessment — I designed and
wrote the backend, frontend, tests and docs myself, verified the full
suite passes, and checked the sample import against the expected table
under both organizations.
