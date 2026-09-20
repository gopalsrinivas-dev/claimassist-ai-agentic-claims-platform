# 02 — Product Requirements

## Functional requirements

| ID | Requirement |
|---|---|
| FR-001 | Authenticate users and enforce RBAC. |
| FR-002 | Create a claim and associate member, policy and provider context. |
| FR-003 | Upload, validate, store and classify claim documents. |
| FR-004 | Extract structured claim fields with source provenance. |
| FR-005 | Track document completeness and identify missing required artifacts. |
| FR-006 | Validate policy status, member eligibility and key dates through deterministic tools. |
| FR-007 | Index versioned policy documents and retrieve relevant clauses with citations. |
| FR-008 | Evaluate coverage rules including waiting periods and monetary limits. |
| FR-009 | Identify duplicate/inconsistent claim indicators using structured history. |
| FR-010 | Run agentic analysis using only approved tools. |
| FR-011 | Return one structured recommendation category: APPROVE_REVIEW, REJECT_REVIEW, NEED_INFO, ESCALATE or MANUAL_REVIEW. |
| FR-012 | Show evidence and source references for each major AI assertion. |
| FR-013 | Allow authorized reviewers to accept, override, request information or escalate. |
| FR-014 | Require reviewer reason codes/comments for overrides. |
| FR-015 | Maintain append-only/immutable-style audit events for important actions. |
| FR-016 | Support re-analysis after claim data or documents change. |
| FR-017 | Provide dashboard queues, filters and status views. |
| FR-018 | Capture evaluation and observability telemetry for each agent run. |
| FR-019 | Support model/provider abstraction and controlled fallback. |
| FR-020 | Expose versioned REST APIs for frontend and integrations. |

## Acceptance principles

- Any consequential write must identify the authenticated actor.
- Any AI recommendation must be traceable to evidence/tool results.
- Any failed critical dependency must result in explicit `UNKNOWN`, `MANUAL_REVIEW`, safe retry or failure — never fabricated success.
- A policy clause citation must resolve to the exact indexed policy version.
- A reviewer must be able to distinguish extracted facts, deterministic rule outputs, retrieved evidence, AI synthesis and final human decision.
