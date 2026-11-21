# Session Security Design

## Status
Design proposal for PGCC Platform. This document does not claim session persistence or refresh-token revocation is implemented.

## Goals
- Persist refresh-token sessions so they can be revoked server-side.
- Store only a cryptographic hash of refresh tokens.
- Rotate refresh tokens on every successful refresh.
- Detect reuse of a previously rotated token and revoke the token family.
- Revoke sessions on password change, account disablement, MFA reset, and administrative action.
- Provide an active-session inventory and revoke-other-sessions action.

## Proposed data model: auth_sessions
- id: UUID primary key
- user_id: FK users.id, indexed, cascade delete
- token_hash: unique SHA-256 hash of a high-entropy opaque refresh token
- family_id: UUID identifying a rotation family
- created_at, last_used_at, expires_at: UTC timestamps
- revoked_at: nullable UTC timestamp
- replaced_by_session_id: nullable self-reference
- revoke_reason: nullable bounded string
- ip_address: nullable, subject to privacy/retention policy
- user_agent: nullable bounded string
- device_label: nullable user-provided label

Do not persist raw refresh tokens. Use opaque random refresh tokens (at least 256 bits entropy), not JWT refresh tokens, so server-side revocation is straightforward. Access tokens remain short-lived JWTs; minimize lifetime and claims.

## Refresh flow
1. Accept refresh token only from agreed secure transport (prefer HttpOnly, Secure, SameSite cookie; define explicit policy for API clients).
2. Hash token and find matching session.
3. Reject if absent, expired, revoked, or user disabled.
4. In a DB transaction, lock session row using SELECT FOR UPDATE.
5. Generate a new opaque refresh token and persist its hash.
6. Mark prior token/session as rotated and record successor.
7. Commit before returning tokens.
8. If a rotated token is presented again, revoke the entire family and log a security event.

## Revocation triggers
- Password change/reset: revoke all user's sessions.
- Account deactivation: revoke all sessions.
- MFA reset/disable: revoke all sessions and require fresh authentication.
- Admin action: revoke selected session or all sessions.
- Reuse detection: revoke the affected token family.

## Cookie and CSRF considerations
For browser sessions, use HttpOnly, Secure, and an appropriate SameSite policy. If refresh is cookie-based and cross-site requests are permitted, implement CSRF protection (synchronizer token or double-submit with strict origin validation). Access tokens should preferably remain in memory rather than localStorage. CORS must use explicit trusted origins and credentials only where needed.

## Audit events
Record session creation, refresh, revocation, reuse detection, password-change revocation, account-disable revocation, and administrative session actions. Do not log token values or secrets. Define retention and access restrictions for IP/user-agent metadata.

## Migration plan
1. Add Alembic migration for auth_sessions and indexes.
2. Deploy schema migration before application code requiring it.
3. Existing JWT refresh tokens cannot be reliably revoked before expiry; use a short transition window and reject old refresh-token format after cutover.
4. Implement refresh endpoint and session-management API.
5. Update frontend token transport and logout/session-management UI.
6. Add PostgreSQL integration tests for concurrent refresh, replay detection, expiry, revoke-all, password-change, and disabled-user behavior.
7. Roll out with feature flag and monitor authentication errors.

## Acceptance criteria
- Raw refresh tokens are never stored in database or logs.
- Refresh rotation is atomic.
- Reuse detection revokes token family.
- Password change and disablement revoke sessions.
- Users can inspect and revoke sessions.
- Tests cover concurrency and revocation.
- Cookie, CSRF, CORS, and proxy behavior are documented and tested.
