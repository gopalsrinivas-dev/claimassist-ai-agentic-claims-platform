# 23 — Testing Strategy and Quality Gates

## Test pyramid

### Unit
- validators;
- state transitions;
- deterministic rules;
- money/date calculations;
- authorization helpers;
- parsers/chunking;
- tool input/output validation.

### Repository/database
- constraints;
- transaction behavior;
- indexes/queries;
- optimistic version conflicts;
- migrations upgrade/downgrade where safe.

### API integration
- success;
- 401/403;
- 404;
- 409;
- 422;
- idempotency;
- pagination;
- upload validation;
- global exception mapping.

### RAG
- policy-version filter;
- recall@k;
- citation resolution;
- insufficient-evidence behavior;
- cross-version leakage negative tests.

### Agent
Use mocked deterministic tools first:
- graph routing;
- state updates;
- invalid schema;
- tool timeout;
- unauthorized tool attempt;
- partial failure/manual-review path.

### Security
- access-control matrix;
- prompt injection;
- malicious/oversized file metadata;
- SQL-injection-like inputs;
- XSS-safe rendering expectations;
- SSRF prevention if URL capability exists;
- log-redaction checks.

### End-to-end
Synthetic reviewer journey:
create -> upload -> process -> analyze -> inspect evidence -> human review -> audit.

## Coverage policy

Do not chase a percentage alone.
Critical business/security modules require branch/error-path tests.

Initial target:
- overall backend line coverage >= 80%;
- rules/state/auth/tool authorization modules >= 90%;
- no untested final-decision state transition.

## Static quality gate

Before merge:
- formatter clean;
- lint clean;
- type-check clean;
- tests pass;
- dependency/security checks reviewed;
- migration check passes;
- no secret detected.

## AI evaluation gate

A model/prompt/retrieval change is blocked if it:
- introduces policy-version leakage;
- creates invalid/fabricated citations;
- raises unsupported recommendation rate beyond threshold;
- allows unauthorized tool execution;
- breaks required structured schema.

## Pull request definition of done

- requirement linked;
- tests added;
- error paths tested;
- authorization checked;
- telemetry added;
- docs updated;
- no sensitive fixtures;
- reviewer can reproduce locally.
