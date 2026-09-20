# 15 — DevOps and Deployment Design

## Local Docker Compose

Services:
- `frontend`
- `api`
- `worker`
- `postgres` with pgvector
- `redis`
- optional local S3-compatible object store
- optional observability collector

## AWS reference mapping

| Capability | AWS mapping |
|---|---|
| Frontend | CloudFront + suitable Next.js hosting pattern |
| API/Workers | ECS/Fargate behind ALB where needed |
| Database | RDS PostgreSQL with pgvector support validated for target environment |
| Object storage | S3 |
| Redis / Celery broker | ElastiCache Redis for the frozen baseline; alternatives require an ADR |
| Secrets | Secrets Manager / Parameter Store |
| Logs/Metrics | CloudWatch + OpenTelemetry path |
| Registry | ECR |
| LLM | OpenAI via provider abstraction initially; Bedrock-compatible adapter may be added through the same interface |

## CI pipeline

```text
PR
 -> lint
 -> format check
 -> type check
 -> unit tests
 -> integration tests
 -> security/dependency checks
 -> build images
 -> image scan
 -> deploy non-prod
 -> smoke tests
 -> controlled promotion
```

## Deployment requirements

- immutable image tags;
- migration step controlled separately from app startup;
- health/readiness endpoints;
- rollback procedure;
- secret injection at runtime;
- no credentials baked into image;
- environment-specific config;
- smoke test of DB, queue, storage and model integration.

## Backup/recovery for portfolio architecture

Document:
- DB backup/restore assumption;
- object versioning/retention assumption;
- what is reproducible from source (policy embeddings);
- what is authoritative and must be backed up (claim/review/audit records).
