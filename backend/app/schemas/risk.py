# backend/app/schemas/risk.py
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RiskResponse(BaseModel):
    id: UUID
    ref: str
    title: str
    description: Optional[str] = None
    threat: Optional[str] = None
    impact: int
    likelihood: int
    risk_level: int
    site: Optional[str] = None
    owner_id: Optional[UUID] = None
    status: Optional[str] = None
    treatment_plan: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class RiskCreate(BaseModel):
    ref: str = Field(..., min_length=3, max_length=50)
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    threat: Optional[str] = None

    impact: int = Field(default=3, ge=1, le=5)
    likelihood: int = Field(default=3, ge=1, le=5)

    site: Optional[str] = None
    owner_id: Optional[UUID] = None
    status: str = Field(default="Ouvert", max_length=50)
    treatment_plan: Optional[str] = None


class RiskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=500)
    description: Optional[str] = None
    threat: Optional[str] = None

    impact: Optional[int] = Field(default=None, ge=1, le=5)
    likelihood: Optional[int] = Field(default=None, ge=1, le=5)

    site: Optional[str] = None
    owner_id: Optional[UUID] = None
    status: Optional[str] = Field(default=None, max_length=50)
    treatment_plan: Optional[str] = None