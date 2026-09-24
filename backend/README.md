# ClaimAssist backend

Python 3.12+ FastAPI foundation. This package implements operational probes,
configuration, request telemetry, error handling, PostgreSQL infrastructure,
and identity, core healthcare-claims, and document/evidence persistence.
Authentication mechanisms, business services, workers, and AI integrations are outside this foundation.

## Local setup

From the repository root in PowerShell:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
.\backend\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-index --editable './backend[dev]'
Copy-Item backend/.env.example backend/.env
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --app-dir backend --no-access-log
```

Keep the environment at `backend/.venv`; recreate it there if moved, since console
launchers and activation scripts can embed absolute paths. From the repository
root, activate it with `. .\backend\.venv\Scripts\Activate.ps1` and confirm
`python -c "import sys; print(sys.executable)"` resolves to that environment.

Copy the example only when `backend/.env` does not already exist. Create a local
PostgreSQL database named `claimassist_db` and supply its connection URL through
`DATABASE_URL` in `backend/.env` before startup. No connection values are embedded
in application code. Apply the migration from `backend/` with
`python -m alembic upgrade head`, using the activated environment.
The default address is
`http://127.0.0.1:8000`; use Uvicorn's `--host` and `--port` options as needed.
Stop with Ctrl+C to run lifespan shutdown. Keep `--no-access-log`: raw server access
logs include URLs and query strings that the application deliberately excludes.
Runtime-only installation uses `requirements.lock`. To build/install the package,
use `python -m pip install --no-build-isolation --no-deps ./backend` after installing
the development lock, which includes the pinned build backend.

## Configuration

`Settings` reads environment variables first, then `backend/.env`,
then safe defaults. There is no settings singleton or import-time app construction.
For an installed package outside this checkout, supply environment variables or an
explicit dotenv path through `Settings(_env_file=...)` when composing the factory.

| Setting | Default / behavior |
|---|---|
| `APP_NAME` | `ClaimAssist AI` |
| `APP_ENV` | `development`; also `test`, `staging`, `production` |
| `DEBUG` | `false`; rejected in staging/production; never enables traceback pages |
| `API_V1_PREFIX` | `/api/v1`; validated path segments |
| `CORS_ALLOWED_ORIGINS` | `[]`; explicit origins, e.g. `["http://localhost:3000"]` |
| `CORS_ALLOW_CREDENTIALS` | `false` |
| `CORS_ALLOWED_METHODS` | `["GET"]`; accepts GET/HEAD/OPTIONS |
| `CORS_ALLOWED_HEADERS` | `["Content-Type","X-Correlation-ID"]` |
| `LOG_LEVEL` | `INFO`; DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `DATABASE_URL` | Required secret; PostgreSQL URL with explicit host and database; no fallback connection |
| `SQL_ECHO` | `false`; opt-in sanitized query timing events, never native SQL text/parameters |

Lists use JSON arrays. Empty environment values use defaults. Wildcard origins,
credential-bearing URLs, invalid paths and invalid setting values fail startup.
The shared `.env.example` retains future variables; the foundation neither loads those
dependencies nor requires their credentials. Its empty `DATABASE_URL` must be filled
locally. Both `postgresql://` and `postgresql+psycopg://` select the psycopg 3 driver.
Use percent encoding for reserved characters in credentials. The URL is stored as
`SecretStr`, excluded from settings repr, and masked in JSON. Settings validation
redacts inputs in text, structured errors, and JSON, including model-level errors.
Add other required-setting validation
when the corresponding integration is implemented.

## Architecture and probes

