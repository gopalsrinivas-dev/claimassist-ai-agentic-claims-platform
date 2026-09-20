# 09 — API Contracts and Integration Rules

## API conventions

Base path: `/api/v1`

- JSON for normal requests/responses.
- Multipart only for uploads.
- Consistent error envelope.
- Correlation ID returned in every response.
- Explicit authorization at router/service boundary.
- Cursor or page-based pagination documented consistently.
- OpenAPI is generated but does not replace written business contracts.

## Core endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/login` | Authenticate |
| GET | `/auth/me` | Current actor/permissions |
| POST | `/claims` | Create claim |
| GET | `/claims` | List/filter claims |
| GET | `/claims/{claim_id}` | Claim details |
| PATCH | `/claims/{claim_id}` | Update allowed fields |
| POST | `/claims/{claim_id}/submit` | Submit draft |
| POST | `/claims/{claim_id}/documents` | Upload document |
| GET | `/claims/{claim_id}/documents` | List documents |
| POST | `/claims/{claim_id}/analyze` | Idempotently queue analysis |
| GET | `/analysis/{run_id}` | Run status/result |
| GET | `/claims/{claim_id}/evidence` | Evidence/tool/rule package |
| POST | `/claims/{claim_id}/reviews` | Human review action |
| GET | `/claims/{claim_id}/audit` | Authorized audit timeline |
| POST | `/policies/{policy_id}/versions/{version_id}/index` | Queue policy indexing |
| GET | `/dashboard/summary` | Queue metrics |

## Error envelope

```json
{
  "error": {
    "code": "CLAIM_VERSION_CONFLICT",
    "message": "The claim changed since this page was loaded.",
    "details": {},
    "correlation_id": "..."
  }
}
```

## Important status codes

- `200` read/update success
- `201` created
- `202` async work accepted
- `400` malformed request
- `401` unauthenticated
- `403` forbidden
- `404` resource not found or deliberately hidden
- `409` version/idempotency/state conflict
- `413` upload too large
- `422` schema/business validation details
- `429` rate limited
- `503` dependency/capacity unavailable

## Analysis request contract

Request:
```json
{
  "analysis_profile": "default-v1",
  "expected_claim_version": 3
}
```

Response:
```json
{
  "run_id": "uuid",
  "claim_id": "uuid",
  "claim_version": 3,
  "status": "QUEUED"
}
```

## Human review contract

```json
{
  "expected_claim_version": 3,
  "decision": "APPROVED",
  "recommendation_id": "uuid",
  "override_reason_code": null,
  "comments": "Evidence reviewed."
}
```

If decision materially disagrees with the AI recommendation, configured override reason is required.

## Idempotency

`POST /claims`, upload-finalization and `/analyze` accept an `Idempotency-Key` where retry duplication is possible.

## Security contract

Client-supplied:
- role;
- ownership;
- policy version;
- claim status;
- tool authorization

must never be trusted without server-side validation.
