# Phase 0 — Security review findings (2026-11-21)

This review is based on source inspection of the stabilization branch. It is not a penetration test or runtime validation.

## Refresh-token rotation and concurrency

### Implemented
- Persisted refresh sessions keyed by SHA-256 of JWT `jti`; raw JWT is not stored.
- Refresh flow locks the user row, then the refresh-session row, validates eligibility and expiry, creates the replacement session, revokes the previous session, and commits.
- Reuse of a revoked refresh token revokes the user's active refresh sessions.
- Logout revokes the presented session.
- Password-change flow revokes active refresh sessions.

### Remaining validation / risks
- PostgreSQL integration tests are required to prove locking behavior and atomicity.
- Two legitimate clients (e.g. tabs) refreshing the same token concurrently can cause the second request to be treated as replay and revoke the newly-created session. Client-side single-flight coordination and cross-tab coordination should be implemented or documented before auth gate closure.
- Review whether MFA-confirmation and forced-password-change flows persist session rows consistently and whether audit events are emitted after the transaction without misleading success records.
- A failed refresh should not accidentally leave partial session state; verify with DB tests.

## PostgreSQL migrations

- Revision 0021 creates refresh_token_sessions with FK cascade, unique JTI hash, expiry and user indexes.
- Static revision-graph checks exist.
- **Not verified:** full upgrade on a clean PostgreSQL database, upgrade from an existing supported deployment, downgrade behavior, SQL generated/executed against the target PostgreSQL version, and post-upgrade schema drift.

## Documents and RAG

### Positive controls observed
- Upload reads at most 10 MiB plus one byte.
- Filename is normalized and bounded; PDF/DOCX extensions and signatures are checked.
- Extraction is bounded and parser exceptions are not exposed.
- RAG chunk count is capped; embeddings are generated before replacing chunks; DB rollback preserves prior chunks on failure.
- Document routes use explicit permission dependencies.
- Deletion refuses documents referenced as ISO evidence and explicitly removes chunks.

### Risks requiring closure
- File parsing is not sandboxed and antivirus scanning is not integrated.
- Signature checks are shallow (PDF magic prefix and ZIP prefix for DOCX); deeper structural validation and archive-bomb protection need tests/controls.
- Document model has no classification/ACL fields. AI context endpoint checks the global `documents:read` permission, then queries PSSI documents and control-reference matches. This means authorization is role-level only; document-level classification/access policy is not implemented. Define a classification model and enforce it in list, preview, download, AI context retrieval, and vector search before production use.
- Indexing is synchronous and may block API workers; production should use a bounded worker/job mechanism.
- AI context query logs only successful responses; denial, provider failures, and query metadata should be considered for security/audit event coverage without logging full prompts or sensitive content.
- RAG/index failure paths and concurrent re-index/delete need integration tests.

## Audit logging

- Security log values are bounded; forwarded client IP is not trusted by default.
- Logger uses a separate session and is best-effort; failures are logged but do not fail the business action.
- This is not tamper-resistant audit storage. Production requires retention policy, restricted write/delete access, integrity protection or external sink, monitoring/alerting for logging failures, and coverage of high-risk events.

## API authorization

- RBAC matrix normalizes role/module/action and denies unknown values; unit tests cover normalization and default deny.
- AST coverage test verifies that non-auth endpoints declare a dependency, but it does not prove correct permission, object-level authorization, tenant/scope enforcement, or authorization inside service functions.
- Asset-risk linking performs additional cross-module permission checks, with API tests for unauthorized linking and unlinking.
- Required: broad role matrix tests for read/write/delete/export, object-level access tests, document/RAG classification tests, and checks for IDOR.
- Source review found the assets impact endpoint selectively omits linked risks/supplier access details based on module permissions; continue testing response field-level authorization to avoid leakage.

## Phase 0 exit gates

Do not close Phase 0 until evidence is attached for:
1. Current-head CI (backend and frontend).
2. PostgreSQL clean install + migration upgrade from supported baseline.
3. Refresh rotation/replay/logout/password-change concurrency tests on PostgreSQL.
4. Docker compose fresh stack health.
5. Endpoint permission and object-level authorization tests.
6. Document upload/download/delete and RAG retrieval authorization tests.
7. Audit event coverage and operational integrity decisions.
8. Full PR diff review and human approval.



## RBAC source review — additional evidence

- `role_has_permission` normalizes role/module/action and denies unknown roles/modules/actions.
- Unit tests cover normalization and default-deny behavior.
- Asset-risk endpoints perform explicit cross-module permission checks and API tests verify denial before DB access.
- The endpoint dependency AST test is structural only; it is not a substitute for route-level permission and object-authorization tests.


## Docker deployment review — source inspection

- Compose waits for PostgreSQL health before backend start, which is good.
- PostgreSQL image uses the floating `ankane/pgvector:latest` tag; pin a tested version/digest for reproducibility.
- Backend and frontend are development-oriented: hot-reload mounts, `ENVIRONMENT: development`, frontend `npm install` on startup, and direct published ports. A production profile should use immutable builds, lockfile-driven install, non-root runtime, secrets management, reverse proxy/TLS, restrictive network exposure, and health checks for backend/frontend.
- No Docker Compose runtime test has been executed in this review.


## Refresh session schema alignment

- Migration 0021 defines a database-side default for `created_at` (`now()`). The ORM model previously only had a Python-side default; it has now been aligned with `server_default=func.now()` so direct SQL inserts and ORM metadata agree.
- Added a model test asserting the server default exists. PostgreSQL integration migration/test is pending CI.