- `app/main.py`: application factory and middleware composition.
- `app/api/`: thin transport routers, response schemas, central error mapping.
- `app/api/v1/router.py`: empty composition point under the configured v1 prefix.
- `app/core/`: immutable settings, exception taxonomy, lifecycle readiness.
- `app/middleware/`: pure ASGI context, CORS, and unexpected-error boundaries.
- `app/observability/`: context variables and structured logging.
- `app/db/`: declarative metadata, shared engine/session factories, readiness, safe telemetry.
- `app/identity/`: User, Role, and explicit UserRole association models.
- `app/domain/`: Member, Provider, Policy, PolicyVersion, Claim, ClaimLine,
  ClaimDocument, ExtractedFact, and PolicyChunk models.
- `alembic/`: migration environment and foundation, identity, core domain, and evidence revisions.

`GET /health` returns `200 {"status":"ok"}` for a responsive process.
`GET /ready` runs a read-only connectivity query after lifespan startup. It returns
`200 {"status":"ready"}` when PostgreSQL responds, or a controlled
`503 DATABASE_UNAVAILABLE` envelope on database failure. Before startup and after
shutdown it returns `503 DEPENDENCY_UNAVAILABLE`. The sync probe runs in FastAPI's
thread pool, leaving the async event loop responsive. Connections are always released.
Readiness checks connectivity, not migration revision or business schema state.
OpenAPI is available at `/openapi.json`, with Swagger UI at `/docs`.

## Database lifecycle and migrations

The lifespan constructs one lazy PostgreSQL engine and session factory per app,
then disposes the pool on shutdown. Importing modules or constructing the app does
not connect. The pool allows 5 connections plus 5 overflow connections, waits at
most 5 seconds for checkout, validates pooled connections, and sets 5-second
connection and statement timeouts. There is no application retry loop or write
retry; SQLAlchemy's pool may replace stale connections during pre-ping. These
timeouts bound individual operations, not a strict end-to-end readiness deadline;
DNS resolution and a network blackhole can depend on OS socket timeouts.

Use `DatabaseSession` in synchronous endpoints or `transaction(session_factory)`
at a service composition boundary. Work succeeds -> commit; body/commit failure
-> rollback; every exit -> close. Non-database exceptions propagate. SQLAlchemy
connectivity/pool failures become controlled application errors without driver
messages; other SQLAlchemy failures propagate to the centralized safe 500 boundary. The
dependency uses `scope="function"` so commit finishes before a success response
can be sent. Services must not create their own engines/sessions, commit inside
this unit of work, or hold transactions across slow external calls. Synchronous
database operations must not run directly on the async event loop.

`Base.metadata` defines stable names for indexes, primary/foreign keys, unique
constraints, and explicitly named check constraints. Importing `app.identity.models`
registers the three identity tables; `app.domain.models` registers the nine domain/evidence
tables. Alembic imports both explicitly.

`users` has a UUID primary key, unique required email (320 characters), required
password hash (text) and display name (200 characters), an active flag defaulting
to true, and required timezone-aware creation/update timestamps. UUIDs are generated
by the ORM; timestamps default in PostgreSQL, and ORM updates refresh `updated_at`.
Direct SQL writers must explicitly maintain `updated_at` when changing a user.
`roles` has a UUID primary key, unique required code (64 characters), and required
name (120 characters). `user_roles` links them through two required foreign keys
and a composite primary key `(user_id, role_id)`, with a separate role lookup index.
Both parents expose `user_roles`; each assignment exposes `user` and `role`.
Assignments must be explicitly removed before deleting a referenced user or role.
No roles, users, credentials, or assignments are seeded. Role codes remain data;
this schema introduces no permission tables or authorization behavior.

The core domain links each claim to a member, provider, policy version, and creator
user; each policy owns versions and each claim owns lines. UUID primary keys,
foreign keys, documented unique keys, valid date ranges, and positive claim totals
are enforced in PostgreSQL. Money uses `Decimal` / `NUMERIC(14,2)`. Claim lookup
indexes cover status/creation time, member/service date, provider/service date,
and policy version. Referenced parents cannot be deleted until children are removed.
The six core domain entities except claim lines have creation/update timestamps, with the
same ORM update and direct SQL responsibilities as users.

