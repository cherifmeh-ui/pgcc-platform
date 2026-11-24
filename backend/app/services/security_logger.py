"""Durable audit event outbox and append-only security log delivery."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.audit_outbox import AuditOutbox
from app.models.security_log import SecurityLog

logger = logging.getLogger(__name__)


class AuditOutboxPersistenceError(RuntimeError):
    """Raised when an audit event cannot be durably queued."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_client_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    # Never trust X-Forwarded-For unless a trusted-proxy policy is configured.
    return request.client.host if request.client else None


def get_user_agent(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    user_agent = request.headers.get("user-agent")
    return user_agent[:255] if user_agent else None


def _infer_event_type(resource: Optional[str], action: str) -> str:
    if resource == "auth":
        return "AUTH"
    if resource == "risks":
        return "RISK"
    if resource == "actions":
        return "ACTION"
    if resource == "documents":
        return "DOCUMENT"
    if resource == "pam":
        return "PAM"
    if resource == "audits":
        return "AUDIT"
    if resource == "security_logs":
        return "SECURITY_LOG"
    if action in {"LOGIN_SUCCESS", "LOGIN_FAILED", "MFA_FAILED", "PASSWORD_CHANGED"}:
        return "AUTH"
    return "SYSTEM"


def _build_payload(
    *,
    user_email: Optional[str],
    action: str,
    resource: Optional[str],
    resource_id: Optional[str],
    details: Optional[str],
    event_type: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> dict:
    return {
        "event_type": (event_type or _infer_event_type(resource, action))[:50],
        "user_email": user_email[:255] if user_email else None,
        "action": action[:100],
        "resource": resource[:100] if resource else None,
        "resource_id": resource_id[:255] if resource_id else None,
        "details": details[:2000] if details else None,
        "ip_address": ip_address[:45] if ip_address else None,
        "user_agent": user_agent[:255] if user_agent else None,
    }


def _insert_security_log(session, event: AuditOutbox) -> None:
    session.add(SecurityLog(event_id=event.id, **event.payload))


async def _record_delivery_failure(event_id: UUID, error: Exception) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(AuditOutbox)
                .where(AuditOutbox.id == event_id, AuditOutbox.delivered_at.is_(None))
                .values(
                    attempts=AuditOutbox.attempts + 1,
                    last_error=type(error).__name__[:100],
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Could not persist audit outbox retry metadata (event_id=%s)", event_id)


async def deliver_pending_audit_events(
    *, limit: int = 100, event_id: Optional[UUID] = None
) -> int:
    """Atomically materialize pending outbox rows into immutable security logs."""
    delivered = 0
    failed_id: Optional[UUID] = None
    async with AsyncSessionLocal() as session:
        statement = (
            select(AuditOutbox)
            .where(AuditOutbox.delivered_at.is_(None))
            .order_by(AuditOutbox.created_at, AuditOutbox.id)
            .limit(max(1, min(limit, 500)))
            .with_for_update(skip_locked=True)
        )
        if event_id is not None:
            statement = statement.where(AuditOutbox.id == event_id)
        events = (await session.execute(statement)).scalars().all()

        try:
            for event in events:
                failed_id = event.id
                existing = await session.scalar(
                    select(SecurityLog.id).where(SecurityLog.event_id == event.id)
                )
                if existing is None:
                    _insert_security_log(session, event)
                event.delivered_at = utcnow()
                event.attempts += 1
                event.last_error = None
                delivered += 1
            await session.commit()
        except Exception as exc:
            await session.rollback()
            failed_id = failed_id or event_id
            if failed_id is not None:
                await _record_delivery_failure(failed_id, exc)
            raise
    return delivered


async def log_action(
    user_email: Optional[str],
    action: str,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[str] = None,
    event_type: Optional[str] = None,
    ip_address: Optional[str] = None,
    request: Optional[Request] = None,
):
    """Durably enqueue an audit event, then attempt immediate log delivery.

    Failure to deliver to security_logs leaves the committed outbox row pending.
    Failure to commit the outbox itself is surfaced to the caller.
    """
    payload = _build_payload(
        user_email=user_email,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details,
        event_type=event_type,
        ip_address=ip_address or get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    async with AsyncSessionLocal() as session:
        event = AuditOutbox(payload=payload)
        session.add(event)
        try:
            await session.commit()
            event_id = event.id
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "Audit outbox persistence failed (event_type=%s, resource=%s, action=%s)",
                payload["event_type"], payload["resource"], payload["action"],
            )
            raise AuditOutboxPersistenceError(
                "Audit event could not be durably queued"
            ) from exc

    try:
        await deliver_pending_audit_events(limit=1, event_id=event_id)
    except Exception:
        # The event is already durable in audit_outbox and will be retried by
        # the lifespan worker. Do not silently discard it.
        logger.warning("Audit event remains pending delivery (event_id=%s)", event_id)
    return event_id


async def audit_outbox_worker(poll_interval_seconds: float = 5.0) -> None:
    """Retry pending audit events until application shutdown."""
    while True:
        try:
            delivered = await deliver_pending_audit_events(limit=100)
            if delivered:
                logger.info("Delivered %s pending audit events", delivered)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Audit outbox delivery cycle failed")
        await asyncio.sleep(poll_interval_seconds)
