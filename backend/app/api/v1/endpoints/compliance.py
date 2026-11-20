# backend/app/api/v1/endpoints/compliance.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.iso_control import IsoControl
from app.models.risk import Risk
from app.models.action_item import ActionItem, ActionStatus
from app.models.user import User

router = APIRouter(prefix="/compliance", tags=["Conformité ISO"])

class ComplianceMatrixRow(BaseModel):
    ref_code: str
    title: str
    domain: str
    status: str # "Couvert", "Partiel", "Non Couvert"
    linked_risks_count: int
    last_update: str | None
    
class MatrixResponse(BaseModel):
    total_controls: int
    covered_count: int
    partial_count: int
    uncovered_count: int
    overall_score: float # % global
    rows: List[ComplianceMatrixRow]

@router.get("/matrix", response_model=MatrixResponse)
async def get_compliance_matrix(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("iso27002", "read"),
):
    """Calcule la matrice de conformité ISO 27002 basée sur les risques et actions."""
    try:
        # 1. Fetch all controls
        ctrl_query = await db.execute(select(IsoControl))
        controls = ctrl_query.scalars().all()
        
        if not controls:
             return MatrixResponse(total_controls=0, covered_count=0, partial_count=0, uncovered_count=0, overall_score=0.0, rows=[])

        # 2. Fetch relevant risks/actions to determine coverage
        risk_query = await db.execute(select(Risk))
        risks = risk_query.scalars().all()
        
        action_query = await db.execute(select(ActionItem).where(ActionItem.status == ActionStatus.DONE))
        done_actions = action_query.scalars().all()
        
        rows = []
        covered = 0
        partial = 0
        uncovered = 0
        
        now_str = datetime.now().isoformat()
        
        for c in controls:
            ref = c.ref_code.lower().strip() # e.g., "a.8.9"
            found_links = 0
            has_done_action = False
            
            # Check manual override first
            if c.is_manually_covered:
                status = "Couvert"
                covered += 1
                rows.append(ComplianceMatrixRow(
                    ref_code=c.ref_code, title=c.title, domain=c.domain,
                    status=status, linked_risks_count=0, last_update=now_str
                ))
                continue
                
            # Search in Risks (Treatment Plan or Title)
            for r in risks:
                text_blob = f"{r.title} {getattr(r, 'treatment_plan', '')}".lower()
                if ref in text_blob:
                    found_links += 1
                    
            # Search in Done Actions (Title/Desc)
            for a in done_actions:
                text_blob = f"{a.title} {getattr(a, 'description', '')}".lower()
                if ref in text_blob:
                    has_done_action = True
            
            # Determine Status Logic
            if has_done_action:
                status = "Couvert"
                covered += 1
            elif found_links > 0:
                status = "Partiel" 
                partial += 1
            else:
                status = "Non Couvert"
                uncovered += 1
                
            rows.append(ComplianceMatrixRow(
                ref_code=c.ref_code, title=c.title, domain=c.domain,
                status=status, linked_risks_count=found_links, last_update=now_str
            ))
            
        total = len(rows)
        score = round((covered / total * 100), 1) if total > 0 else 0.0
        
        return MatrixResponse(
            total_controls=total,
            covered_count=covered,
            partial_count=partial,
            uncovered_count=uncovered,
            overall_score=score,
            rows=rows
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur calcul matrice: {str(e)}")