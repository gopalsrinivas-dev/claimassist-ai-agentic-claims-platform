# 21 — Exact API Schema Contracts

## Schema conventions

- External IDs: UUID.
- Money: decimal serialized as string where precision matters.
- Dates: ISO `YYYY-MM-DD`.
- Datetimes: ISO-8601 UTC.
- Request models reject unknown fields for sensitive write endpoints.
- Enums are explicit.
- All success/error responses include a correlation ID either in body or response header.

## ClaimCreateRequest

```json
{
  "member_id": "uuid",
  "provider_id": "uuid",
  "policy_version_id": "uuid",
  "service_start_date": "2026-09-01",
  "service_end_date": "2026-09-03",
  "claimed_amount": "125000.00",
  "currency": "INR"
}
```

Validation:
- service_end_date >= service_start_date;
- claimed_amount > 0;
- referenced entities exist and are accessible;
- policy version association is validated server-side.

## ClaimResponse

```json
{
  "id": "uuid",
  "claim_number": "CLM-...",
  "status": "DRAFT",
  "claim_version": 1,
  "member_id": "uuid",
  "provider_id": "uuid",
  "policy_version_id": "uuid",
  "service_start_date": "2026-09-01",
  "service_end_date": "2026-09-03",
  "claimed_amount": "125000.00",
  "currency": "INR",
  "created_at": "...",
  "updated_at": "..."
}
```

## ClaimUpdateRequest

Allowed while editable:
```json
{
  "expected_claim_version": 1,
  "service_start_date": "2026-09-01",
  "service_end_date": "2026-09-03",
  "claimed_amount": "125000.00"
}
```

The service controls editable fields by state/role.

## SubmitClaimRequest

```json
{
  "expected_claim_version": 2
}
```

## AnalyzeClaimRequest

```json
{
  "expected_claim_version": 3,
  "analysis_profile": "default-v1"
}
```

## AnalyzeClaimResponse

```json
{
  "run_id": "uuid",
  "claim_id": "uuid",
  "claim_version": 3,
  "status": "QUEUED"
}
```

## DocumentUploadResponse

```json
{
  "document_id": "uuid",
  "claim_id": "uuid",
  "document_type": "HOSPITAL_BILL",
  "sha256": "...",
  "size_bytes": 12345,
  "processing_status": "UPLOADED"
}
```

## HumanReviewRequest

```json
{
  "expected_claim_version": 3,
  "recommendation_id": "uuid",
  "decision": "APPROVED",
  "override_reason_code": null,
  "comments": "Evidence reviewed."
}
```

Allowed decisions:
- APPROVED
- REJECTED
- REQUEST_INFO
- ESCALATED

Override reason is mandatory when configured business policy requires it.

## RecommendationResponse

```json
{
  "recommendation_id": "uuid",
  "category": "NEED_INFO",
  "reasons": [],
  "missing_documents": [],
  "eligibility": {},
  "coverage_findings": [],
  "risk_signals": [],
  "citations": [],
  "requires_human_review": true,
  "claim_version": 3,
  "policy_version_id": "uuid",
  "model": {
    "provider": "openai",
    "model_name": "...",
    "prompt_version": "v1"
  }
}
```

## ErrorResponse

```json
{
  "error": {
    "code": "CLAIM_VERSION_CONFLICT",
    "message": "The claim changed since this request was prepared.",
    "details": {},
    "correlation_id": "uuid"
  }
}
```

## Pagination

List response:
```json
{
  "items": [],
  "page": 1,
  "page_size": 25,
  "total": 0
}
```

Initial limit:
- default page_size: 25
- max page_size: 100