## Migration review — revision 0020 downgrade index mismatch

- Found a mismatch in revision `0020`: upgrade creates a unique index on `lower(btrim(reference))`, while downgrade recreated the earlier index on `lower(reference)`. This would leave schema behavior different from the prior revision after downgrade.
- Corrected downgrade to restore the exact pre-0020 index expression `lower(reference)`, preserving upgrade/downgrade symmetry.
- Added a static regression test asserting both index expressions and the guarded downgrade for cloud_resource values.
- Runtime PostgreSQL migration/downgrade validation is still required.


## PostgreSQL migration CI failure — baseline dependency

- The first PostgreSQL clean-upgrade CI run failed in revision `0001_initial`: SQLAlchemy metadata creation could not resolve `action_items.iso_assessment_id` to `iso_control_assessments.id` because the baseline did not import the assessment model.
- Corrected baseline imports to register `iso_control_assessment` before metadata `create_all`.
- Revision `0002_iso_assessments` now checks whether the table already exists and creates missing indexes, avoiding duplicate-table failure when the initial metadata baseline creates the table. This supports clean DB upgrade and previously migrated databases where 0002 originally created the table.
- CI must confirm this migration path. Downgrade semantics remain to be exercised against disposable PostgreSQL.


## Alembic baseline architecture caveat

- Revision `0001_initial` uses `Base.metadata.create_all()` and imports only a subset of models; later revisions create other tables and add columns/constraints.
- This hybrid baseline can overlap later revisions when models imported by the baseline already contain fields added in later migrations (notably ActionItem ISO links). Conditional checks are being added to make clean upgrades resilient.
- Downgrade symmetry is not fully guaranteed: because baseline metadata can include schema introduced by later revisions, downgrading a later revision may remove columns that were also created by baseline metadata. The baseline is intentionally non-downgradable, but the intermediate downgrade path still needs disposable-DB validation and a documented support policy.
- Long-term recommendation: replace metadata-driven baseline with explicit schema DDL or a carefully generated frozen baseline, and keep later revisions strictly additive/differential. Do not perform this redesign in the stabilization branch without a dedicated migration strategy.


## Root cause confirmed: baseline metadata is globally loaded

- `backend/migrations/env.py` imports every current model into `Base.metadata` before migrations run.
- Revision `0001_initial` calls `Base.metadata.create_all()` without an explicit historical table list. Therefore the baseline may create tables introduced by later revisions, producing duplicate-table/column/index/constraint failures when later revisions run.
- Conditional guards added to revisions 0002/0004/0006 mitigate specific overlaps but are not a complete migration-chain strategy.
- Recommended stabilization strategy: determine the exact legacy baseline schema and make revision 0001 create only that frozen schema (explicit table list or explicit DDL); then validate upgrade from 0001 through head and downgrade on a disposable PostgreSQL instance. Avoid broadly adding `IF NOT EXISTS` to all migrations because that can conceal schema drift and missing constraints.
- This is a blocking Phase 0 migration issue until clean upgrade and downgrade are demonstrated.

## Follow-up — transactional document/RAG and refresh-session audit — 2026-11-24

- Document upload and deletion now enqueue durable audit events in the same transaction as the document/chunk changes. RAG chunk replacement and the is_indexed flag now share the INDEX audit event transaction.
- Added PostgreSQL test coverage for index-vs-delete serialization, duplicate-upload uniqueness with a durable UPLOAD event, upload rollback on audit enqueue failure, and RAG chunk rollback on audit enqueue failure. These additions are committed but await fresh CI execution.
- Refresh rotation, replay detection, account-eligibility denial/session revocation and logout now enqueue audit-outbox events before the same transaction commits. The refresh endpoint uses the request context for actor metadata.
- Added PostgreSQL tests that exercise concurrent calls to the actual refresh endpoint with one old token, assert replay revocation and both audit events, and verify the old session remains active if audit enqueue fails. These tests are committed but await fresh CI execution.
- Residual: proactively revoke persisted sessions from account disable, role change, MFA reset and administrator security-reset workflows; add retention/cleanup for expired refresh sessions; monitor outbox delivery and test logout audit rollback.

## Migration head correction

- The current migration head is 0024_audit_outbox, not 0021_refresh_token_sessions. The database validation runbook now reflects revision 0024 and includes audit_outbox/security_logs checks.


## RBAC normalization hardening — 2026-11-24

- Access-token authentication now normalizes the persisted role before privileged-role MFA enforcement, matching the RBAC matrix's case/whitespace normalization.
- Access-token role claims are now required, must be non-empty strings, and must match the normalized database role. Missing, malformed or mismatched claims are rejected with 403.
- Added unit tests for uppercase/whitespace privileged-role MFA enforcement, missing/malformed/mismatched claims and normalized matching roles.
- Commits: 07c434f (implementation), 8149214 (tests). Fresh CI execution remains pending.


## Authentication transaction follow-up — 2026-11-25

- Password change now updates password state, revokes old refresh sessions, persists a replacement session and enqueues PASSWORD_CHANGED in one transaction with rollback on failure.
- MFA enrollment start now locks the user row and enqueues MFA_ENROLLMENT_STARTED in the same transaction as writing the pending enrollment secret.
- MFA completion events (initial enrollment/login and mandatory-password-change path) are now enqueued before commit with rollback on audit failure.
- Added focused unit tests for password-change audit ordering/rollback and MFA enrollment audit ordering/rollback. Added separate MFA enrollment test module.
- Remaining: administrator lifecycle paths for account/role/MFA reset and session revocation; encrypted MFA secret storage; rate limiting; CI execution on latest head.
