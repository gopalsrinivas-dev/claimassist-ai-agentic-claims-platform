# 13 — Security and Threat Model

## Assets

- claim/member/provider data
- claim/policy documents
- credentials/tokens
- policy evidence
- reviewer decisions
- audit trail
- model/tool configuration
- object-storage keys
- evaluation datasets

## Threat boundaries

- browser -> API
- uploaded file -> parser
- retrieved document text -> LLM
- LLM -> tool layer
- API/worker -> database/object storage
- platform -> external model provider

## Threat register

| Threat | Example | Mitigation |
|---|---|---|
| Broken access control | Processor reads another team claim | RBAC + scope checks + negative tests |
| Prompt injection | PDF asks model to approve claim | Treat docs as untrusted data; allow-listed tools; structured prompts |
| Tool escalation | Model calls unauthorized write | Server-side auth; deny-by-default; no final-decision tool |
| Cross-policy leakage | Wrong version clause used | Mandatory policy_version filters + eval tests |
| Malicious upload | disguised executable/oversized file | MIME/signature/size checks; malware-scan hook; isolated parsing |
| Secret leakage | key in repo/log | env/secret manager; redaction; CI secret scan |
| PII leakage | raw member data in logs | field redaction + structured logging policy |
| Replay/duplicate | repeated analyze/create request | idempotency keys + dedup records |
| Stale write | two reviewers submit | optimistic version + 409 |
| Dependency outage | LLM/store unavailable | timeouts, circuit/backoff, safe manual path |
| Citation fabrication | model invents clause | citation resolver validation |
| Supply-chain | vulnerable package/image | pinned dependencies, scans, minimal images |

## Authentication/session baseline

- secure password hashing for demo local identities;
- short-lived access token/session;
- HTTPS in deployed environments;
- refresh/session strategy documented before productionization;
- admin actions audited.

## Authorization

Enforce at:
1. route dependency;
2. application service;
3. tool wrapper for model-initiated calls.

Never rely on frontend hiding buttons.

## File security

- size limit;
- extension + MIME/signature validation;
- randomized object key;
- checksum;
- malware-scan hook;
- no direct public bucket;
- time-limited authorized access.

## AI guardrails

- system instructions separated from document content;
- tool allow-list;
- typed tool schemas;
- output schema validation;
- citation resolution check;
- maximum steps/tool calls;
- model/provider timeout;
- human approval gate.
