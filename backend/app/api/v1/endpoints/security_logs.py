# backend/app/api/v1/endpoints/security_logs.py
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.security_log import SecurityLog
from app.models.user import User

router = APIRouter(prefix="/security/logs", tags=["Journal d'Audit"])


class LogEntryResponse(BaseModel):
    id: str
    timestamp: str
    event_type: str
    user_email: Optional[str] = None
    action: str
    resource: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[LogEntryResponse])
async def list_security_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("security_log", "read"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_email_filter: Optional[str] = Query(default=None, alias="user_email"),
    event_type_filter: Optional[str] = Query(default=None, alias="event_type"),
):
    """
    Retourne les derniers logs de sécurité, paginés et filtrables.
    Réservé aux rôles admin et auditor.
    """
    query = select(SecurityLog).order_by(SecurityLog.timestamp.desc())

    if user_email_filter:
        query = query.where(SecurityLog.user_email == user_email_filter.lower())
    if event_type_filter:
        query = query.where(SecurityLog.event_type == event_type_filter.upper())

    result = await db.execute(query.offset(offset).limit(limit))
    logs = result.scalars().all()

    return [
        LogEntryResponse(
            id=str(log.id),
            timestamp=log.timestamp.isoformat(),
            event_type=log.event_type,
            user_email=log.user_email,
            action=log.action,
            resource=log.resource,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
        )
        for log in logs
    ]