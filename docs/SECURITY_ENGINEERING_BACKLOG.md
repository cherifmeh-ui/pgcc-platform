# PGCC Platform — Security & Engineering Backlog

Status: active engineering review. This is a static review backlog, not a security certification.

## Phase 0 — Build and integration stability

- [x] Declare PDF/DOCX extraction and pgvector dependencies.
- [x] Make AI enablement configurable in Compose (disabled by default).
- [x] Add backend dependency-install and Python compile CI.
- [x] Add backend security unit tests.
- [x] Add frontend production-build CI.
- [x] Validate JWT algorithm, HS256 secret length, and selected production configuration.
- [ ] Validate a clean Docker build and fresh database startup.
- [ ] Add API integration tests with PostgreSQL.
- [ ] Add Alembic migrations and stop relying on create_all for production schema evolution.
- [ ] Pin container image versions and separate development/production Compose profiles.

## Phase 1 — Authentication and access security

- [x] Expose MFA enrollment state at login.
- [x] Correct first-time MFA enrollment UI/API flow.
- [x] Allow recovery codes in MFA verification.
- [x] Consume recovery codes after successful use.
- [ ] Persist refresh-token sessions and implement rotation/reuse detection.
- [ ] Revoke sessions on password change, account disable, role change, and logout.
- [x] Require dedicated change-password token for forced password change; remove access-token fallback.
- [ ] Complete frontend forced-password-change flow and validate token issuance.
- [x] Apply account lockout policy to MFA verification failures.
- [ ] Add distributed rate limiting for login, MFA, enrollment, and refresh endpoints.
- [ ] Encrypt MFA secrets at rest and define key rotation.
- [ ] Add MFA reset/recovery process with audit and administrator approval.
- [ ] Verify anti-enumeration behavior and consistent login responses.
- [ ] Review all endpoint permissions; add authorization tests.
- [ ] Replace browser localStorage bearer-token persistence with safer session design (HttpOnly Secure SameSite cookie strategy, CSRF controls, short-lived access token).
- [x] Security logger no longer trusts client-supplied X-Forwarded-For by default; user-agent length bounded.
- [ ] Add security headers and trusted proxy configuration.

## Phase 2 — Core GRC

- [x] Risk API validates owner existence on create/update and bounds optional text fields.
- [x] Risk API now requires a documented treatment plan for statuses `En traitement`, `Traité` and `Accepté`; update transitions validate the combined status/plan.
- [x] Action-plan deletion is audit-logged.
- [ ] Risk register: scenario, threat, vulnerability, affected asset/process, owners, inherent and residual risk.
- [ ] Formal risk treatment (avoid/reduce/transfer/accept), rationale and approval.
- [ ] Residual-risk acceptance with approver, expiry, review date, compensating controls.
- [x] Audit log for action-plan create/update/delete and bounded input validation.
- [ ] Action-plan workflow with owner, evidence, validation, history and overdue tracking.
- [x] Audit log for document upload, deletion and successful indexing.
- [ ] Audit trail for every sensitive business mutation.

## Phase 3 — Asset and application inventory

- [ ] Extend inventory to business/technical owner, classification, data types, hosting, dependencies, exposure, lifecycle, support, security controls and continuity targets.
- [ ] Add asset relationships and risk/control links.
- [ ] Support inventory evidence and review dates.

## Phase 4 — ISO compliance and audit

- [ ] Verify ISO/IEC 27002:2022 control references and titles against an authoritative licensed source.
- [ ] Version control reference datasets; never mix editions.
- [x] Current compliance score is explicitly declarative; text-linked risks/actions are shown as 'À vérifier' rather than treated as implemented controls. UI badges/filters updated to reflect these states; fabricated last-update timestamps removed.
- [ ] Separate applicability, implementation status, maturity, verification and evidence.
- [ ] Implement statement of applicability and justified exclusions.
- [ ] Add audit findings, nonconformities, recommendations and linked actions.

