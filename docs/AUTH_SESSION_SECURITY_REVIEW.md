# Authentication Session Security Review

## Controls currently reviewed
- JWT tokens are typed (`access`, `refresh`, `pre_auth`, `change_password`) and expire.
- Access token lifetime is configured to 15 minutes by default.
- Accounts can be temporarily locked after failed login/MFA attempts.
- Password change timestamps are used to reject older refresh tokens.
- Current-user checks verify account active state, forced password change, privileged-role MFA and role consistency.
- Refresh endpoint now also denies inactive, locked, password-change-required, privileged-without-MFA accounts and tokens issued before password change.

## Residual risks
1. Refresh tokens are stateless and not persisted. Rotation currently issues a new refresh token but does not revoke the previous token; replay remains possible until expiry.
2. There is no server-side session inventory, per-device/session revoke, logout revocation or refresh-token reuse detection.
3. MFA secret is stored in the user record; at-rest encryption/key management needs design.
4. Pre-auth tokens can be used to initiate enrollment; enrollment state needs rate limits, lifecycle expiry and stronger session binding.
5. Login and MFA lockout counters share a field, which may create coupled behavior. Review separate counters and rate limiting by account/IP/device.
6. Password policy, password reuse, reset flow, administrator reset, MFA reset, and recovery need explicit workflows and audit.
7. Frontend storage of bearer tokens must be reviewed for XSS. Target architecture: short-lived access token in memory and refresh token in HttpOnly, Secure, SameSite cookie, with CSRF protections.
8. MFA backup-code consumption must be transactionally safe and tests should confirm one-time use under concurrent requests.

## Recommended architecture
- Add Session/RefreshToken table with token identifier, hashed token or JTI, user, issued/expiry, revoked, replaced_by, last_used, device/IP metadata (privacy-minimized).
- Use rotation on every refresh, revoke old token atomically, detect reuse and revoke session family.
- Add `/logout`, `/logout-all`, administrator session revocation and session listing.
- Revoke sessions after password reset, MFA reset, role changes, account disablement and security incident.
- Implement rate limiting at reverse proxy/API layer for login, MFA, enrollment, refresh and password reset.
- Add immutable audit events for session creation, refresh, revocation, reuse detection and MFA lifecycle.
- Add migration and integration tests before implementation; do not retrofit persistence without a verified Alembic baseline.

## Release gate
Authentication is not production-ready until refresh rotation/revocation, session management, rate limiting, MFA lifecycle and frontend token storage are addressed and tested, or formally risk-accepted by the system owner.
