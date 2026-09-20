# 04 — Actors, Use Cases and Business Workflows

## Actors

### Claims Processor
- Create/edit draft claims.
- Associate member, policy and provider.
- Upload supporting documents.
- Submit claims.
- Respond to `NEED_INFO`.

### Claims Reviewer
- Inspect claim facts, policy evidence, rule results and AI synthesis.
- Accept/override recommendation.
- Request information.
- Approve/reject/escalate according to authorization.

### Supervisor
- Inspect work queues and aging.
- Perform controlled quality review and overrides.
- Review escalations and reporting.

### Administrator
- Manage users/roles.
- Manage reference/configuration data.
- Manage policy ingestion configuration and integrations.

### Auditor
- Read-only access to authorized audit/evidence views.

## Core use cases

1. Create draft claim.
2. Upload one or more claim documents.
3. Submit claim for processing.
4. Extract facts with provenance.
5. Evaluate eligibility.
6. Retrieve correct policy-version evidence.
7. Evaluate coverage and financial/date rules.
8. Generate explainable risk indicators.
9. Run agentic synthesis.
10. Present reviewer package.
11. Human reviewer selects final next action.
12. Reprocess after new documents or corrected data.
13. Audit full lifecycle.

## Alternate/error flows

- Required document missing -> `NEED_INFO`.
- Policy inactive -> deterministic failure result -> human review path.
- No sufficient RAG evidence -> `MANUAL_REVIEW`, not guessed answer.
- Tool timeout -> bounded retry -> explicit failure state if exhausted.
- Conflicting extracted values -> document inconsistency flag.
- Prompt injection in document -> store as untrusted content; do not treat as system instruction.
- Wrong policy version -> retrieval metadata filter blocks cross-version evidence.