## Phase 5 — Documents and evidence

- [x] Signature/format validation, bounded upload read, file size/page limits, PDF encryption rejection, DOCX ZIP structure/expansion checks and safe parsing.
- [ ] Malware scanning and isolated parsing.
- [ ] Hashing, versioning, classification, retention, ownership and approval.
- [ ] Prefer object storage for binaries; database stores metadata and references.
- [ ] Evidence links to risks, controls, audits and actions.
- [x] Validate uploaded file type/signature, bounds, filename and PDF/DOCX parsing containers.
- [x] RAG indexing now uses Ollama `/api/embed`, validates vector count/dimensions, and atomically replaces old chunks only after successful embedding generation.
- [ ] Add processing states, chunk metadata, citations, hybrid retrieval and permission/classification filters.

## Phase 6 — AI/RAG

- [ ] Fix missing/unfinished AI service functions and endpoint mismatches.
- [ ] Add hybrid retrieval and permission/classification filtering.
- [ ] Verify embedding model dimensions and pgvector compatibility.
- [ ] Include document/page/version citations and confidence/missing-context notes.
- [ ] AI suggestions must be reviewable and never silently change GRC records.
- [x] Treat risk data as untrusted in ISO suggestion prompt and validate/filter returned control references.
- [ ] Add prompt-injection handling for uploaded content and retrieved documents.

## Phase 7 — Observability and release

- [ ] Append-only audit design with retention and export.
- [ ] Monitoring, alerting, health checks and backup/restore tests.
- [ ] Unit, integration, frontend, migration and security tests.
- [ ] Dependency scanning, secret scanning and container scanning in CI.
- [ ] Release checklist, changelog, rollback and deployment documentation.

## Engineering rules

1. Work on feature branches; never push directly to main.
2. One coherent change per commit/PR.
3. Tests must accompany security-sensitive changes.
4. No production credentials in repository or logs.
5. Do not claim compliance or security certification based solely on automated checks.
6. Merge only after CI is green and the change is reviewed.


## Document and RAG security review (current prototype)

- Document RBAC is currently role-level: all users granted `documents:read` can see the full document listing. There is no document classification or per-document ACL, so sensitive-document segregation is not implemented.
- The advanced AI context endpoint retrieves up to three documents by PSSI type or substring match on document text. It is not vector-relevance retrieval and may include irrelevant PSSI documents. Retrieved text is framed as untrusted prompt data, but prompt injection cannot be fully prevented by prompting alone.
- RAG indexing is synchronous and resource-consuming. A hard limit of 2,000 chunks per document is now enforced before embedding generation. Long-running indexing should move to a queue with status tracking, rate limits, and retry controls.
- Upload validation covers PDF/DOCX signatures and parser/ZIP constraints, but production should additionally use malware scanning, quarantine, storage isolation, and document classification/approval.
- No download endpoint currently exposes file bytes; if one is added, it must use the same RBAC checks, safe content disposition, and no public/static file path.

- [x] Document indexing endpoint now returns HTTP 200 because indexing is synchronous in the current implementation; HTTP 202 is reserved for future queued processing.

## Additional review findings (2026-11-21)

- `ActionItem.risk_id` and the `Risk.actions` relationship currently use cascading deletion. The API blocks deleting risks that have actions, but direct database deletion or another code path can still cascade-delete action history. Change this to `RESTRICT`/`NO ACTION` in a dedicated migration after validating existing data; do not change ORM metadata alone.
- Action assignee validation currently matches active users by email, but `assigned_to` remains a free-text column. Plan a migration to replace or supplement it with a foreign key to `users.id` and retain a display field only if needed.
- Compliance matrix counters use names `partial_count` and `uncovered_count`, while the underlying statuses are `À vérifier` and `Non évalué`. This is declarative indicator logic, not a verified compliance assessment; rename/clarify counters and add tests before exposing a compliance percentage as a KPI.
- Document indexing is synchronous. Its endpoint returns HTTP 200; the service still needs a background-job architecture before returning 202.


