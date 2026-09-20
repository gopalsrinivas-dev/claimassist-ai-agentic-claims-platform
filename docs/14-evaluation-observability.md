# 14 — Evaluation, Observability and LLMOps

## Correlation model

One `correlation_id` follows:
API request -> job -> worker -> extraction -> rules -> retrieval -> agent nodes -> tools -> recommendation.

## Telemetry

### API
- latency
- status/error codes
- DB query timings
- actor/route (no sensitive payload logs)

### Queue/workers
- queue depth
- oldest job age
- processing latency
- retry/dead-letter count
- worker concurrency

### RAG
- query hash
- policy version
- retrieved chunk IDs
- scores
- rerank outputs
- citation resolution

### LLM/agents
- provider/model
- prompt/graph version
- input/output token count
- latency
- schema-valid rate
- tool calls
- retry/error count
- estimated cost

## Offline evaluation dataset

Target:
- 100+ synthetic claims over time;
- start with 10–15 representative scenarios before implementation;
- labeled critical fields;
- expected deterministic rule results;
- expected policy clause IDs;
- expected safe recommendation category;
- prompt-injection/adversarial cases.

## Metrics

- extraction field accuracy
- retrieval recall@k
- precision@k where useful
- citation correctness/resolution
- rules regression pass rate
- invalid tool-call rate
- groundedness/unsupported-claim rate
- schema-valid rate
- reviewer override/agreement tracking
- latency, throughput, token/cost per claim

## Regression gate

A prompt/model/retriever change must not be merged if it:
- introduces cross-policy leakage;
- increases fabricated/invalid citations;
- bypasses deterministic failed rules;
- permits unauthorized tool usage;
- breaks schema validity beyond agreed threshold.
