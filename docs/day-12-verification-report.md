# Day 12 database foundation — implementation and verification report

Verified on 2026-09-21 with Python 3.14.6 and PostgreSQL 18.4 on Windows.
Continued from the existing working tree. No commit or push was performed.
The continuation reran every required quality gate and the PostgreSQL checks;
the existing application and test implementation needed no further changes.

1. **Files created**
   - `backend/app/db/__init__.py`
   - `backend/app/db/base.py`
   - `backend/app/db/errors.py`
   - `backend/app/db/health.py`
   - `backend/app/db/session.py`
   - `backend/app/db/telemetry.py`
   - `backend/alembic.ini`
   - `backend/alembic/env.py`
   - `backend/alembic/script.py.mako`
   - `backend/alembic/versions/20260921_0001_database_foundation.py`
   - `backend/tests/test_database.py`
   - `backend/tests/test_migrations.py`
   - `backend/tests/integration/test_postgres.py`
   - This report.

2. **Files modified**
   - `backend/.env.example`
   - `backend/README.md`
   - `backend/pyproject.toml`
   - `backend/requirements.lock`
   - `backend/app/core/config.py`
   - `backend/app/core/exceptions.py`
   - `backend/app/core/lifecycle.py`
   - `backend/app/api/errors.py`
   - `backend/app/api/health.py`
   - `backend/app/api/v1/router.py` (roadmap wording removed from its docstring)
   - `backend/app/observability/logging.py`
   - `backend/tests/conftest.py`
   - `backend/tests/test_config.py`

   The pre-existing moves of `.env.example`, `.gitignore`, `AGENTS.md`, and
   `copy-to-project-docs.ps1` from the root into `backend/` were preserved.
   `backend/.env` was neither edited nor moved. `requirements-dev.lock` includes
   the runtime lock, so it inherits the new database dependency pins unchanged.

3. **Temporary files removed**
   Removed `backend/.tmp/` in full after stopping both disposable PostgreSQL
   instances, including `verify_database.py`, cluster data/logs, and pytest
   scratch data. The old `verify_day12.py`, `backend/tmp/`, and `backend/build/`
   were already absent at the start of this continuation. No application source
   was removed.
   Future pytest scratch files are confined to `backend/.tmp/pytest/`.
   The existing test harness recreates `.tmp/` automatically for pytest's nested
   basetemp directory. A rerun after cleanup verified that removing temporary
   artifacts does not break subsequent test runs; its scratch data was then removed.

4. **Final database folder**

   ```text
   backend/app/db/
   ├── __init__.py
   ├── base.py
   ├── errors.py
   ├── health.py
   ├── session.py
   └── telemetry.py
   ```

5. **Settings**
   Added required `database_url: SecretStr` and `sql_echo: bool = False`.
   `DATABASE_URL` is the sole connection source. PostgreSQL URLs are validated
   without reflecting credentials. No application connection defaults are
   hard-coded. Dotenv resolution uses `BACKEND_ROOT / ".env"`, preserving the
   existing working-tree change from the repository-root dotenv. Settings
   repr/JSON and validation text/structured errors redact secret inputs.

6. **Engine and session architecture**
   One lazy SQLAlchemy 2 engine and session factory belong to each application
   lifespan. Engine creation does not connect; shutdown disposes the pool.
   PostgreSQL uses psycopg 3, parameter hiding, pool pre-ping, bounded pool size,
   five-second checkout/connect timeouts, and a five-second statement timeout.
   Timeouts are per operation; DNS/socket behavior can affect total duration.
   No application retry loop or automatic write retry is implemented.

7. **Transactions**
   `transaction()` commits on success, rolls back on body/commit failure, and
   closes sessions on every exit, including cancellation. Failures propagate or
   receive controlled dependency mapping. `DatabaseSession` uses FastAPI function
   scope so commit completes before a success response is sent. Services consume
   this shared foundation rather than constructing ad-hoc engines or sessions.

8. **Readiness**
   `/health` remains a process-only probe. `/ready` checks lifecycle state and
   executes a lightweight read-only PostgreSQL query in FastAPI's thread pool.
   An unavailable database returns `503 DATABASE_UNAVAILABLE` with correlation
   ID and no driver details. Before startup/after shutdown the existing
   `DEPENDENCY_UNAVAILABLE` behavior remains. Live success and actual outage
   behavior were both verified; liveness remained 200 during the outage.

9. **Alembic**
   The INI has no connection string. Online migrations reuse application
   settings, engine construction, and `Base.metadata`; offline SQL uses the same
   validated settings. Stable metadata naming conventions are defined, with no
   registered domain tables. Migration execution is explicit, not part of startup.

