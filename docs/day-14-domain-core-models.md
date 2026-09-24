# Day 14 — Domain Core Models

**Project:** ClaimAssist AI – Agentic Healthcare Claims Platform

## Goal

Complete Day 14 in sequence. Do not silently introduce business rules that are absent from the core design documents.

## Tasks

1. Implement Member, Provider, Policy, PolicyVersion, Claim and ClaimLine.
2. Add constraints/indexes and migrations.
3. Add repository tests.

## Expected Deliverables

- `domain core`

## Policy index status contract

`PolicyVersion.index_status` is non-null and defaults to `PENDING` in both
the ORM and database. Its only values are:

| Value | Meaning |
|---|---|
| `PENDING` | Indexing not started. |
| `INDEXING` | Ingestion/embedding/index-validation in progress. |
| `READY` | Indexing successfully validated and usable for retrieval. |
| `FAILED` | Indexing failed and requires retry/investigation. |

This task stores the status only. It adds no indexing workers, RAG behavior, APIs,
workflow-transition service, document uploads, or AI integrations.

## Persistence boundaries

- Models live in `backend/app/domain/models.py` and share the existing metadata.
- Business dates use `date`; monetary values use `Decimal` / `NUMERIC(14,2)`.
- Varchar fields with no documented length remain unbounded. Fields without a
  documented required constraint remain nullable; UUID primary keys, references,
  and applicable timestamps are required. No additional fields are introduced.
- Parent deletion is rejected while references remain; there are no delete cascades.
- ORM claim updates/deletes use `row_version` for optimistic concurrency. Bulk SQL
  writers must explicitly check versions. `claim_version` is stored independently;
  workflow services are responsible for its future business semantics.
- Timestamps default in PostgreSQL; ORM updates refresh `updated_at`. Direct SQL
  writers must maintain `updated_at` themselves.

## 4-Hour Time Box

- 00:00–00:30 — review previous output and current source-of-truth docs
- 00:30–03:00 — main design/implementation
- 03:00–03:45 — tests/review/validation
- 03:45–04:00 — update docs + commit

## Definition of Done

- [x] Today's source-of-truth documents/code are complete
- [x] Conflicts with earlier design have been resolved
- [x] Security/authorization implications reviewed
- [x] Relevant tests or validation completed
- [x] No secrets or real patient data added
- [x] Git diff/status reviewed
- Commit intentionally deferred: the user requested no commit or push.

## Verification

Verified on 2026-09-24 using PostgreSQL 18.4 and the repository virtual environment:
- Unit run: 137 passed; 84 PostgreSQL tests skipped by the explicit opt-in gate.
- Full PostgreSQL run: 221 passed, including all earlier foundation/identity tests.
- Overall branch-inclusive coverage: 99.52%; domain model coverage: 100%.
- Domain upgrade/downgrade/upgrade and `alembic check` passed, preserving identity
  data through the domain downgrade and removing/recreating both domain enum types.
- Ruff lint/format, `mypy app`, and `pip check` passed. `pip_audit` found no known
  dependency vulnerabilities; the local project package is not auditable on PyPI.
- The existing Starlette/AnyIO deprecation warning remains visible.

Negative paths cover foreign keys, required fields, uniqueness, invalid enums,
date ranges, nonpositive claim totals, monetary overflow, stale updates/deletes,
transaction rollback, and sensitive-data logging. No remaining core-schema TODOs.

## Suggested Commit

`feat(domain): add core healthcare claims schema`
