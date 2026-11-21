# backend/app/api/v1/endpoints/apps.py
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from uuid import UUID

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.application import Application
from app.models.user import User
from app.services.security_logger import log_action

router = APIRouter(prefix="/apps", tags=["Applications Critiques"])


class AppBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    module: Optional[str] = Field(None, max_length=100)
    owner: Optional[str] = Field(None, max_length=150)
    direction: Optional[str] = Field(None, max_length=50)
    access_level: Optional[str] = Field(None, max_length=100)
    hosting_current: Optional[str] = Field(None, max_length=100)
    hosting_target: Optional[str] = Field(None, max_length=100)
    criticality: str = Field("Moyenne", pattern="^(Faible|Moyenne|Élevée|Critique)$")
    main_risk: Optional[str] = Field(None, max_length=200)
    treatment_plan: Optional[str] = None
    comment: Optional[str] = None


class AppCreate(AppBase):
    pass


class AppUpdate(AppBase):
    pass


class AppResponse(AppBase):
    id: UUID
    class Config:
        from_attributes = True


@router.get("/", response_model=List[AppResponse])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("apps", "read"),
):
    result = await db.execute(select(Application).order_by(Application.criticality.desc(), Application.name))
    return result.scalars().all()


@router.post("/", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    data: AppCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("apps", "create"),
):
    app = Application(**data.model_dump())
    db.add(app)
    await db.commit()
    await db.refresh(app)
    await log_action(
        user_email=current_user.email,
        action="CREATE",
        resource="applications",
        resource_id=str(app.id),
        details=f"Application created: {app.name[:100]}",
        event_type="APPLICATION",
        request=request,
    )
    return app


@router.put("/{app_id}", response_model=AppResponse)
async def update_application(
    app_id: UUID,
    data: AppUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("apps", "update"),
):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application non trouvée")
    for k, v in data.model_dump().items():
        setattr(app, k, v)
    await db.commit()
    await db.refresh(app)
    await log_action(
        user_email=current_user.email,
        action="UPDATE",
        resource="applications",
        resource_id=str(app.id),
        details=f"Application updated: {app.name[:100]}",
        event_type="APPLICATION",
        request=request,
    )
    return app


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("apps", "delete"),
):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application non trouvée")
    app_name = app.name[:100]
    await db.delete(app)
    await db.commit()
    await log_action(
        user_email=current_user.email,
        action="DELETE",
        resource="applications",
        resource_id=str(app_id),
        details=f"Application deleted: {app_name}",
        event_type="APPLICATION",
        request=request,
    )