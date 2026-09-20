# 25 — Environment and Technology Contract

## Frozen MVP choices

- Backend: FastAPI + Pydantic + SQLAlchemy 2 + Alembic
- Primary DB: PostgreSQL + pgvector
- Queue/worker: **Celery + Redis**
- Agent orchestration: LangGraph
- Primary LLM for initial implementation: **OpenAI through provider abstraction**
- Alternate future path: Bedrock-compatible adapter
- Frontend: Next.js + TypeScript + Tailwind
- Object storage:
  - local simplest path: filesystem adapter for tests;
  - Docker integration profile: **S3-compatible MinIO adapter**;
  - cloud: S3.
- Containers: Docker / Docker Compose
- CI: GitHub Actions
- Cloud reference: AWS

## Required environment variables

```env
APP_NAME=ClaimAssist AI
APP_ENV=development
DEBUG=false
API_V1_PREFIX=/api/v1

DATABASE_URL=
REDIS_URL=

JWT_SECRET_KEY=
JWT_ALGORITHM=
ACCESS_TOKEN_EXPIRE_MINUTES=

LLM_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=
EMBEDDING_MODEL=

OBJECT_STORAGE_PROVIDER=local
LOCAL_STORAGE_PATH=
S3_ENDPOINT_URL=
S3_REGION=
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=

MAX_UPLOAD_BYTES=
ALLOWED_UPLOAD_MIME_TYPES=

CORS_ALLOWED_ORIGINS=
LOG_LEVEL=
OTEL_EXPORTER_OTLP_ENDPOINT=
```

## Rules

- `.env` is ignored by Git.
- `.env.example` contains empty/safe example values only.
- production secrets come from managed secret storage.
- startup validates required settings for the selected environment/provider.
