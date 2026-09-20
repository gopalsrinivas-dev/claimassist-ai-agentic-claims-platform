# ClaimAssist AI — Documentation Map

## Purpose

This folder is the implementation source-of-truth for the ClaimAssist AI project.
The master blueprint remains the product/design baseline; these Markdown files convert that
baseline into implementation-ready specifications for Codex and normal development.

## Source-of-truth order

1. `01-project-scope-and-principles.md`
2. `02-product-requirements.md`
3. `03-system-requirements.md`
4. `04-use-cases-and-workflows.md`
5. `05-claim-state-machine.md`
6. `06-system-architecture.md`
7. `07-system-design-deep-dive.md`
8. `08-data-model-and-erd.md`
9. `09-api-contracts.md`
10. `10-agentic-ai-design.md`
11. `11-rag-document-intelligence.md`
12. `12-tool-contracts-and-permissions.md`
13. `13-security-threat-model.md`
14. `14-evaluation-observability.md`
15. `15-devops-deployment.md`
16. `16-architecture-decision-records.md`
17. `17-synthetic-scenarios.md`
18. `18-implementation-readiness-checklist.md`
19. Day-wise execution files: `day-01-...md` through `day-45-...md`

## Conflict rule

If a day-wise checklist conflicts with a core design specification, the core design specification wins.
If two core design files conflict, stop implementation and resolve the conflict through an ADR before coding.

## Design principles

- Human reviewer retains final authority for consequential claim decisions.
- LLM output is advisory, structured, validated and evidence-backed.
- Deterministic business rules remain outside the LLM.
- All tools enforce authorization server-side.
- Uploaded documents are untrusted input.
- Policy evidence is version-scoped and citation-preserving.
- Auditability is a first-class requirement.
- Use synthetic/de-identified data only for portfolio development.
- Start as a modular monolith plus workers; split services only when evidence justifies it.
- Every long-running/retriable operation must be idempotent.


## Engineering implementation standards

19. `19-error-handling-and-reliability-standard.md`
20. `20-secure-coding-standard.md`
21. `21-exact-api-schema-contracts.md`
22. `22-database-field-dictionary.md`
23. `23-testing-and-quality-gates.md`
24. `24-codex-implementation-rules.md`
25. `25-environment-and-technology-contract.md`
26. `26-rbac-resource-matrix.md`
27. `fixtures/synthetic-policy-v1.md`
28. `fixtures/synthetic-policy-v2.md`

## Final repository audit

- `00-repository-final-audit.md` — final consistency/cleanliness/readiness verification.
