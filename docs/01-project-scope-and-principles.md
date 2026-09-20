# 01 — Project Scope and Engineering Principles

## Product

ClaimAssist AI is a production-oriented, human-in-the-loop health-insurance claims review platform.

It assists claims teams with:
- claim intake;
- document ingestion and extraction;
- eligibility and deterministic rules;
- policy retrieval with citations;
- coverage analysis;
- risk/anomaly indicators;
- structured agentic synthesis;
- reviewer decisions and overrides;
- audit and evaluation.

## Primary users

- **Claims Processor** — create/update claims, upload documents, respond to missing-information requests.
- **Claims Reviewer** — inspect evidence and AI recommendations; approve/reject/request information/escalate.
- **Supervisor** — queue oversight, quality review, controlled overrides, reporting.
- **Administrator** — users, roles, reference data and integrations.
- **Auditor** — read-only inspection of evidence, tool calls, decisions and changes.

## Explicit non-goals

- Autonomous final claims adjudication.
- Medical diagnosis or treatment recommendation.
- Use of real patient data in portfolio/demo environments.
- LLM-based replacement for deterministic eligibility/financial/date calculations.
- Unbounded agent access to databases, files, networks or mutable tools.
- Premature microservices.

## High-level workflow

```text
Claim Submission
  -> Document Processing
  -> Deterministic Eligibility
  -> Policy RAG
  -> Coverage Rules
  -> Risk Checks
  -> Agent Synthesis
  -> Human Review
  -> Final Decision
  -> Audit
```

## Claim recommendation categories

AI may propose only:
- `APPROVE_REVIEW`
- `REJECT_REVIEW`
- `NEED_INFO`
- `ESCALATE`
- `MANUAL_REVIEW`

The recommendation is not the final claim disposition.

## Technology baseline

- Python 3.12+
- FastAPI + Pydantic
- SQLAlchemy 2 + Alembic
- PostgreSQL + pgvector
- LangGraph
- Provider abstraction for OpenAI / Bedrock-compatible LLMs
- Celery + Redis worker model
- Next.js + TypeScript + Tailwind
- S3-compatible object storage
- Docker / Docker Compose
- GitHub Actions
- AWS reference deployment

## Quality bar

A feature is not complete until:
1. authorization is explicit;
2. typed schemas exist;
3. tests cover success and negative paths;
4. audit/observability implications are addressed;
5. secrets/PII are not leaked;
6. documentation is updated;
7. AI behavior changes have evaluation fixtures.