`PolicyVersion.index_status` permits only `PENDING`, `INDEXING`, `READY`, and
`FAILED`, is required, and defaults to `PENDING` in the ORM and database.
Claim ORM updates/deletes check `row_version`, and updates increment it; stale writes raise
`StaleDataError` and the shared transaction boundary rolls back. `claim_version`
is independent. Bulk SQL writers must explicitly check row versions. This schema
adds no API, workflow transition service, indexing worker, or document processing.

Day 15 adds `ClaimDocument` (claim and uploader references), `ExtractedFact`
(document reference), and `PolicyChunk` (policy-version reference). Claims expose
`documents`, documents expose `facts`, and policy versions expose `chunks`.
Document types are exactly `CLAIM_FORM`, `HOSPITAL_BILL`, `DISCHARGE_SUMMARY`,
`PRESCRIPTION`, `INVESTIGATION_REPORT`, and `IMPLANT_INVOICE`; policy documents
use the policy-ingestion path. Processing status is required, defaults to `UPLOADED`
in Python and PostgreSQL, and also permits `PROCESSING`, `EXTRACTED`, and `FAILED`.
Object keys are globally unique; document checksums are unique per claim and
chunk hashes per policy version. Evidence references reject parent deletion.
Documents have creation/update timestamps; facts have only creation timestamps.
Chunks have no timestamps or embedding column. Vector dimensions remain deferred
to Day 25. JSONB preserves untrusted values as data; fact confidence uses
`Decimal` / `NUMERIC(5,4)`. Chunk `metadata_json` maps to the SQL `metadata` column
and defaults to an independent empty object per row. Replace JSON attribute values
when updating them; in-place nested JSON edits are not tracked by these mappings.
These are persistence contracts only: no storage, extraction, chunking, retrieval,
worker, service write API, or claim-decision behavior is added.

Alembic imports the same `Settings`, engine constructor, and metadata. Its INI
contains no URL, and it does not interpolate credentials through ConfigParser.
Revision `20260921_0001` intentionally has empty upgrade/downgrade functions.
Alembic creates its own `alembic_version` table; downgrade to base removes the
revision row, leaving an empty version table. Revision `20260921_0002` creates only
`users`, `roles`, and `user_roles`; its downgrade removes assignments before parents.
Revision `20260922_0003` adds `members`, `providers`, `policies`, `policy_versions`,
`claims`, and `claim_lines`, plus the claim and policy index status enum types.
Its downgrade removes only those six tables and their enum types, preserving identity data.
Revision `20260924_0004` adds only the three evidence tables and two document enum
types. Downgrading to `20260922_0003` removes those tables/types while preserving
the identity and core domain tables and data.
Migrations run explicitly, never automatically during application startup.

From `backend/`, with the virtual environment activated:

