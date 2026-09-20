# 05 — Claim Lifecycle and State Machine

## Canonical claim states

```text
DRAFT
  -> SUBMITTED
  -> PROCESSING
  -> NEED_INFO
     OR READY_FOR_REVIEW
  -> APPROVED | REJECTED | ESCALATED
```

Reprocessing is allowed after authorized data/document changes.

## State ownership

- LLMs/agents may propose recommendation categories.
- Backend application services validate transitions.
- Human reviewers execute final consequential review actions.
- A tool cannot bypass service-layer transition validation.

## Transition table

| From | To | Initiator | Guard |
|---|---|---|---|
| DRAFT | SUBMITTED | Claims Processor | Mandatory claim header fields present |
| SUBMITTED | PROCESSING | System | Processing job created idempotently |
| PROCESSING | NEED_INFO | System/Reviewer | Missing required information/documents |
| PROCESSING | READY_FOR_REVIEW | System | Analysis package available or safe manual package prepared |
| NEED_INFO | PROCESSING | System | New information received and re-analysis requested |
| READY_FOR_REVIEW | APPROVED | Reviewer | Authorized + review form complete |
| READY_FOR_REVIEW | REJECTED | Reviewer | Authorized + reason code/evidence recorded |
| READY_FOR_REVIEW | ESCALATED | Reviewer/Supervisor | Escalation reason recorded |
| Any reviewable | PROCESSING | Authorized reprocess action | Claim/document version changed |

## Invariants

- Final state changes are transactional and audited.
- Recommendation and final disposition are separate fields.
- Every transition stores actor, timestamp, reason and correlation ID.
- Stale reviewer pages must not overwrite newer claim versions; use optimistic version checks.
