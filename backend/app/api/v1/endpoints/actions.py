# backend/app/api/v1/endpoints/actions.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.action_item import ActionItem, ActionStatus, Priority
from app.models.risk import Risk
from app.models.user import User

router = APIRouter(prefix="/actions", tags=["Plans d'Action"])


# --- SCHÉMAS PYDANTIC ---

class ActionBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: ActionStatus = ActionStatus.TODO
    priority: Priority = Priority.MEDIUM
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None


class ActionCreate(ActionBase):
    risk_id: UUID = Field(..., description="UUID du risque associé")


class ActionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[ActionStatus] = None
    priority: Optional[Priority] = None
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None


class ActionResponse(ActionBase):
    id: UUID
    risk_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# --- ENDPOINTS CRUD ---

@router.get("/", response_model=List[ActionResponse])
async def list_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "read"),
    risk_id: Optional[UUID] = Query(None, description="Filtrer par risque spécifique"),
    status_filter: Optional[ActionStatus] = Query(None, alias="status", description="Filtrer par statut"),
):
    """Liste toutes les actions, optionnellement filtrées par risque ou statut."""
    query = select(ActionItem).order_by(ActionItem.due_date.asc(), ActionItem.priority.desc())
    
    conditions = []
    if risk_id:
        conditions.append(ActionItem.risk_id == risk_id)
    if status_filter:
        conditions.append(ActionItem.status == status_filter)
        
    if conditions:
        query = query.where(and_(*conditions))
        
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action(
    data: ActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "create"),
):
    """Crée une nouvelle tâche corrective liée à un risque existant."""
    # 1. Vérifier que le risque existe
    risk_check = await db.execute(select(Risk).where(Risk.id == data.risk_id))
    risk = risk_check.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail=f"Risque ID={data.risk_id} introuvable.")
    
    # 2. Créer l'action
    action_dict = data.model_dump(exclude={"risk_id"})
    action = ActionItem(**action_dict, risk_id=data.risk_id)
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


@router.put("/{action_id}", response_model=ActionResponse)
async def update_action(
    action_id: UUID,
    data: ActionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "update"),
):
    """Met à jour une action existante (titre, statut, deadline...)."""
    result = await db.execute(select(ActionItem).where(ActionItem.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action non trouvée.")
    
    # Mise à jour partielle (exclude_unset évite d'écraser avec None)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(action, key, value)
        
    await db.commit()
    await db.refresh(action)
    return action


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "delete"),
):
    """Supprime définitivement une action."""
    result = await db.execute(select(ActionItem).where(ActionItem.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action non trouvée.")
    
    await db.delete(action)
    await db.commit()