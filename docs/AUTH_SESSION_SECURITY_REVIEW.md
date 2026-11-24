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
2. **Refresh auditability:** rotation, reuse detection, denial and logout do not yet write durable audit-outbox events in the same transaction as session changes. Add actor/request-aware audit events without weakening rollback semantics.
3. **HTTP-level concurrency:** add PostgreSQL integration tests that call the actual /auth/refresh endpoint with the same token concurrently, assert exactly one success, and verify reuse revocation behavior.
4. **Rate limiting:** add distributed account/IP/device rate limiting for login, MFA, enrollment, refresh and password reset. Current database lockout counters are not a substitute for distributed rate limiting.
5. **MFA secret protection:** mfa_secret is stored on the user record; design encryption at rest, key management and rotation, plus an administrator-approved MFA reset/recovery workflow.
6. **Enrollment lifecycle:** constrain pre-auth enrollment state, prevent repeated enrollment-secret replacement abuse, and bind enrollment to a short-lived authenticated flow.
7. **Password lifecycle:** define password reuse/history, reset and administrator recovery policy. Login and MFA failures currently share failed_login_attempts; assess separate counters and lockout semantics.
8. **Browser token storage:** review the frontend bearer-token persistence and XSS exposure. Target design remains short-lived access token in memory and refresh token in HttpOnly, Secure, SameSite cookie with CSRF protection.
9. **Audit delivery:** define and test security events for session creation, rotation, revocation, reuse detection, MFA enrollment/reset and password changes. Avoid silently dropping audit persistence failures.

## Release gate

Authentication/session security remains open until the HTTP-level PostgreSQL rotation/reuse tests, full session lifecycle revocation, durable audit coverage, rate limiting, MFA secret protection and frontend token-storage review are completed or explicitly risk-accepted by the system owner.
