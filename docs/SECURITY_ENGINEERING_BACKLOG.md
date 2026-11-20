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
- [x] Require dedicated change-password token for forced password change; remove access-token fallback.\n- [ ] Complete frontend forced-password-change flow and validate token issuance.
- [x] Apply account lockout policy to MFA verification failures.\n- [ ] Add distributed rate limiting for login, MFA, enrollment, and refresh endpoints.
- [ ] Encrypt MFA secrets at rest and define key rotation.
- [ ] Add MFA reset/recovery process with audit and administrator approval.
- [ ] Verify anti-enumeration behavior and consistent login responses.
- [ ] Review all endpoint permissions; add authorization tests.
- [ ] Replace browser localStorage bearer-token persistence with safer session design (HttpOnly Secure SameSite cookie strategy, CSRF controls, short-lived access token).
- [ ] Add security headers and trusted proxy configuration.

## Phase 2 — Core GRC

- [ ] Risk register: scenario, threat, vulnerability, affected asset/process, owners, inherent and residual risk.
- [ ] Formal risk treatment (avoid/reduce/transfer/accept), rationale and approval.
- [ ] Residual-risk acceptance with approver, expiry, review date, compensating controls.
- [ ] Action-plan workflow with owner, evidence, validation, history and overdue tracking.
- [x] Audit log for document upload, deletion and successful indexing.\n- [ ] Audit trail for every sensitive business mutation.

## Phase 3 — Asset and application inventory

- [ ] Extend inventory to business/technical owner, classification, data types, hosting, dependencies, exposure, lifecycle, support, security controls and continuity targets.
- [ ] Add asset relationships and risk/control links.
- [ ] Support inventory evidence and review dates.

## Phase 4 — ISO compliance and audit

- [ ] Verify ISO/IEC 27002:2022 control references and titles against an authoritative licensed source.
- [ ] Version control reference datasets; never mix editions.
- [ ] Separate applicability, implementation status, maturity, verification and evidence.
- [ ] Implement statement of applicability and justified exclusions.
- [ ] Add audit findings, nonconformities, recommendations and linked actions.

## Phase 5 — Documents and evidence

- [x] Signature/format validation, bounded upload read, file size/page limits, PDF encryption rejection, DOCX ZIP structure/expansion checks and safe parsing.\n- [ ] Malware scanning and isolated parsing.
- [ ] Hashing, versioning, classification, retention, ownership and approval.
- [ ] Prefer object storage for binaries; database stores metadata and references.
- [ ] Evidence links to risks, controls, audits and actions.
- [x] Validate uploaded file type/signature, bounds, filename and PDF/DOCX parsing containers.\n- [ ] Secure RAG ingestion, chunk metadata, processing states, failure handling and citations.

## Phase 6 — AI/RAG

- [ ] Fix missing/unfinished AI service functions and endpoint mismatches.
- [ ] Add hybrid retrieval and permission/classification filtering.
- [ ] Verify embedding model dimensions and pgvector compatibility.
- [ ] Include document/page/version citations and confidence/missing-context notes.
- [ ] AI suggestions must be reviewable and never silently change GRC records.
- [x] Treat risk data as untrusted in ISO suggestion prompt and validate/filter returned control references.\n- [ ] Add prompt-injection handling for uploaded content and retrieved documents.

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
