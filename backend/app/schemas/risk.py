# backend/app/schemas/risk.py
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class RiskResponse(BaseModel):
    id: UUID
    ref: str
    title: str
    description: Optional[str] = Field(default=None, max_length=10000)
    threat: Optional[str] = Field(default=None, max_length=5000)
    impact: int
    likelihood: int
    risk_level: int
    site: Optional[str] = Field(default=None, max_length=100)
    owner_id: Optional[UUID] = None
    status: Optional[str] = None
    treatment_plan: Optional[str] = Field(default=None, max_length=10000)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class RiskCreate(BaseModel):
    ref: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = Field(default=None, max_length=10000)
    threat: Optional[str] = Field(default=None, max_length=5000)

    impact: int = Field(default=3, ge=1, le=5, strict=True)
    likelihood: int = Field(default=3, ge=1, le=5, strict=True)

    site: Optional[str] = Field(default=None, max_length=100)
    owner_id: Optional[UUID] = None
    status: str = Field(default="Ouvert", max_length=50, pattern=r"^(Ouvert|En traitement|Traité|Accepté)$")
    treatment_plan: Optional[str] = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_treatment_rationale(self):
        if self.status == "Accepté" and not (self.treatment_plan or "").strip():
            raise ValueError("Un risque accepté doit comporter une justification documentée dans le plan de traitement.")
        if self.status in {"En traitement", "Traité"} and not (self.treatment_plan or "").strip():
            raise ValueError("Un risque en traitement ou traité doit comporter un plan documenté.")
        return self


class RiskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=500)
    description: Optional[str] = Field(default=None, max_length=10000)
    threat: Optional[str] = Field(default=None, max_length=5000)

    impact: Optional[int] = Field(default=None, ge=1, le=5, strict=True)
    likelihood: Optional[int] = Field(default=None, ge=1, le=5, strict=True)

    site: Optional[str] = Field(default=None, max_length=100)
    owner_id: Optional[UUID] = None
    status: Optional[str] = Field(default=None, max_length=50, pattern=r"^(Ouvert|En traitement|Traité|Accepté)$")
    treatment_plan: Optional[str] = Field(default=None, max_length=10000)