```powershell
python -m alembic heads
python -m alembic upgrade head --sql
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

To verify reversibility on a disposable PostgreSQL database, set `DATABASE_URL`
to that database, run `upgrade head`, `downgrade base`, then `upgrade head`.
At head, check that the twelve identity/domain/evidence tables and `alembic_version`
exist and the version row is `20260924_0004`. Downgrading to `20260921_0002` removes the domain
schema; downgrading to `20260921_0001` also removes identity tables. Downgrading to
base also removes the revision row. Downgrades destroy data in removed tables,
so use a disposable database for verification.
Offline identity downgrade rendering is
`python -m alembic downgrade 20260921_0002:20260921_0001 --sql`.

## Logs and correlation

At `INFO`, stdout contains one JSON event per line:
`application.startup`, `request.started`, `request.error` when needed,
`request.completed`, and `application.shutdown`.
Request events include `method`, safe route-template `path`, and `correlation_id`.
Completion includes `status_code`, `duration_ms`, and `response_completed`.
Unmatched paths are logged as `<unmatched>`. Query strings and path-parameter
values are excluded. Lifecycle events have no request ID. Higher log thresholds
intentionally suppress informational events.

`X-Correlation-ID` accepts exactly one nonzero UUID in hyphenated form, normalizes
its casing, and otherwise generates UUID4. Duplicate, malformed, empty, oversized,
and injection-like values are replaced. It is available in
`request.state.correlation_id` and `get_correlation_id()` during processing,
returned on every response, and exposed to allowed CORS origins. Context is reset
after each request, including failures, and isolated between concurrent requests.
The ID is telemetry only; it never grants authority or proves caller identity.

Use fixed event names and reviewed metadata in `claimassist.*` loggers. The formatter
allow-lists metadata and serializes `exc_info` as exception type and code locations.
It excludes exception messages, source lines, local values, chained errors, full
file paths, bodies, document content, credentials and healthcare/member data.
Logs are ready for a JSON collector; no OpenTelemetry exporter is installed.

Database successes emit `database.readiness.completed` with duration and dependency
name; errors log once at the existing HTTP boundary with the safe error code,
dependency name, and request correlation context. Alembic failures use
`database.migration.failed`. `SQL_ECHO=true` enables `database.query.completed`
timing events at INFO. Native SQLAlchemy echo stays disabled even when this flag
is true, since hiding parameters alone would not hide sensitive SQL literals.
Raw SQLAlchemy engine/pool and psycopg logging are suppressed centrally. No URL,
SQL statement, parameter, result row, or raw database exception is logged.

## Errors and CORS

All application/framework errors, invalid request bodies, rejected CORS preflights,
and unexpected failures use:

```json
{"error":{"code":"VALIDATION_ERROR","message":"The request is invalid.","details":{},"correlation_id":"uuid"}}
```

| Exception / condition | HTTP | Code |
|---|---|---|
| `ClaimAssistError` | 400 | `APPLICATION_ERROR` |
| `ValidationError` / request validation | 422 | `VALIDATION_ERROR` |
| `AuthenticationError` | 401 | `AUTHENTICATION_ERROR` |
| `AuthorizationError` | 403 | `AUTHORIZATION_ERROR` |
| `ResourceNotFoundError` | 404 | `RESOURCE_NOT_FOUND` |
| `ConflictError` | 409 | `CONFLICT` |
| `DependencyError` | 503 | `DEPENDENCY_UNAVAILABLE` |
| `DatabaseUnavailableError` / SQLAlchemy connectivity or pool failure | 503 | `DATABASE_UNAVAILABLE` |
| Unexpected SQLAlchemy failure | 500 | `INTERNAL_ERROR` |
| Unexpected exception / invalid response schema | 500 | `INTERNAL_ERROR` |

Expected errors use fixed, reviewed class-level messages, ignoring exception
arguments. Validation details are deliberately empty to avoid reflecting private
input or arbitrary object keys. Framework 404/405/413/429 failures also receive
stable codes. Protocol headers (`Allow`, `WWW-Authenticate`, `Retry-After`) are
preserved when provided by server code. The exception patterns are infrastructure;
they do not implement login, authorization, or protected business endpoints.

Middleware runs context -> CORS -> unexpected-error boundary -> central expected
handlers -> routes. This preserves CORS and correlation headers on 500 responses.
Unexpected errors are logged once at the application boundary with sanitized
`exc_info`. If a response has already started, it cannot become a JSON 500: the
boundary logs the failure and raises a generic transport failure to abort delivery
without exposing the original exception to server logs. There are no streaming
endpoints in the shipped API.

## Quality checks

From `backend/`, using the repository virtual environment:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip_audit
.\.venv\Scripts\python.exe -m pip_audit -r requirements-dev.lock --no-deps --disable-pip --cache-dir .tmp/audit
```

