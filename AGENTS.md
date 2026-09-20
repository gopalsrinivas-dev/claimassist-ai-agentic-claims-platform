# ClaimAssist AI — Coding Agent Instructions

Read `docs/00-documentation-map.md`, `docs/18-implementation-readiness-checklist.md`,
`docs/24-codex-implementation-rules.md`, and the current day task before editing code.

Key invariants:
- human reviewer owns final consequential claim decisions;
- deterministic rules are not replaced by LLM reasoning;
- agents use typed, allow-listed, server-authorized tools;
- uploaded documents and model output are untrusted;
- all important writes are validated, transactional and audited;
- expected errors use explicit application exceptions and centralized handlers;
- no swallowed exceptions, secrets, real patient data or fabricated citations;
- every feature includes success + negative/error tests.

Implement one scoped task at a time and report tests/security/error-handling implications.
