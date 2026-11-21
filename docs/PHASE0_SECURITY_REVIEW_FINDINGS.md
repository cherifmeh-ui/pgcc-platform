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
- RAG retrieval authorization must be enforced at query time for document classification/permissions; inspect all AI endpoints and retrieval query paths.
- Indexing is synchronous and may block API workers; production should use a bounded worker/job mechanism.
- RAG/index failure paths and concurrent re-index/delete need integration tests.

## Audit logging

- Security log values are bounded; forwarded client IP is not trusted by default.
- Logger uses a separate session and is best-effort; failures are logged but do not fail the business action.
- This is not tamper-resistant audit storage. Production requires retention policy, restricted write/delete access, integrity protection or external sink, monitoring/alerting for logging failures, and coverage of high-risk events.

## API authorization

- AST coverage test verifies that non-auth endpoints declare a dependency, but it does not prove correct permission, object-level authorization, tenant/scope enforcement, or authorization inside service functions.
- Required: role matrix tests for read/write/delete/export, object-level access tests, document/RAG classification tests, and checks for IDOR.

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

