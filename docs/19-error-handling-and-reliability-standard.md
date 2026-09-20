# 19 — Error Handling and Reliability Standard

## Purpose

This file defines the code-level error-handling contract for ClaimAssist.
The goal is predictable failures, safe rollback, useful diagnostics and no silent data corruption.

## Exception taxonomy

Application code must use explicit domain/application exceptions rather than generic `Exception`
for expected failures.

Recommended hierarchy:

```text
ClaimAssistError
├── ValidationError
├── AuthenticationError
├── AuthorizationError
├── ResourceNotFoundError
├── ConflictError
│   ├── ClaimVersionConflictError
│   ├── InvalidStateTransitionError
│   └── IdempotencyConflictError
├── DependencyError
│   ├── DatabaseUnavailableError
│   ├── ObjectStorageError
│   ├── QueueUnavailableError
│   └── LLMProviderError
├── DocumentProcessingError
├── RetrievalError
├── ToolExecutionError
└── UnsafeOrInsufficientEvidenceError
```

## FastAPI global handlers

Define centralized handlers that map internal exceptions to the API error envelope.

Rules:
- Never return raw stack traces to clients.
- Always include `correlation_id`.
- Log unexpected exceptions once at the application boundary with `exc_info`.
- Map expected domain errors to stable machine-readable error codes.
- Use `500 INTERNAL_ERROR` only for unexpected server failures.

## HTTP mapping

| Internal failure | HTTP |
|---|---:|
| Request/schema validation | 422 |
| Invalid credentials | 401 |
| Authenticated but unauthorized | 403 |
| Missing resource | 404 |
| Claim version/state/idempotency conflict | 409 |
| Upload too large | 413 |
| Rate limited | 429 |
| Temporary external dependency unavailable | 503 |
| Unexpected server error | 500 |

## `try/except` rules

Use `try/except` only when the code can:
1. add meaningful context;
2. translate a lower-level error to an application error;
3. perform required cleanup/rollback;
4. implement a bounded retry;
5. choose a documented safe fallback.

Do **not**:
- write `except Exception: pass`;
- swallow errors and return success;
- retry non-idempotent writes blindly;
- catch an exception only to log and rethrow at every layer;
- expose provider/database exception messages to API clients.

## Transaction rule

Application-service pattern:

```text
authorize
  -> validate state/version
  -> begin transaction
  -> perform deterministic writes
  -> write audit event
  -> commit
```

If any write fails:
- rollback transaction;
- do not emit a successful business response;
- record safe failure telemetry.

Never hold a database transaction open while waiting for an LLM, object-storage network call or long-running parser.

## Dependency calls

Every external dependency call must define:
- connect/read timeout;
- maximum attempts;
- retryable error set;
- backoff policy;
- idempotency behavior;
- safe failure mapping;
- metrics.

## Retry policy

Retry only transient failures such as selected timeouts/temporary availability errors.

Do not retry:
- validation failures;
- authorization failures;
- deterministic business-rule failures;
- malformed provider responses without a bounded schema-repair policy.

Use exponential backoff with jitter conceptually; configure concrete values per adapter.

## Circuit-breaker / degradation strategy

For repeated provider failures:
- stop hammering the failing dependency;
- surface degraded/manual-review mode;
- preserve queued work where safe;
- expose health/readiness degradation.

## Async job failures

A job records:
- job_id;
- attempt;
- failure_code;
- sanitized error_summary;
- last_failed_at;
- next_retry_at;
- terminal/retryable state.

After attempts are exhausted:
- move to failed/dead-letter state;
- do not fabricate analysis;
- expose recovery action to authorized operator/reviewer.

## Logging

Log:
- correlation ID;
- actor ID/type where allowed;
- claim/run/tool IDs;
- error code;
- dependency name;
- latency;
- retry attempt.

Never log:
- passwords/tokens/API keys;
- full uploaded document content;
- unnecessary member/health details;
- raw authorization headers.

## Error-handling test requirements

Each critical service must test:
- success;
- validation error;
- authorization error;
- not found;
- version/state conflict;
- dependency timeout;
- transaction rollback;
- retry exhaustion;
- unexpected exception mapping.
