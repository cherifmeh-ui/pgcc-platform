# backend/app/services/security_logger.py
from typing import Optional

from fastapi import Request

from app.core.database import AsyncSessionLocal
from app.models.security_log import SecurityLog


def get_client_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None

    # Never trust client-supplied X-Forwarded-For unless a trusted-proxy
    # configuration is explicitly implemented. Direct peer is the safe default.
    if request.client:
        return request.client.host

    return None


def get_user_agent(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    user_agent = request.headers.get("user-agent")
    return user_agent[:255] if user_agent else None


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
    """
    Enregistre une action dans le journal de sécurité.
    Fire-and-forget : ne bloque jamais l'action principale si le log échoue.
    """
    resolved_event_type = event_type or _infer_event_type(resource, action)
    resolved_ip = ip_address or get_client_ip(request)
    resolved_user_agent = get_user_agent(request)

    async with AsyncSessionLocal() as session:
        try:
            new_log = SecurityLog(
                event_type=resolved_event_type,
                user_email=user_email,
                action=action,
                resource=resource,
                resource_id=resource_id,
                details=details,
                ip_address=resolved_ip,
                user_agent=resolved_user_agent,
            )

            session.add(new_log)
            await session.commit()
            await session.refresh(new_log)
            return new_log
        except Exception as exc:
            await session.rollback()
            print(f"❌ Erreur journal de sécurité: {exc}")
            return None


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