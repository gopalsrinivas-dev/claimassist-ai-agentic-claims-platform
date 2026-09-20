# ClaimAssist backend — Day 11

Python 3.12+ FastAPI foundation. This package implements operational probes,
configuration, request telemetry, and error handling. Business services, persistence,
authentication mechanisms, workers, and AI integrations belong to later days.

## Local setup

From the repository root in PowerShell:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
.\backend\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-index --editable './backend[dev]'
Copy-Item .env.example .env
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --app-dir backend --no-access-log
```

Keep the environment at `backend/.venv`; recreate it there if moved, since console
launchers and activation scripts can embed absolute paths. From the repository
root, activate it with `. .\backend\.venv\Scripts\Activate.ps1` and confirm
`python -c "import sys; print(sys.executable)"` resolves to that environment.

Copy the example only when `.env` does not already exist. The default address is
`http://127.0.0.1:8000`; use Uvicorn's `--host` and `--port` options as needed.
Stop with Ctrl+C to run lifespan shutdown. Keep `--no-access-log`: raw server access
logs include URLs and query strings that the application deliberately excludes.
Runtime-only installation uses `requirements.lock`. To build/install the package,
use `python -m pip install --no-build-isolation --no-deps ./backend` after installing
the development lock, which includes the pinned build backend.

## Configuration

`Settings` reads environment variables first, then the repository-root `.env`,
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
| `CORS_ALLOWED_METHODS` | `["GET"]`; Day 11 accepts GET/HEAD/OPTIONS |
| `CORS_ALLOWED_HEADERS` | `["Content-Type","X-Correlation-ID"]` |
| `LOG_LEVEL` | `INFO`; DEBUG/INFO/WARNING/ERROR/CRITICAL |

Lists use JSON arrays. Empty environment values use defaults. Wildcard origins,
credential-bearing URLs, invalid paths and invalid setting values fail startup.
The shared `.env.example` retains future variables; Day 11 neither loads those
dependencies nor requires their credentials. Add their required-setting validation
when the corresponding integration is implemented.

## Architecture and probes

- `app/main.py`: application factory and middleware composition.
- `app/api/`: thin transport routers, response schemas, central error mapping.
- `app/api/v1/router.py`: empty composition point under the configured v1 prefix.
- `app/core/`: immutable settings, exception taxonomy, lifecycle readiness.
- `app/middleware/`: pure ASGI context, CORS, and unexpected-error boundaries.
- `app/observability/`: context variables and structured logging.

`GET /health` returns `200 {"status":"ok"}` for a responsive process.
`GET /ready` returns `200 {"status":"ready"}` after lifespan startup; before startup
and after shutdown it returns a `503 DEPENDENCY_UNAVAILABLE` error envelope.
This is application readiness only. No database, queue, storage or provider checks
are claimed. OpenAPI is available at `/openapi.json`, with Swagger UI at `/docs`.

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
.\.venv\Scripts\python.exe -m mypy .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip_audit -r requirements-dev.lock --no-deps --disable-pip --cache-dir .tmp/audit
```

Pytest reserves `backend/tmp/` for temporary test data and recreates it on each run.
Tests ignore developer settings and never use external services or real patient data.
Coverage includes branches and enforces at least 80%. Ruff supplies formatting,
lint and security rules; mypy runs in strict mode on application and test code.
Warnings are errors except a specifically identified Starlette 1.6 / AnyIO
`BlockingPortal` deprecation, which remains visible in test output.

The lock files pin the runtime and development dependency sets. Audit uses the
network to query vulnerability records; it is separate from the offline test suite.
Existing project design documentation remains the implementation source of truth.
