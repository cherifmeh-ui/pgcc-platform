# Authentication Session Security Review

Status: active review; not a certification or production approval.

## Controls verified in the current code

- JWTs are typed (access, refresh, pre_auth, change_password) and use configured expiry.
- Refresh-session persistence stores a SHA-256 hash of the JWT jti, not the raw refresh token. The database enforces unique JTI hashes and indexes user/expiry state.
- The refresh endpoint locks the user row and then the presented session row, validates account eligibility, revokes the old session and inserts the replacement in one database transaction.
- Reuse of a revoked refresh token revokes all remaining active refresh sessions for that user.
- Logout revokes the presented refresh session; invalid tokens are handled idempotently.
- Password change revokes active refresh sessions and issues a new persisted refresh session.
- Refresh is denied for inactive, locked, forced-password-change, privileged-without-MFA accounts and tokens issued before the password-change timestamp.
- Access-token authentication checks account active state, forced password change, MFA for privileged roles and token-role/database-role consistency.
- MFA backup-code consumption and MFA verification lock the user row to serialize concurrent attempts.
- PostgreSQL test coverage exists for a concurrent rotation model using user/session row locks, as well as logout and session persistence unit tests. The concurrency test currently exercises the database locking sequence directly rather than invoking the HTTP refresh endpoint.

## Residual risks and validation gates

1. **Session lifecycle completeness:** explicitly revoke sessions when an account is disabled, a user's role changes, MFA is reset, or an administrator performs a security reset. Current access-token checks block inactive accounts and role-mismatched access tokens; refresh eligibility also blocks inactive users, but the persisted rows are not proactively revoked by every administrative lifecycle operation.
2. **Refresh auditability:** rotation, reuse detection, eligibility denial and logout now enqueue durable audit-outbox events in the same transaction as session changes. The new paths still require fresh CI execution and operational delivery monitoring.
3. **HTTP-level concurrency:** PostgreSQL integration tests now call the actual /auth/refresh endpoint concurrently with the same token, assert exactly one success, verify replay revocation and test rollback when audit enqueue fails. Fresh CI execution on the latest branch head remains pending.
4. **Rate limiting:** add distributed account/IP/device rate limiting for login, MFA, enrollment, refresh and password reset. Current database lockout counters are not a substitute for distributed rate limiting.
5. **MFA secret protection:** TOTP secrets are now Fernet-encrypted at rest, with a managed key ring, legacy migration script and non-development startup gate. Operational key custody/rotation and administrator-approved MFA reset/recovery remain deployment controls.
6. **Enrollment lifecycle:** constrain pre-auth enrollment state, prevent repeated enrollment-secret replacement abuse, and bind enrollment to a short-lived authenticated flow.
7. **Password lifecycle:** define password reuse/history, reset and administrator recovery policy. Login and MFA failures currently share failed_login_attempts; assess separate counters and lockout semantics.
8. **Browser token storage:** review the frontend bearer-token persistence and XSS exposure. Target design remains short-lived access token in memory and refresh token in HttpOnly, Secure, SameSite cookie with CSRF protection.
9. **Audit delivery:** refresh rotation, reuse, eligibility denial, logout, MFA enrollment start/success and password changes now enqueue durable outbox events in their business transaction. Remaining work: administrative MFA reset/session revocation events, monitoring/retention and tests for audit delivery retries.

## Release gate

Authentication/session security remains open until the HTTP-level PostgreSQL rotation/reuse tests, full session lifecycle revocation, durable audit coverage, rate limiting, MFA secret protection and frontend token-storage review are completed or explicitly risk-accepted by the system owner.

## Frontend token-storage review — 2026-11-25

- Confirmed current implementation stores both access and refresh tokens in browser localStorage (`pgcc_access_token`, `pgcc_refresh_token`) and the Axios interceptor reads the access token from localStorage on each request.
- This exposes long-lived refresh credentials to any successful same-origin XSS. It is not a theoretical or closed item: the current implementation is not using HttpOnly cookies.
- Target remediation: move refresh token to an HttpOnly, Secure, SameSite cookie with a narrow auth path; add CSRF/origin controls; remove refresh token from JSON and localStorage; keep access token short-lived and preferably memory-only; bootstrap the session via cookie refresh.
- Do not implement only the frontend half: backend cookie issuance/rotation/clearing, CORS credentials, CSRF policy, integration tests and frontend state bootstrap must be deployed together.

## Refresh cookie transport review — 2026-11-25

- Refresh tokens are no longer included in TokenPairResponse. Backend sets an HttpOnly, SameSite=Strict cookie scoped to `/api/v1/auth`; Secure is enabled outside development.
- Cookie refresh/logout requests require an Origin in the configured explicit CORS allowlist. CORS already enables credentials and rejects wildcard origins in production.
- Frontend stores access token in memory only, uses credentialed requests and restores a session from the cookie after reload. Concurrent restore calls share one in-flight promise.
- Remaining validation: CI and production same-site deployment review. The legacy JSON refresh-token input has been removed; refresh and logout now require the cookie transport. Fresh CI and production same-site deployment review remain pending.

## CI cookie migration correction — 2026-11-25

- Workflow 45569880462 found a test invocation mismatch, not a production request flaw: direct function calls inherited FastAPI's Cookie marker default. The endpoints now use Annotated Cookie parameters with a None default.
- The browser cookie flow and Origin checks remain in place. Fresh CI validation is pending.

## Refresh-cookie security CI evidence — 2026-11-25

- Workflow 45572713404 passed backend (303 passed/13 skipped), PostgreSQL (13 passed), frontend build/audit and Docker Compose smoke.
- Cookie-only refresh/logout transport, HttpOnly/Secure/SameSite cookie flags, Origin allowlist, in-memory access token, cookie-backed reload bootstrap and PostgreSQL rotation/replay tests are included in this green run.
- Remaining: human review of production frontend/API same-site topology, deployment cookie settings, and administrative account/role/MFA reset flows.

## MFA storage hardening — 2026-11-25

- TOTP secrets are now encrypted at rest with Fernet. New enrollments persist ciphertext; legacy plaintext is lazily encrypted when MFA is used.
- Non-development environments require a managed Fernet key ring and startup fails closed while plaintext rows remain. The one-time migration and rotation script is documented in `docs/MFA_SECRET_ENCRYPTION_RUNBOOK.md`.
- Remaining: verify CI and run the migration on the target database before production rollout; back up keys securely and define operational rotation ownership.

## MFA and document ACL validation evidence — 2026-11-25

- Workflow 45574537534 passed all four jobs: backend 341 passed/14 skipped; PostgreSQL 14 passed; frontend build/npm audit passed; Docker Compose stack/proxy smoke passed.
- Fernet-encrypted MFA secret persistence, legacy conversion, key rotation, key-ring validation and startup integrity gate have automated unit/PostgreSQL coverage.
- Document classification enforcement has unit and PostgreSQL coverage for viewer listing, direct preview and download denial.
- Operational production steps remain: set/backup managed Fernet key ring, migrate existing plaintext secrets, review key rotation ownership and verify deployment same-site cookie behavior.

## Latest CI evidence — 2026-11-25

- Workflow 45574715908 passed 4/4 jobs: backend 342 passed/15 skipped; PostgreSQL 15 passed; frontend npm audit zero/build passed; Docker Compose full stack/proxy smoke passed.
- Cookie-only refresh transport, Fernet MFA secret encryption and document classification ACL all passed automated tests.
- Remaining operational controls: production key custody/migration, admin account lifecycle session revocation, distributed rate limiting, and production database backup/restore/legacy-upgrade rehearsal.