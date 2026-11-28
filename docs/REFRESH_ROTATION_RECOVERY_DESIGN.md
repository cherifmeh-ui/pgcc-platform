# Refresh-token rotation recovery — design gate

**Status:** analysis only; no behavior change approved  
**Date:** 28 November 2026  
**Related:** Issue #7

## Problem statement

The refresh endpoint commits the new refresh-session row and revokes the presented row before returning the replacement token as an HttpOnly cookie. If the database commit succeeds but the HTTP response (including Set-Cookie) is lost, the browser retains the now-revoked token. A subsequent request with that token follows the existing replay path and revokes the user's active refresh sessions.

This is an ambiguous outcome: the server cannot infer from the old bearer token alone whether the second presentation is a legitimate retry after a lost response or an attacker replaying a stolen token.

## Security invariant

Do not turn a revoked-token presentation into an accepted refresh merely because it occurs within a time window. Do not remove or weaken the current replay detection, session revocation, audit event, origin validation, rate limiting, or PostgreSQL row-locking behavior without a reviewed protocol that distinguishes an authorized retry from a replay.

## Candidate protocol requiring security review

A possible idempotent retry protocol would require all of the following, not just a grace period:

1. The client creates a cryptographically random refresh-operation identifier before sending the refresh request and retains it only for the lifetime of that unresolved operation.
2. The request sends the identifier in a dedicated header. It must not be placed in URLs or application logs.
3. The server binds the operation to the user, old refresh-token hash, current auth/security version and a short explicit expiry.
4. The server stores the replacement refresh token only as authenticated ciphertext under a dedicated, managed, rotatable encryption key; the existing MFA key must not be silently repurposed.
5. A retry is recoverable only when the old token **and** the exact operation identifier match the committed operation, and only while the recovery record is valid. A different identifier or an old token without the matching operation identifier remains a replay and follows the current revocation path.
6. The operation record is created atomically with token rotation, is single-purpose, is not reusable indefinitely, and has explicit cleanup/retention behavior.
7. Concurrent tabs must share or safely await the same in-flight operation result. A per-tab identifier alone does not solve the case where a second tab takes the lock after the first tab loses its response.
8. Tests must cover database commit followed by dropped response, same-operation retry, different-operation replay, simultaneous tabs, process restart, encryption-key rotation/loss, expiry, cleanup, audit durability and rate limiting.

This protocol creates a short-lived encrypted bearer-token recovery store and a new sensitive key-management obligation. It is **not approved for implementation** until threat-model review, key-management/runbook work, schema/migration review and end-to-end PostgreSQL/browser tests are complete.

## Alternatives and trade-offs

- **Fail closed / require re-authentication:** simplest and avoids storing recoverable bearer tokens, but a lost response can cause the user to lose the session and the next old-token presentation may trigger global session revocation under current policy.
- **Short grace period based only on old token:** rejected. It makes stolen-token replay indistinguishable from legitimate retry and weakens the existing replay control.
- **Encrypted idempotent response recovery:** potentially viable, but requires the full binding and cross-tab coordination protocol above; a timestamp window alone is insufficient.

## Current evidence

- The auth refresh endpoint commits rotation and revocation before setting the replacement cookie.
- RefreshTokenSession stores only the old token hash, expiry, revocation time and replacement hash; it does not retain the raw replacement JWT.
- Existing PostgreSQL tests verify one winner for concurrent rotation and that a second use of the revoked token is detected and audited.
- Playwright currently verifies cross-tab Web Locks and shared HttpOnly cookie behavior against an intercepted/simulated refresh endpoint, not the real FastAPI/PostgreSQL endpoint.

## Exit criteria

- Approved threat model and explicit decision on acceptable recovery vs re-authentication.
- Reviewed encryption-key ownership, rotation, backup, access control and incident procedure if encrypted recovery data/key is exposed or lost.
- PostgreSQL migration and atomic transaction tests.
- Browser tests against the actual backend, including response loss after commit and simultaneous tabs.
- Evidence that a distinct replay remains detected and revoked.
- Documentation and CI green on the exact reviewed commit.

Until these criteria are met, retain the current fail-secure replay behavior and keep Phase 0 Auth / Issue #7 open.
