# 22 — Database Field Dictionary

This is the MVP implementation contract. Additional fields require a migration and documentation update.

## Common rules

- Primary IDs: UUID.
- Timestamps: UTC `created_at`, `updated_at` where applicable.
- Money: `NUMERIC(14,2)`.
- Never use float for money.
- Soft deletion is not automatically added; use explicit status/retention behavior.
- Foreign keys and important uniqueness rules are enforced in DB.

## users

| Field | Type | Rules |
|---|---|---|
| id | UUID | PK |
| email | varchar(320) | unique, not null |
| password_hash | text | not null |
| display_name | varchar(200) | not null |
| is_active | boolean | default true |
| created_at | timestamptz | not null |
| updated_at | timestamptz | not null |

## roles

| Field | Type | Rules |
|---|---|---|
| id | UUID | PK |
| code | varchar(64) | unique |
| name | varchar(120) | not null |

Codes:
`CLAIMS_PROCESSOR`, `CLAIMS_REVIEWER`, `SUPERVISOR`, `ADMINISTRATOR`, `AUDITOR`.

## user_roles

Composite uniqueness on `(user_id, role_id)`.

## members

- id UUID PK
- member_number varchar unique not null
- display_name varchar
- date_of_birth date nullable for synthetic demo
- created_at/updated_at

## providers

- id UUID PK
- provider_code varchar unique
- name varchar not null
- created_at/updated_at

## policies

- id UUID PK
- policy_number varchar unique
- name varchar
- created_at/updated_at

## policy_versions

- id UUID PK
- policy_id UUID FK not null
- version_code varchar not null
- effective_from date not null
- effective_to date nullable
- document_sha256 char(64) not null
- index_status enum not null
- created_at/updated_at
- unique `(policy_id, version_code)`

## claims

- id UUID PK
- claim_number varchar unique not null
- member_id UUID FK not null
- provider_id UUID FK not null
- policy_version_id UUID FK not null
- status enum not null
- service_start_date date not null
- service_end_date date not null
- claimed_amount numeric(14,2) not null
- currency char(3) not null
- claim_version integer not null default 1
- row_version integer not null default 1
- created_by UUID FK users not null
- created_at/updated_at
- check `claimed_amount > 0`
- check `service_end_date >= service_start_date`

Indexes:
- `(status, created_at)`
- `(member_id, service_start_date)`
- `(provider_id, service_start_date)`
- `(policy_version_id)`

## claim_lines

- id UUID PK
- claim_id UUID FK not null
- line_number integer not null
- description text
- service_date date
- amount numeric(14,2) not null
- procedure_code varchar nullable
- unique `(claim_id, line_number)`

## claim_documents

- id UUID PK
- claim_id UUID FK not null
- document_type enum not null
- original_filename varchar not null
- object_key text unique not null
- sha256 char(64) not null
- content_type varchar not null
- size_bytes bigint not null
- processing_status enum not null
- uploaded_by UUID FK users not null
- created_at/updated_at
- unique `(claim_id, sha256)`

## extracted_facts

- id UUID PK
- claim_document_id UUID FK not null
- fact_type varchar not null
- value_json jsonb not null
- normalized_value text nullable
- source_page integer nullable
- source_span text nullable
- extractor_version varchar not null
- confidence numeric(5,4) nullable
- created_at

## policy_chunks

- id UUID PK
- policy_version_id UUID FK not null
- section varchar nullable
- clause_id varchar nullable
- page integer nullable
- chunk_text text not null
- chunk_hash char(64) not null
- embedding vector(dimension chosen by configured embedding model)
- metadata jsonb not null default `{}`
- unique `(policy_version_id, chunk_hash)`

## eligibility_checks

- id UUID PK
- claim_id UUID FK not null
- claim_version integer not null
- check_type varchar not null
- result enum `PASS|FAIL|UNKNOWN`
- evidence jsonb not null
- rules_version varchar not null
- created_at

## coverage_checks

Same pattern as eligibility checks, plus:
- calculated_amount numeric(14,2) nullable
- policy_chunk_ids jsonb not null default `[]`

## risk_signals

- id UUID PK
- claim_id UUID FK
- claim_version integer
- signal_type varchar
- severity enum `LOW|MEDIUM|HIGH`
- evidence jsonb
- detector_version varchar
- created_at

Risk signal is not a fraud verdict.

## agent_runs

- id UUID PK
- claim_id UUID FK not null
- claim_version integer not null
- policy_version_id UUID FK not null
- correlation_id UUID not null
- status enum not null
- graph_version varchar not null
- prompt_version varchar not null
- model_provider varchar
- model_name varchar
- input_tokens bigint default 0
- output_tokens bigint default 0
- estimated_cost numeric nullable
- started_at/finished_at
- unique run/dedup key enforced through ProcessingJob

## tool_calls

- id UUID PK
- agent_run_id UUID FK not null
- tool_name varchar not null
- tool_version varchar not null
- input_hash char(64) not null
- sanitized_input jsonb
- sanitized_output jsonb
- status enum not null
- error_code varchar nullable
- latency_ms integer
- created_at

## recommendations

- id UUID PK
- agent_run_id UUID FK unique not null
- category enum not null
- reasons jsonb not null
- missing_documents jsonb not null
- eligibility jsonb not null
- coverage_findings jsonb not null
- risk_signals jsonb not null
- citations jsonb not null
- requires_human_review boolean not null default true
- created_at

## human_reviews

- id UUID PK
- claim_id UUID FK not null
- recommendation_id UUID FK nullable
- reviewer_id UUID FK users not null
- claim_version integer not null
- decision enum not null
- override_reason_code varchar nullable
- comments text nullable
- created_at

## audit_events

Append-only:
- id UUID PK
- actor_type varchar
- actor_id UUID nullable
- event_type varchar not null
- entity_type varchar not null
- entity_id UUID not null
- correlation_id UUID not null
- safe_before jsonb nullable
- safe_after jsonb nullable
- metadata jsonb not null default `{}`
- created_at timestamptz not null

No normal update/delete API for audit events.

## processing_jobs

- id UUID PK
- job_type varchar
- dedup_key varchar unique
- entity_id UUID
- entity_version integer
- status enum
- attempt integer default 0
- max_attempts integer
- last_error_code varchar nullable
- next_retry_at timestamptz nullable
- lease_expires_at timestamptz nullable
- created_at/updated_at

## idempotency_records

- id UUID PK
- actor_id UUID
- operation varchar
- idempotency_key varchar
- request_hash char(64)
- result_reference jsonb nullable
- status_code integer nullable
- expires_at timestamptz
- created_at
- unique `(actor_id, operation, idempotency_key)`
