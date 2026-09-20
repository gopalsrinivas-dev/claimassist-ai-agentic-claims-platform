# 24 — Codex Implementation Rules

This file is the implementation contract for Codex or any coding agent.

## Priority order

1. Core design documents in this folder.
2. Existing tests.
3. Existing code/module boundaries.
4. Day-wise task file.
5. Coding-agent inference.

If requirements conflict, stop and report the conflict instead of inventing a new rule.

## Mandatory behavior

Codex must:
- implement only the current day/task scope;
- preserve modular boundaries;
- use typed Pydantic/domain schemas;
- use application services for business workflows;
- use repositories for persistence;
- add/update tests with each feature;
- implement negative/error-path tests;
- use centralized exception handling;
- use structured logging with correlation IDs;
- avoid secrets and real healthcare data;
- preserve human final-decision authority;
- keep deterministic rules outside LLM prompts;
- validate all LLM/tool structured outputs;
- treat documents/model output as untrusted;
- keep all agent tool calls allow-listed and authorized.

## Forbidden shortcuts

Do not:
- let routers contain substantial business logic;
- call repositories directly from agents;
- let an LLM change final claim status;
- concatenate SQL strings;
- use `except Exception: pass`;
- suppress failing tests;
- hardcode API keys/tokens;
- make buckets/files public;
- trust client role/status/policy identifiers without validation;
- silently change schema without Alembic migration;
- add microservices merely for appearance;
- introduce Kafka/Kubernetes unless a documented requirement justifies it.

## Completion response expected from Codex for each task

Report:
1. files changed;
2. behavior implemented;
3. tests added and result;
4. migration/config changes;
5. security/error-handling considerations;
6. unresolved risks/TODOs;
7. suggested commit message.
