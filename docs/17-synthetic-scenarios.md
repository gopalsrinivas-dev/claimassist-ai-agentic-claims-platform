# 17 — Initial Synthetic Scenario Matrix

Use only synthetic/de-identified data.

| Scenario | Expected behavior |
|---|---|
| Complete clearly covered claim | Deterministic checks pass; evidence-backed APPROVE_REVIEW recommendation |
| Missing implant invoice | NEED_INFO with exact missing document |
| Policy inactive on service date | Eligibility failure surfaced; human/manual path |
| Waiting period not met | Rule result includes date calculation + cited policy clause |
| Possible duplicate invoice | Risk indicator + reviewer escalation; no fraud accusation |
| Conflicting dates | Inconsistency flag + manual review |
| Prompt injection inside PDF | Ignored as instruction; treated as untrusted document text |
| Wrong policy version available | Metadata filter prevents cross-version evidence |
| Retriever has insufficient evidence | MANUAL_REVIEW/insufficient evidence; no guessing |
| Tool timeout | bounded retry or safe failure; no fabricated result |
| LLM returns invalid schema | schema repair/bounded retry then safe failure |
| Duplicate analyze request | one effective analysis run due to idempotency |
| Two reviewers submit simultaneously | one succeeds; stale one receives 409 |
| Worker crashes mid-run | lease expires; idempotent retry resumes safely |
| New document after recommendation | claim version increments; old recommendation marked stale |