## Authentication session review (2026-11-21)

- Refresh tokens are JWTs with a seven-day lifetime and are exchanged for new token pairs, but refresh-token rotation is not persisted or enforced. A previously issued refresh token remains usable until expiration, so theft/reuse detection and session revocation are not implemented.
- User state and password-change timestamp are checked during refresh, but there is no per-session registry, device/session management, or revocation on logout.
- Implement a persistent session/token-family model before claiming rotation or reuse detection. Store only a cryptographic hash of refresh tokens (or token identifiers), enforce one-time rotation transactionally, revoke the token family on reuse, and provide revocation on password change, account disable, role change, and logout.
- Do not add a logout endpoint that only deletes client-side tokens and imply server-side revocation; it must revoke the server-side session.
- Existing password_changed_at invalidates tokens issued before the password change; preserve this behavior and test timezone/iat boundary conditions.


## Frontend session storage review (2026-11-21)

- Access and refresh JWTs are persisted in browser localStorage (`pgcc_access_token`, `pgcc_refresh_token`). Any successful script injection/XSS can read and exfiltrate them. This confirms the existing backlog item to migrate to HttpOnly, Secure, SameSite cookies with CSRF protection and a short access-token lifetime.
- Frontend refresh queue serializes concurrent 401 requests, but the backend currently does not persist refresh-token rotation; queued retry behavior does not provide theft/reuse detection or revocation.
- Client logout only removes local storage; it cannot revoke an already issued token server-side. Implement server-backed session revocation as part of the session model, not as a client-only logout.
- Avoid persisting role/permission values as authoritative security decisions. Backend RBAC must remain the enforcement point; client-side permission data is UI-only.


## Deployment and public health endpoint review (2026-11-21)

- The public `/health` response reports environment name, AI-enabled state, database connectivity, service phase, and version. Consider separating a minimal liveness endpoint from an authenticated or network-restricted readiness/diagnostics endpoint; public health should expose only the minimum needed by the load balancer.
- Production CORS must be explicitly configured to the deployed frontend origin(s). The current defaults are localhost development origins; validate deployment configuration rather than relying on defaults.
- Security headers, trusted-host validation, and reverse-proxy trust configuration remain unimplemented. Do not enable forwarded-header trust globally without a defined trusted proxy boundary.


## Container configuration review (2026-11-21)

- The current Compose file is development-oriented: PostgreSQL publishes port 5432 on all host interfaces, the frontend runs the Vite development server, backend source is bind-mounted, and `ENVIRONMENT=development` is set. Do not deploy this Compose configuration as-is to production.
- PostgreSQL uses `ankane/pgvector:latest`; pin a maintained image and version/digest. Other runtime images should also be pinned.
- Prepare separate production Compose/deployment configuration: no public database port, production frontend build served by a hardened web server, no source bind mounts, production settings, non-root containers, resource limits, health checks, and private network boundaries.
- `.env.example` includes a placeholder password and JWT secret; deployment automation must fail if placeholders remain and must never commit actual `.env` files.


## GRC API audit coverage review (2026-11-21)

- Applications (`apps.py`) create/update/delete operations currently commit without calling the security audit logger. These business mutations are not traceable in the current security-log API.
- Document upload/delete and risk/action mutations have logging in reviewed paths, but audit logging is a separate best-effort transaction. A mutation can succeed while its audit event fails, leaving a gap. For high-assurance records, use a transactional audit/outbox pattern or append-only database mechanism and monitor failed delivery.
- Expand audit coverage systematically to inventory, compliance assessments, user/role administration, evidence verification, configuration changes, and exports. Define mandatory fields, actor identity, target ID, event, outcome, timestamp, correlation ID, and sanitized before/after values.
