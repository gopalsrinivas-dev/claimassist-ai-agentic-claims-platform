# 16 — Architecture Decision Records (ADR Index)

Create one ADR per decision with:
Context -> Decision -> Alternatives -> Consequences -> Status.

## ADR-001 — Modular monolith first
Decision: FastAPI modular monolith plus independent workers.
Reason: transactional correctness, simpler development and strong boundaries without premature distributed complexity.

## ADR-002 — PostgreSQL + pgvector
Decision: relational + vector data in PostgreSQL initially.
Reason: policy-version metadata and vector evidence remain close; simpler operations.

## ADR-003 — LangGraph
Decision: explicit stateful graph for agent orchestration.
Reason: conditional routing, inspectable state and HITL-friendly design.

## ADR-004 — Human final authority
Decision: agents cannot finalize claim approval/rejection.
Reason: consequential workflow requires accountable reviewer control.

## ADR-005 — Deterministic rules outside LLM
Decision: dates, limits, eligibility and completeness logic live in testable services/tools.
Reason: reproducibility and regression testing.

## ADR-006 — Async long-running processing
Decision: document/embedding/agent work runs via queue/workers.
Reason: request latency, retries, scaling and recovery.

## ADR-007 — Provider abstraction
Decision: LLM client interface isolates provider-specific implementation.
Reason: avoid model/provider lock-in and support OpenAI/Bedrock-compatible paths.

## ADR-008 — Policy-version-scoped RAG
Decision: vector retrieval requires policy version/effective-date filtering.
Reason: prevent evidence leakage across policy versions.