Pytest reserves `backend/.tmp/pytest/` for temporary test data and recreates it on each run.
The test harness creates the parent `.tmp/` when absent, including after cleanup.
Unit tests ignore developer settings and mock engine construction at the application
lifespan boundary. They need neither a running server nor psycopg/libpq to create
`TestClient`. Production startup still constructs the real PostgreSQL engine.
Run `python -m pytest` for the unit suite; PostgreSQL integration tests are explicitly
skipped unless `--postgres-integration` is supplied. No test uses real patient data.

For real driver, transaction, readiness, sanitized SQL telemetry, and migration
verification, supply `DATABASE_URL` as a process environment variable pointing to
a **disposable PostgreSQL database with no business tables**, then run:

```powershell
python -m pytest --postgres-integration
```

This runs the entire suite including the PostgreSQL tests. The integration suite
does not read the developer's dotenv connection implicitly, performs a baseline
upgrade/downgrade/upgrade and identity and domain upgrade/downgrade/upgrade, and rejects
databases containing business tables or an unexpected migration revision.
Transaction tests use a connection-local temporary
table and remove it afterward. Identity tests check relationships, defaults,
timestamps, uniqueness, required fields, lengths, foreign keys, explicit deletion,
transaction rollback, safe telemetry, and migration/metadata agreement. They restore
the baseline after each test. Domain tests additionally verify exact money,
date and amount constraints, enum values/defaults, stale updates/deletes, and
identity preservation during domain downgrade. `alembic check` verifies metadata
agreement before and after the domain round trip.
Evidence tests also check exact enums, SQL NULL rejection, JSON value preservation,
provenance and confidence, defaults without the ORM, scoped deduplication, rollback,
parent deletion rejection, safe telemetry, and upgrade/downgrade/upgrade. Explicit
metadata comparison includes server defaults, with separate PostgreSQL enum checks.
Only Alembic's version table persists. The suite
uses PostgreSQL exclusively; there is no SQLite substitute.
Coverage includes branches and enforces at least 80%. Ruff supplies formatting,
lint and security rules; the required mypy gate runs in strict mode on application code.
The new evidence tests also pass a focused strict type check. A broader `mypy app tests`
run still reports pre-existing typing issues in the identity/domain test modules.
Warnings are errors except a specifically identified Starlette 1.6 / AnyIO
`BlockingPortal` deprecation, which remains visible in test output.

The lock files pin the runtime and development dependency sets. Audit uses the
network to query vulnerability records; it is separate from the offline test suite.
Existing project design documentation remains the implementation source of truth.

### Windows driver compatibility

The psycopg binary extra normally bundles libpq. If Windows Application Control
blocks that wheel, use psycopg's supported pure Python implementation with a
locally installed PostgreSQL client library. Add that installation's `bin` directory
to the process PATH and set `$env:PSYCOPG_IMPL = 'python'` before running Python.
For this Windows workstation, from `backend/` with the virtual environment active:

```powershell
$postgresBin = 'D:\Workspace\softwares\PostgreSQL\18\bin'
if (!(Test-Path (Join-Path $postgresBin 'libpq.dll'))) {
    throw 'The PostgreSQL client library is not installed at the selected location.'
}
$env:PATH = "$postgresBin;$env:PATH"
$env:PSYCOPG_IMPL = 'python'
python -c "import psycopg; print(psycopg.pq.__impl__, psycopg.pq.version())"
```

Apply this in **each shell** used to run the application, Alembic, or PostgreSQL
integration tests. Setting `PSYCOPG_IMPL=python` alone is insufficient: libpq and
its dependent DLLs must be discoverable. Adjust the documented path on other
machines. Unit-only tests require neither this PATH change nor a PostgreSQL server.
The application contains no machine-specific path or driver-implementation override.
Do not disable machine security policy. This workstation's verification used
that supported driver option with PostgreSQL 18.4.

Environment variables take priority over dotenv: an unrelated process-level
`DEBUG` value can fail boolean validation. Use a valid boolean or remove that
process override so `backend/.env` supplies it.
