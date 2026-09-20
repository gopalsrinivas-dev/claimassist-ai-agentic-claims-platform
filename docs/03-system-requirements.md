# 03 — System and Non-Functional Requirements

| ID | Area | Requirement |
|---|---|---|
| NFR-001 | Security | Least privilege, safe file handling, input validation, secret hygiene, complete privileged-action audit. |
| NFR-002 | Reliability | Idempotent processing, bounded retries with backoff, failed-job capture, explicit recovery paths. |
| NFR-003 | Performance | Long-running extraction/embedding/agent work is asynchronous; APIs remain responsive. |
| NFR-004 | Scalability | Stateless API tier, horizontally scalable workers, indexed DB access, pagination and backpressure. |
| NFR-005 | Explainability | Recommendations reference rules, evidence, tool outputs, policy version and model metadata. |
| NFR-006 | Maintainability | Modular boundaries, typed contracts, migrations, ADRs, tests and clear ownership. |
| NFR-007 | Observability | Correlation IDs, structured logs, traces, metrics, queue depth, model/tool/retrieval telemetry. |
| NFR-008 | Portability | Local Docker Compose and documented cloud mapping. |
| NFR-009 | Privacy | Synthetic/de-identified demo data, log redaction, controlled document access and retention hooks. |
| NFR-010 | AI Safety | Prompt-injection defenses, tool allow-lists, structured output validation and human approval gates. |

## Initial engineering SLO targets for the portfolio demo

These are engineering targets, not production commitments:
- API health/read endpoints: p95 < 300 ms locally under normal demo load.
- Standard CRUD endpoints: p95 < 800 ms locally.
- Async analyze request acceptance: p95 < 1 s.
- No unbounded synchronous LLM/document processing in request threads.
- Tool schema-valid rate: >= 99% in controlled tests.
- Policy citation resolution: >= 95% on the evaluation set.
- Critical extraction field accuracy target: >= 95% on labeled synthetic fixtures.
- Policy retrieval recall@k target: >= 90% on the evaluation set.

## Reliability rules

- Every async job has a stable job ID.
- Retriable operations use idempotency keys or deduplication keys.
- Tool timeouts are bounded.
- Partial agent failures are persisted and visible.
- Database writes use transactions at service boundaries.
- Final human review is never silently replaced by an automated status mutation.
