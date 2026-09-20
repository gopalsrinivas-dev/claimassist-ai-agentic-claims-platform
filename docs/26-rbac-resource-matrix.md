# 26 — RBAC and Resource-Scope Matrix

`Scoped` means the actor can access only claims/resources assigned to or permitted for their business scope.

| Action | Processor | Reviewer | Supervisor | Admin | Auditor |
|---|---:|---:|---:|---:|---:|
| Create claim | Yes | No | No | No | No |
| Edit DRAFT/NEED_INFO claim | Scoped | No | No | No | No |
| Upload claim document | Scoped | Scoped if workflow permits | Yes | No | No |
| Submit claim | Scoped | No | No | No | No |
| View claim | Scoped | Assigned/Scoped | Cross-team authorized | Config/support only | Read-only authorized |
| Start/restart analysis | Scoped | Assigned | Yes | No | No |
| View AI evidence | Scoped | Assigned | Yes | Config/support only | Read-only |
| Submit final review | No | Assigned | Yes | No | No |
| Override recommendation | No | Yes with reason | Yes with reason | No | No |
| Escalation disposition | No | Scoped | Yes | No | No |
| Manage users/roles | No | No | No | Yes | No |
| Manage policy/reference data | No | No | Controlled | Yes | Read-only |
| View audit | Own/scoped events as needed | Scoped | Yes | Privileged | Read-only authorized |
| Mutate audit | Never | Never | Never | Never | Never |

## Enforcement

- Frontend controls are convenience only.
- API routes authenticate.
- Application services authorize resource scope.
- Tool wrappers re-authorize.
- Repository methods accept already-authorized scope/filter inputs; they do not infer role from untrusted request fields.
