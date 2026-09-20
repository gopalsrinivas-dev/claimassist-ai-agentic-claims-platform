# ClaimAssist AI — Agentic Healthcare Claims Platform

ClaimAssist AI is a production-oriented, human-in-the-loop health-insurance claims review platform designed as an AI engineering portfolio project.

It combines deterministic claims rules, document intelligence, policy RAG with citations, LangGraph-based agent orchestration, approved tool calling, reviewer workflows, auditability, evaluation, observability, and AWS-ready deployment design.

## Safety and product boundary

- AI produces evidence-backed recommendations; authorized human reviewers retain final consequential decision authority.
- Deterministic eligibility, date, monetary and policy rules are implemented outside LLM reasoning.
- Uploaded documents and model outputs are treated as untrusted input.
- Portfolio development uses synthetic/de-identified data only.

## Frozen MVP technology baseline

- Python 3.12+
- FastAPI + Pydantic
- SQLAlchemy 2 + Alembic
- PostgreSQL + pgvector
- Celery + Redis
- LangGraph
- OpenAI through a provider abstraction
- Next.js + TypeScript + Tailwind
- Local filesystem / MinIO / S3 storage adapters
- Docker / Docker Compose
- GitHub Actions
- AWS reference deployment

## Architecture strategy

The MVP begins as a modular monolith with independently scalable asynchronous workers. Domain boundaries are explicit so selected workloads can be extracted later if operational evidence justifies microservices.

## Documentation

Start with:

1. [`docs/00-documentation-map.md`](docs/00-documentation-map.md)
2. [`docs/00-final-codex-readiness-report.md`](docs/00-final-codex-readiness-report.md)
3. [`docs/18-implementation-readiness-checklist.md`](docs/18-implementation-readiness-checklist.md)
4. [`docs/24-codex-implementation-rules.md`](docs/24-codex-implementation-rules.md)
5. [`docs/day-11-backend-repository-skeleton.md`](docs/day-11-backend-repository-skeleton.md)

## Current status

**READY FOR CODEX IMPLEMENTATION — FOUNDATION PHASE**

Implementation begins at Day 11 and proceeds sequentially. Do not jump directly to RAG or agents before the backend, persistence, auth, claims, document, and deterministic rule foundations exist.
