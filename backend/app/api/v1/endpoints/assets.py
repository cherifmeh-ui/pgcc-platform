"""Asset inventory and dependency graph API."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.asset import Asset, AssetRelationship, AssetRiskLink
from app.models.risk import Risk
from app.models.application import Application
from app.models.user import User
from app.services.security_logger import log_action
from app.utils.rbac import role_has_permission

router = APIRouter(prefix="/assets", tags=["Cartographie des actifs"])

AssetType = Literal[
    "process", "information", "application", "hardware", "software",
    "infrastructure", "network", "service", "cloud_resource", "facility", "other",
]
Level = Literal["Faible", "Moyenne", "Élevée", "Critique"]
Lifecycle = Literal["Identifié", "Actif", "En maintenance", "En projet", "Retiré", "Décommissionné"]
RelationshipType = Literal[
    "depends_on", "hosts", "connects_to", "stores", "processes", "supports",
    "contains", "communicates_with", "supplied_by", "other",
]


class AssetFields(BaseModel):
    reference: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    asset_type: AssetType = "other"
    application_id: UUID | None = None
    owner: str | None = Field(default=None, max_length=150)
    custodian: str | None = Field(default=None, max_length=150)
    direction: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    lifecycle_status: Lifecycle = "Identifié"
    criticality: Level = "Moyenne"
    confidentiality: Level | None = None
    integrity: Level | None = None
    availability: Level | None = None
    classification: str | None = Field(default=None, max_length=100)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    fqdn: str | None = Field(default=None, max_length=255)
    operating_system: str | None = Field(default=None, max_length=150)
    version: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    discovery_source: str | None = Field(default=None, max_length=100)
    source_reference: str | None = Field(default=None, max_length=255)
    last_inventory_date: datetime | None = None
    end_of_support_date: datetime | None = None
    comment: str | None = None


class AssetCreate(AssetFields):
    pass


class AssetUpdate(BaseModel):
    reference: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    asset_type: AssetType | None = None
    application_id: UUID | None = None
    owner: str | None = Field(default=None, max_length=150)
    custodian: str | None = Field(default=None, max_length=150)
    direction: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    lifecycle_status: Lifecycle | None = None
    criticality: Level | None = None
    confidentiality: Level | None = None
    integrity: Level | None = None
    availability: Level | None = None
    classification: str | None = Field(default=None, max_length=100)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    fqdn: str | None = Field(default=None, max_length=255)
    operating_system: str | None = Field(default=None, max_length=150)
    version: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    discovery_source: str | None = Field(default=None, max_length=100)
    source_reference: str | None = Field(default=None, max_length=255)
    last_inventory_date: datetime | None = None
    end_of_support_date: datetime | None = None
    comment: str | None = None


class AssetResponse(AssetFields):
    id: UUID
    created_at: datetime
    updated_at: datetime
    retired_at: datetime | None

    class Config:
        from_attributes = True


class AssetRiskLinkCreate(BaseModel):
    risk_id: UUID
    relationship_context: str | None = Field(default=None, max_length=500)


class AssetRiskLinkResponse(BaseModel):
    id: UUID
    asset_id: UUID
    risk_id: UUID
    relationship_context: str | None
    created_at: datetime
    created_by: str | None

    class Config:
        from_attributes = True


class RelationshipCreate(BaseModel):
    target_asset_id: UUID
    relationship_type: RelationshipType
    description: str | None = Field(default=None, max_length=500)
    criticality: Level | None = None


class RelationshipResponse(BaseModel):
    id: UUID
    source_asset_id: UUID
    target_asset_id: UUID
    relationship_type: RelationshipType
    description: str | None
    criticality: Level | None
    created_at: datetime
    created_by: str | None

    class Config:
        from_attributes = True




async def _would_create_dependency_cycle(db: AsyncSession, source_id: UUID, target_id: UUID) -> bool:
    """Return whether source -> target would close a depends_on cycle."""
    result = await db.execute(
        select(AssetRelationship.source_asset_id, AssetRelationship.target_asset_id)
        .where(AssetRelationship.relationship_type == "depends_on")
    )
    graph: dict[UUID, list[UUID]] = {}
    for source, target in result.all():
        graph.setdefault(source, []).append(target)
    pending = [target_id]
    visited: set[UUID] = set()
    while pending:
        node = pending.pop()
        if node == source_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        pending.extend(graph.get(node, []))
    return False




def _compute_asset_impact(source_asset_id: UUID, dependency_pairs: list[tuple[UUID, UUID]]) -> list[tuple[UUID, int]]:
    """Find assets that transitively depend on source; nearest dependents first."""
    reverse_graph: dict[UUID, list[UUID]] = {}
    for dependent_id, dependency_id in dependency_pairs:
        reverse_graph.setdefault(dependency_id, []).append(dependent_id)
    distances: dict[UUID, int] = {}
    queue: list[tuple[UUID, int]] = [(source_asset_id, 0)]
    while queue:
        current, distance = queue.pop(0)
        for dependent in reverse_graph.get(current, []):
            if dependent == source_asset_id or dependent in distances:
                continue
            distances[dependent] = distance + 1
            queue.append((dependent, distance + 1))
    return sorted(distances.items(), key=lambda item: (item[1], str(item[0])))


async def _ensure_application_exists(application_id: UUID | None, db: AsyncSession) -> None:
    if application_id is None:
        return
    result = await db.execute(select(Application.id).where(Application.id == application_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail="Application associée introuvable")


@router.get("/graph")
async def get_asset_dependency_graph(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    """Return the active asset inventory and its explicit relationships for visualization."""
    assets_result = await db.execute(select(Asset).where(Asset.retired_at.is_(None)).order_by(Asset.name.asc()))
    assets = assets_result.scalars().all()
    relations_result = await db.execute(select(AssetRelationship).order_by(AssetRelationship.created_at.asc()))
    asset_ids = {asset.id for asset in assets}
    relations = [relation for relation in relations_result.scalars().all() if relation.source_asset_id in asset_ids and relation.target_asset_id in asset_ids]
    return {
        "nodes": [{"id": asset.id, "reference": asset.reference, "name": asset.name, "asset_type": asset.asset_type, "criticality": asset.criticality, "direction": asset.direction, "lifecycle_status": asset.lifecycle_status, "owner": asset.owner, "location": asset.location} for asset in assets],
        "edges": [{"id": relation.id, "source": relation.source_asset_id, "target": relation.target_asset_id, "relationship_type": relation.relationship_type, "description": relation.description} for relation in relations],
        "node_count": len(assets), "edge_count": len(relations),
    }


@router.get("/", response_model=list[AssetResponse])
async def list_assets(
    q: str | None = Query(default=None, max_length=100),
    asset_type: AssetType | None = None,
    criticality: Level | None = None,
    lifecycle_status: Lifecycle | None = None,
    direction: str | None = Query(default=None, max_length=100),
    include_retired: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    stmt = select(Asset)
    if not include_retired:
        stmt = stmt.where(Asset.retired_at.is_(None))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(Asset.name.ilike(pattern) | Asset.reference.ilike(pattern) | Asset.hostname.ilike(pattern))
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if criticality:
        stmt = stmt.where(Asset.criticality == criticality)
    if lifecycle_status:
        stmt = stmt.where(Asset.lifecycle_status == lifecycle_status)
    if direction:
        stmt = stmt.where(Asset.direction == direction)
    stmt = stmt.order_by(Asset.name.asc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    data: AssetCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "create"),
):
    await _ensure_application_exists(data.application_id, db)
    asset = Asset(**data.model_dump())
    db.add(asset)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Référence d'actif déjà utilisée ou contrainte invalide")
    await db.refresh(asset)
    await log_action(
        user_email=current_user.email, action="CREATE", resource="assets",
        resource_id=str(asset.id), details=f"Asset created: {asset.reference}",
        event_type="ASSET", request=request,
    )
    return asset


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    return asset


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: UUID,
    data: AssetUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "update"),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    values = data.model_dump(exclude_unset=True)
    await _ensure_application_exists(values.get("application_id"), db)
    for key, value in values.items():
        setattr(asset, key, value)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Référence d'actif déjà utilisée ou contrainte invalide")
    await db.refresh(asset)
    await log_action(
        user_email=current_user.email, action="UPDATE", resource="assets",
        resource_id=str(asset.id), details=f"Asset updated: {asset.reference}",
        event_type="ASSET", request=request,
    )
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_asset(
    asset_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "delete"),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    if asset.retired_at is None:
        asset.retired_at = datetime.now(timezone.utc)
        asset.lifecycle_status = "Retiré"
        await db.commit()
        await log_action(
            user_email=current_user.email, action="RETIRE", resource="assets",
            resource_id=str(asset.id), details=f"Asset retired: {asset.reference}",
            event_type="ASSET", request=request,
        )




@router.get("/{asset_id}/impact")
async def get_asset_impact(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    """Return transitive assets depending on the selected asset and their linked risks."""
    source_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    source = source_result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    rel_result = await db.execute(
        select(AssetRelationship.source_asset_id, AssetRelationship.target_asset_id)
        .where(AssetRelationship.relationship_type == "depends_on")
    )
    impacted = _compute_asset_impact(asset_id, rel_result.all())
    if not impacted:
        return {"source": {"id": source.id, "reference": source.reference, "name": source.name}, "impacted_assets": [], "total_impacted": 0}
    impacted_ids = [item[0] for item in impacted]
    asset_result = await db.execute(select(Asset).where(Asset.id.in_(impacted_ids)))
    assets_by_id = {asset.id: asset for asset in asset_result.scalars().all()}
    risks_by_asset: dict[UUID, list[dict]] = {}
    if role_has_permission((current_user.role or "").lower(), "risks", "read"):
        risk_result = await db.execute(
            select(AssetRiskLink.asset_id, Risk.id, Risk.ref, Risk.title)
            .join(Risk, Risk.id == AssetRiskLink.risk_id)
            .where(AssetRiskLink.asset_id.in_(impacted_ids))
        )
        for linked_asset_id, risk_id, risk_ref, risk_title in risk_result.all():
            risks_by_asset.setdefault(linked_asset_id, []).append({"id": risk_id, "ref": risk_ref, "title": risk_title})
    results = []
    for impacted_id, distance in impacted:
        asset = assets_by_id.get(impacted_id)
        if asset is None:
            continue
        results.append({
            "id": asset.id, "reference": asset.reference, "name": asset.name,
            "asset_type": asset.asset_type, "criticality": asset.criticality,
            "lifecycle_status": asset.lifecycle_status, "owner": asset.owner,
            "direction": asset.direction, "application_id": asset.application_id,
            "dependency_distance": distance, "linked_risks": risks_by_asset.get(asset.id, []),
        })
    return {"source": {"id": source.id, "reference": source.reference, "name": source.name}, "impacted_assets": results, "total_impacted": len(results)}


@router.get("/{asset_id}/relationships", response_model=list[RelationshipResponse])
async def list_asset_relationships(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    result = await db.execute(select(Asset.id).where(Asset.id == asset_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    stmt = select(AssetRelationship).where(
        (AssetRelationship.source_asset_id == asset_id)
        | (AssetRelationship.target_asset_id == asset_id)
    ).order_by(AssetRelationship.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{asset_id}/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_relationship(
    asset_id: UUID,
    data: RelationshipCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "update"),
):
    if asset_id == data.target_asset_id:
        raise HTTPException(status_code=422, detail="Un actif ne peut pas dépendre de lui-même")
    if data.relationship_type == "depends_on" and await _would_create_dependency_cycle(db, asset_id, data.target_asset_id):
        raise HTTPException(status_code=422, detail="Cette relation créerait un cycle de dépendances")
    result = await db.execute(select(Asset.id).where(Asset.id.in_([asset_id, data.target_asset_id]))
    )
    if len(result.scalars().all()) != 2:
        raise HTTPException(status_code=404, detail="Actif source ou cible introuvable")
    relationship = AssetRelationship(
        source_asset_id=asset_id,
        target_asset_id=data.target_asset_id,
        relationship_type=data.relationship_type,
        description=data.description,
        criticality=data.criticality,
        created_by=current_user.email,
    )
    db.add(relationship)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Relation déjà existante ou contrainte invalide")
    await db.refresh(relationship)
    await log_action(
        user_email=current_user.email, action="CREATE_RELATIONSHIP", resource="asset_relationships",
        resource_id=str(relationship.id), details=f"Asset relationship created: {asset_id} -> {data.target_asset_id}",
        event_type="ASSET", request=request,
    )
    return relationship


@router.delete("/{asset_id}/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_relationship(
    asset_id: UUID,
    relationship_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "update"),
):
    result = await db.execute(
        select(AssetRelationship).where(
            AssetRelationship.id == relationship_id,
            (AssetRelationship.source_asset_id == asset_id) | (AssetRelationship.target_asset_id == asset_id),
        )
    )
    relationship = result.scalar_one_or_none()
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relation introuvable pour cet actif")
    await db.delete(relationship)
    await db.commit()
    await log_action(
        user_email=current_user.email, action="DELETE_RELATIONSHIP", resource="asset_relationships",
        resource_id=str(relationship.id), details=f"Asset relationship deleted: {relationship.source_asset_id} -> {relationship.target_asset_id}",
        event_type="ASSET", request=request,
    )


@router.get("/{asset_id}/risks", response_model=list[AssetRiskLinkResponse])
async def list_asset_risk_links(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    if not role_has_permission((current_user.role or "").lower(), "risks", "read"):
        raise HTTPException(status_code=403, detail="Accès refusé : permission risks:read requise.")
    asset_result = await db.execute(select(Asset.id).where(Asset.id == asset_id))
    if asset_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    result = await db.execute(
        select(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id).order_by(AssetRiskLink.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{asset_id}/risks", response_model=AssetRiskLinkResponse, status_code=status.HTTP_201_CREATED)
async def link_asset_to_risk(
    asset_id: UUID,
    data: AssetRiskLinkCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "update"),
):
    asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    risk_result = await db.execute(select(Risk).where(Risk.id == data.risk_id))
    risk = risk_result.scalar_one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risque introuvable")
    link = AssetRiskLink(asset_id=asset_id, risk_id=data.risk_id, relationship_context=data.relationship_context, created_by=current_user.email)
    db.add(link)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Association actif/risque déjà existante ou contrainte invalide")
    await db.refresh(link)
    await log_action(user_email=current_user.email, action="LINK_RISK", resource="asset_risk_links", resource_id=str(link.id), details=f"Asset {asset.reference} linked to risk {risk.ref}", event_type="ASSET_RISK", request=request)
    return link


@router.delete("/{asset_id}/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_asset_from_risk(
    asset_id: UUID,
    risk_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "update"),
):
    result = await db.execute(select(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id, AssetRiskLink.risk_id == risk_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Association actif/risque introuvable")
    await db.delete(link)
    await db.commit()
    await log_action(user_email=current_user.email, action="UNLINK_RISK", resource="asset_risk_links", resource_id=f"{asset_id}:{risk_id}", details="Asset-risk association removed", event_type="ASSET_RISK", request=request)
