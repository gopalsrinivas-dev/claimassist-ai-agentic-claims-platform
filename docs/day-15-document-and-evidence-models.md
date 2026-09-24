# Day 15 — Document And Evidence Models

**Project:** ClaimAssist AI – Agentic Healthcare Claims Platform

## Goal

Complete Day 15 in sequence. Do not silently introduce business rules that are absent from the core design documents.

## Tasks

1. Implement ClaimDocument, ExtractedFact, PolicyChunk.
2. Add provenance/checksum fields.
3. Add migrations/tests.
4. Verify PostgreSQL upgrade/downgrade/upgrade, Alembic metadata agreement, and
   all backend quality gates. Leave changes uncommitted for review.

## Expected Deliverables

- `document data model`

## Canonical persistence contracts

`ClaimDocument.document_type` is required and permits exactly `CLAIM_FORM`,
`HOSPITAL_BILL`, `DISCHARGE_SUMMARY`, `PRESCRIPTION`, `INVESTIGATION_REPORT`, and
`IMPLANT_INVOICE`. It has no default. `POLICY_DOCUMENT` is excluded; policy documents
belong to the PolicyVersion / policy-ingestion path.

`ClaimDocument.processing_status` is required and defaults to `UPLOADED` in both
the ORM and database. Its complete value set and meanings are:
- `UPLOADED`: document metadata/file persisted; extraction has not started.
- `PROCESSING`: document extraction/processing is in progress.
- `EXTRACTED`: processing completed successfully.
- `FAILED`: processing failed and may be retried later.

Do not add `PolicyChunk.embedding`. Its exact vector dimension/storage contract is
intentionally deferred to Day 25. This task implements persistence only, with no
upload/storage API, extraction, workers, chunking, embeddings, retrieval, or agents.

Preserve source document/page/span, extractor version, policy version/clause/page,
checksums, JSON values, and optional confidence exactly as documented. Binary files
remain outside PostgreSQL; sensitive evidence must not appear in logs. Parent
deletes are rejected while evidence references remain; no delete cascades are added.
Only documented defaults and constraints apply, with no additional checksum format,
confidence range, page numbering, or size validation rules introduced here.

## 4-Hour Time Box

- 00:00–00:30 — review previous output and current source-of-truth docs
- 00:30–03:00 — main design/implementation
- 03:00–03:45 — tests/review/validation
- 03:45–04:00 — update docs and inspect the uncommitted diff

## Definition of Done

- [x] Today's source-of-truth documents/code are complete
- [x] Enum contracts and embedding deferral are explicit
- [x] Security/authorization implications reviewed
- [x] Relevant tests or validation completed
- [x] Synthetic fixtures only; local secrets remain ignored
- [x] Git diff/status reviewed
- [x] Changes left uncommitted as requested

## Verification record

- Added `ClaimDocument`, `ExtractedFact`, and `PolicyChunk` in `app/domain/models.py`.
- One migration: `20260924_0004`, following `20260922_0003`.
- Unit suite: 141 passed; PostgreSQL tests require explicit opt-in.
- Full suite on an isolated disposable PostgreSQL database: 265 passed, including
  124 PostgreSQL tests; application branch/line coverage 99.56%.
- PostgreSQL upgrade/downgrade/upgrade, Alembic current/heads/check, enum inspection,
  and metadata comparison including server defaults passed. Earlier domain data
  survived the Day 15 downgrade. The disposable database was removed afterward.
- Ruff lint/format, `mypy app`, `pip check`, and `pip_audit` passed. No known
  dependency vulnerabilities; the local application package is not listed on PyPI.
- Existing Starlette/AnyIO deprecation warning remains visible. Optional broader
  `mypy app tests` still finds pre-existing identity/domain test typing issues;
  the new evidence tests pass focused strict typing.
- No new API or workflow writes: existing transaction/error boundaries remain.
  Negative tests prove constraint rejection and rollback without evidence logging.
- No remaining Day 15 implementation work. Day 16+ behavior and Day 25 vectors
  remain deferred.

## Suggested Commit

`day-15: Document and evidence models`