10. **Baseline result**
    Revision `20260921_0001` intentionally has empty upgrade/downgrade bodies.
    Real PostgreSQL integration verified upgrade → downgrade → upgrade, current
    matching head, and `alembic check` reporting no pending operations. Alembic
    manages only `alembic_version`; downgrade empties its revision row.
    The actual local `claimassist_db` was already at this head during continuation.
    Read-only checks confirmed connectivity, matching current/head, no pending
    operations, and `alembic_version` as its only persistent table. Application
    readiness passed. No downgrade was run on that local development database;
    the round trip used a fresh disposable cluster.

11. **Tests and coverage**
    `python -m pytest`: **113 passed, 5 explicitly skipped** PostgreSQL integration
    tests. Verified with `PSYCOPG_IMPL=python` and PostgreSQL removed from PATH.
    `python -m pytest --postgres-integration`: **118 passed** against disposable
    PostgreSQL. Both runs reported **99.41% combined line/branch coverage**;
    all database modules reported 100%. Existing middleware, correlation, CORS,
    settings, health, logging, and error-contract tests remain passing.
    No SQLite replacement is used. Integration requires an explicit process
    `DATABASE_URL`, validates the baseline schema state, and never implicitly
    uses the developer's dotenv database.

12. **Ruff**
    `python -m ruff check .`: passed.

13. **Formatting**
    `python -m ruff format --check .`: passed, 40 files formatted.

14. **Typing**
    `python -m mypy app`: passed, 25 source files.
    Additional `python -m mypy .`: passed, 38 source files including tests.

15. **Dependency consistency**
    `python -m pip check`: no broken requirements found. Runtime additions are
    SQLAlchemy 2.0.54, psycopg 3.3.6 with the binary extra, and Alembic 1.20.0,
    plus their pinned transitive dependencies.

16. **Dependency audit**
    `python -m pip_audit`: no known vulnerabilities found. The local unpublished
    `claimassist-backend` package is skipped because it has no PyPI advisory entry;
    installed third-party dependencies were audited.

17. **Security and error contracts**
    `backend/.env` is ignored, untracked, and not staged. The example contains
    empty credential placeholders and safe non-secret defaults. Neither secrets
    nor real patient data were added. Connectivity/pool failures map to 503;
    unexpected SQLAlchemy errors use the existing generic 500 boundary with
    sanitized exception frames. URLs, parameters, SQL text, and raw exceptions
    never appear in client errors. Day-number identifiers are absent from
    application code, migrations, and tests; roadmap labels remain under `docs/`.

18. **Logging**
    Central JSON telemetry retains correlation IDs and safe dependency/duration
    fields. Errors are logged once at the HTTP boundary. Native SQL echo remains
    disabled: `SQL_ECHO=true` enables sanitized query timing events only.
    SQLAlchemy engine/pool and psycopg raw logs are centrally suppressed.
    Actual PostgreSQL tests verified that SQL literals and bound parameters do
    not appear in the emitted logs.

19. **Windows prerequisites and warnings**
    Verification used psycopg's supported pure Python driver with installed
    libpq. This is also the documented option if Windows Application Control
    blocks the binary wheel. When using it for application/Alembic/integration
    commands, each shell must add
    `D:\Workspace\softwares\PostgreSQL\18\bin` to PATH and set
    `PSYCOPG_IMPL=python`. The README gives explicit commands; no machine path or
    driver override is present in production code. Unit tests need neither.
    An inherited invalid `DEBUG` environment override was removed only from
    verification processes so the existing dotenv boolean could apply.
    One pre-existing Starlette/AnyIO `BlockingPortal` deprecation remains visible.
    Initial sandbox attempts encountered existing cache permissions and blocked
    audit network access. Approved reruns outside the sandbox passed pytest,
    mypy, and pip-audit without changes to application behavior or security policy.

20. **Remaining Day 12 TODOs**
    None. Future local shells still need the documented driver prerequisites.
    PostgreSQL integration tests intentionally require a disposable target and
    explicit opt-in. No temporary verifier is needed or retained.

21. **Scope**
    No Day 13+ functionality was implemented: no authentication, RBAC, business
    entities, document pipeline, workers, RAG, LLMs, agents, or frontend changes.
    Existing application factory and middleware behavior are preserved.

22. **Suggested commit**
    `feat(db): add PostgreSQL database foundation and verified migrations`

    Nothing was committed, staged, or pushed by this implementation.
