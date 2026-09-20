# 20 — Secure Coding Standard

## Baseline

Security is enforced in backend/application/tool layers, not by UI conventions or LLM instructions.

## Authentication and authorization

- Passwords use a modern password-hashing implementation.
- Tokens/sessions are short-lived and validated server-side.
- Every protected endpoint declares authentication.
- Resource scope is checked in application services.
- Tool wrappers independently re-check actor/service authorization.
- Admin/audit/reviewer privileges are deny-by-default.

## Injection defenses

### SQL injection
- SQLAlchemy parameterized expressions only.
- No string concatenation for dynamic SQL.
- Any unavoidable raw SQL uses bound parameters and code review.

### Prompt injection
- Uploaded/retrieved content is untrusted data.
- System/developer policy is separate from evidence text.
- Documents cannot grant permissions or create tools.
- Retrieved text cannot directly mutate claim state.
- Tool allow-list and server-side authorization remain authoritative.

### Command injection
- Avoid shell execution for document handling.
- If a subprocess is required, pass argument arrays, not interpolated shell strings.
- Use allow-listed executables/options and strict timeouts.

## Web security

### CORS
- Explicit allow-list by environment.
- Never use wildcard origins with credentialed requests.
- Restrict methods/headers to required values.

### CSRF
If cookie-based authentication is used:
- SameSite cookie policy;
- CSRF token/double-submit or equivalent framework protection for state-changing requests;
- Origin/Referer validation where appropriate.

If Authorization-header bearer tokens are used, document why classic CSRF risk differs and still protect against XSS/token theft.

### XSS
- React/Next.js default escaping remains enabled.
- Do not use `dangerouslySetInnerHTML` for document/model content.
- If rendered rich text is required, sanitize with an allow-list.
- Treat LLM output as untrusted display content.

### SSRF
- Do not allow agents/users to fetch arbitrary URLs.
- Outbound integrations use configured allow-listed hosts.
- Block internal/link-local/metadata addresses if URL-fetch capability is introduced.

## File upload security

- Server-side max size.
- Extension + MIME + magic/signature validation.
- Randomized object key.
- SHA-256 checksum.
- Malware-scanning integration hook.
- Store outside executable/web-root paths.
- No public buckets.
- Time-limited authorized download.
- Parser isolation/resource limits for untrusted files.

## Secrets

- `.env` only for local development and excluded from Git.
- `.env.example` contains names, never values.
- Cloud uses secret manager / parameter store.
- CI uses secret store.
- Secret scans run in CI.
- Rotate a secret immediately if committed.

## Data protection

- Use synthetic/de-identified portfolio data.
- TLS in deployed environments.
- Encryption at rest through managed DB/object-storage configuration.
- Minimize PHI/PII fields.
- Redact logs.
- Define retention/deletion hooks.

## API protections

- Request body limits.
- Pagination limits.
- Rate limiting for auth/upload/analyze endpoints.
- Timeouts for expensive requests.
- Strict Pydantic schemas; reject unexpected fields where appropriate.
- Stable error responses without internal exception leakage.

## Dependency/supply-chain security

- Lock/pin dependencies.
- Automated dependency vulnerability checks.
- Container image scan.
- Minimal runtime image.
- Non-root container user where feasible.
- No build tools/secrets in final runtime image.
- Review transitive dependencies for document parsers/AI clients.

## Security test gate

Required negative tests:
- unauthorized access;
- cross-user/cross-scope access;
- stale token;
- SQL-injection-like payloads;
- oversized/invalid upload;
- prompt injection document;
- fabricated citation;
- unauthorized tool call;
- stale claim-version write;
- rate-limit path;
- sensitive-log redaction.
