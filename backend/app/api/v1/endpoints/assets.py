"""Asset inventory and dependency graph API."""
from collections import deque
from datetime import date, datetime, timedelta, timezone
import csv
import io
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select, func, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased, load_only
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.asset import Asset, AssetRelationship, AssetRiskLink
from app.models.supplier import Supplier, SupplierAssetLink, SupplierAccessRequest
from app.models.risk import Risk
from app.models.application import Application
from app.models.user import User
from app.services.security_logger import enqueue_audit_event, log_action  # log_action retained for compatibility with existing tests
from app.services.asset_inventory import build_asset_inventory_filters
from app.utils.rbac import role_has_permission

router = APIRouter(prefix="/assets", tags=["Cartographie des actifs"])

MAX_ASSET_IMPORT_BYTES = 1_048_576
MAX_ASSET_IMPORT_ROWS = 5_000

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

    @field_validator("reference")
    @classmethod
    def normalize_reference(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("La référence ne peut pas être vide")
        return normalized
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

    @field_validator("reference")
    @classmethod
    def normalize_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("La référence ne peut pas être vide")
        return normalized
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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)




async def _would_create_dependency_cycle(db: AsyncSession, source_id: UUID, target_id: UUID) -> bool:
    """Return whether source -> target would close a cycle in the active dependency graph."""
    source_asset = aliased(Asset)
    target_asset = aliased(Asset)
    result = await db.execute(
        select(AssetRelationship.source_asset_id, AssetRelationship.target_asset_id)
        .join(source_asset, source_asset.id == AssetRelationship.source_asset_id)
        .join(target_asset, target_asset.id == AssetRelationship.target_asset_id)
        .where(
            AssetRelationship.relationship_type == "depends_on",
            source_asset.retired_at.is_(None),
            source_asset.lifecycle_status.notin_(("Retiré", "Décommissionné")),
            target_asset.retired_at.is_(None),
            target_asset.lifecycle_status.notin_(("Retiré", "Décommissionné")),
        )
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
    queue = deque([(source_asset_id, 0)])
    while queue:
        current, distance = queue.popleft()
        for dependent in reverse_graph.get(current, []):
            if dependent == source_asset_id or dependent in distances:
                continue
            distances[dependent] = distance + 1
            queue.append((dependent, distance + 1))
    return sorted(distances.items(), key=lambda item: (item[1], str(item[0])))


def _lifecycle_retirement_marker(status: str | None, current_retired_at: datetime | None) -> datetime | None:
    """Keep lifecycle status and retired_at consistent during explicit updates."""
    if status in {"Retiré", "Décommissionné"}:
        return current_retired_at or datetime.now(timezone.utc)
    if status is not None:
        return None
    return current_retired_at


def _relationship_assets_are_active(asset_rows: list[tuple[UUID, datetime | None, str]]) -> bool:
    """Require both endpoints to exist and be active according to retirement markers."""
    return len(asset_rows) == 2 and all(
        not _asset_is_retired(lifecycle_status, retired_at)
        for _, retired_at, lifecycle_status in asset_rows
    )


def _asset_is_retired(lifecycle_status: str, retired_at: datetime | None) -> bool:
    """Treat either lifecycle state or retirement marker as authoritative."""
    return lifecycle_status in {"Retiré", "Décommissionné"} or retired_at is not None


def _active_asset_filter():
    """SQL predicate for assets active in both lifecycle fields."""
    return (Asset.retired_at.is_(None), Asset.lifecycle_status.notin_(("Retiré", "Décommissionné")))


def _asset_allows_risk_link(lifecycle_status: str, retired_at: datetime | None) -> bool:
    """Only active, non-retired assets may be newly linked to risks."""
    return not _asset_is_retired(lifecycle_status, retired_at)


async def _ensure_application_exists(application_id: UUID | None, db: AsyncSession) -> None:
    if application_id is None:
        return
    result = await db.execute(select(Application.id).where(Application.id == application_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail="Application associée introuvable")


async def _ensure_asset_retirement_allowed(db: AsyncSession, asset_id: UUID) -> None:
    """Refuse retirement while supplier access requests or active supplier links remain."""
    open_access_result = await db.execute(
        select(SupplierAccessRequest.id)
        .where(
            SupplierAccessRequest.asset_id == asset_id,
            SupplierAccessRequest.status.in_(("Demandé", "Approuvé", "Suspendu")),
        )
        .limit(1)
    )
    if open_access_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Retrait impossible : une demande ou autorisation d'accès fournisseur "
                "est encore ouverte. Refusez, révoquez ou clôturez-la d'abord."
            ),
        )

    active_supplier_link_result = await db.execute(
        select(SupplierAssetLink.id)
        .where(
            SupplierAssetLink.asset_id == asset_id,
            SupplierAssetLink.status == "Actif",
        )
        .limit(1)
    )
    if active_supplier_link_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Retrait impossible : une relation fournisseur-actif est encore active. "
                "Terminez cette relation avant de retirer l'actif."
            ),
        )


@router.get("/import/template")
async def download_asset_csv_template(
    current_user: User = require_permission("assets", "read"),
):
    """Download a CSV template containing the supported asset fields."""
    columns = list(AssetFields.model_fields.keys())
    sample = {
        "reference": "ASSET-001", "name": "Serveur applicatif exemple", "asset_type": "hardware",
        "criticality": "Critique", "lifecycle_status": "Actif", "owner": "Direction Informatique",
        "direction": "DI", "location": "Datacenter", "hostname": "srv-app-01",
        "classification": "Confidentiel", "discovery_source": "Inventaire manuel",
    }
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerow(sample)
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="pgcc_assets_template.csv"'},
    )


@router.post("/import/preview")
async def preview_asset_csv_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "create"),
):
    """Validate a CSV inventory without writing to the database."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Veuillez fournir un fichier CSV")
    raw = await file.read(MAX_ASSET_IMPORT_BYTES + 1)
    if len(raw) > MAX_ASSET_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Fichier CSV limité à 1 Mo")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Le fichier doit être encodé en UTF-8")
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV vide ou en-tête manquant")
    normalized_headers = [
        name.strip() if isinstance(name, str) else ""
        for name in reader.fieldnames
    ]
    if any(not name for name in normalized_headers):
        raise HTTPException(status_code=422, detail="Le CSV contient un en-tête vide.")
    if len(normalized_headers) != len(set(normalized_headers)):
        raise HTTPException(status_code=422, detail="Le CSV contient des en-têtes dupliqués.")
    allowed = set(AssetFields.model_fields)
    unknown = [name for name in normalized_headers if name not in allowed]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Colonnes inconnues : {', '.join(unknown)}")
    rows = []
    errors = []
    invalid_row_numbers = set()
    parsed_row_count = 0
    seen_refs, seen_hostnames, seen_serials = set(), set(), set()
    for row_number, raw_row in enumerate(reader, start=2):
        if None in raw_row:
            errors.append({
                "row": row_number,
                "error": "Le nombre de colonnes dépasse celui de l'en-tête.",
            })
            invalid_row_numbers.add(row_number)
            continue
        values = {key.strip(): (value.strip() if isinstance(value, str) else value) for key, value in raw_row.items() if key}
        if not any(values.values()):
            continue
        parsed_row_count += 1
        if parsed_row_count > MAX_ASSET_IMPORT_ROWS:
            raise HTTPException(
                status_code=413,
                detail=f"Import CSV limité à {MAX_ASSET_IMPORT_ROWS} lignes de données.",
            )
        try:
            asset = AssetCreate.model_validate(values)
            normalized = asset.model_dump(mode="json")
            ref = asset.reference.casefold()
            hostname = (asset.hostname or "").casefold()
            serial = (asset.serial_number or "").casefold()
            if ref in seen_refs:
                raise ValueError("Référence dupliquée dans le fichier")
            if hostname and hostname in seen_hostnames:
                raise ValueError("Hostname dupliqué dans le fichier")
            if serial and serial in seen_serials:
                raise ValueError("Numéro de série dupliqué dans le fichier")
            seen_refs.add(ref)
            if hostname: seen_hostnames.add(hostname)
            if serial: seen_serials.add(serial)
            rows.append({"row": row_number, "data": normalized})
        except ValidationError as exc:
            # Pydantic's default string representation includes rejected input
            # values. Keep the preview response limited to field names and
            # validation messages so secrets accidentally pasted into a CSV
            # are not echoed back by the API.
            safe_errors = exc.errors(
                include_input=False,
                include_url=False,
                include_context=False,
            )
            message = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in safe_errors
            )
            errors.append({"row": row_number, "error": message})
            invalid_row_numbers.add(row_number)
        except ValueError as exc:
            errors.append({"row": row_number, "error": str(exc)})
            invalid_row_numbers.add(row_number)
    application_ids = {
        UUID(row["data"]["application_id"])
        for row in rows
        if row["data"].get("application_id")
    }
    if application_ids:
        application_result = await db.execute(
            select(Application.id).where(Application.id.in_(application_ids))
        )
        existing_application_ids = {
            str(application_id) for application_id in application_result.scalars().all()
        }
        for row in rows:
            application_id = row["data"].get("application_id")
            if application_id and application_id not in existing_application_ids:
                errors.append({
                    "row": row["row"],
                    "error": "Application associée introuvable",
                })
                invalid_row_numbers.add(row["row"])
    if rows:
        refs = [row["data"]["reference"] for row in rows]
        hostnames = [row["data"]["hostname"] for row in rows if row["data"].get("hostname")]
        serials = [row["data"]["serial_number"] for row in rows if row["data"].get("serial_number")]
        existing_result = await db.execute(
            select(Asset).where(
                (func.lower(Asset.reference).in_([v.casefold() for v in refs]))
                | (func.lower(Asset.hostname).in_([v.casefold() for v in hostnames]))
                | (func.lower(Asset.serial_number).in_([v.casefold() for v in serials]))
            )
        )
        existing = existing_result.scalars().all()
        for row in rows:
            data = row["data"]
            conflicts = []
            for asset in existing:
                if asset.reference.casefold() == data["reference"].casefold(): conflicts.append("référence déjà existante")
                if data.get("hostname") and asset.hostname and asset.hostname.casefold() == data["hostname"].casefold(): conflicts.append("hostname déjà existant")
                if data.get("serial_number") and asset.serial_number and asset.serial_number.casefold() == data["serial_number"].casefold(): conflicts.append("numéro de série déjà existant")
            if conflicts:
                errors.append({"row": row["row"], "error": "; ".join(sorted(set(conflicts)))})
                invalid_row_numbers.add(row["row"])
    valid_row_count = sum(1 for row in rows if row["row"] not in invalid_row_numbers)
    return {"filename": file.filename, "rows_valid": valid_row_count, "rows_parsed": parsed_row_count, "errors": errors, "preview": rows[:20], "validated_rows": rows, "can_import": parsed_row_count > 0 and not errors}


@router.post("/import/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_asset_csv_import(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "create"),
):
    """Revalidate and import CSV assets atomically; never overwrite existing assets."""
    preview = await preview_asset_csv_import(file=file, db=db, current_user=current_user)
    if not preview["can_import"]:
        raise HTTPException(status_code=422, detail={"message": "Import refusé : corrigez les erreurs de prévalidation.", "errors": preview["errors"]})
    rows = preview["validated_rows"]
    for row in rows:
        await _ensure_application_exists(row["data"].get("application_id"), db)
    assets = [
        Asset(
            **{
                **row["data"],
                "retired_at": _lifecycle_retirement_marker(row["data"].get("lifecycle_status"), None),
            }
        )
        for row in rows
    ]
    db.add_all(assets)
    try:
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action="IMPORT", resource="assets",
            details=f"CSV asset import completed: {len(assets)} assets from {file.filename}",
            event_type="ASSET", request=request,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Import annulé : conflit ou contrainte invalide. Aucun actif n'a été importé.")
    except Exception:
        await db.rollback()
        raise
    return {"imported": len(assets), "message": f"{len(assets)} actifs importés avec succès."}


@router.get("/graph")
async def get_asset_dependency_graph(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    """Return the active asset inventory and its explicit relationships for visualization."""
    # The graph is a read model: load only fields serialized in its response.
    # Avoid fetching long descriptions, technical identifiers and other inventory
    # columns for every node/edge when the graph is opened.
    assets_result = await db.execute(
        select(Asset)
        .options(load_only(
            Asset.id, Asset.reference, Asset.name, Asset.asset_type,
            Asset.criticality, Asset.direction, Asset.lifecycle_status,
            Asset.owner, Asset.location,
        ))
        .where(*_active_asset_filter())
        .order_by(Asset.name.asc(), Asset.reference.asc(), Asset.id.asc())
    )
    assets = assets_result.scalars().all()
    active_asset_ids = select(Asset.id).where(*_active_asset_filter())
    relations_result = await db.execute(
        select(AssetRelationship)
        .options(load_only(
            AssetRelationship.id, AssetRelationship.source_asset_id,
            AssetRelationship.target_asset_id, AssetRelationship.relationship_type,
            AssetRelationship.description,
        ))
        .where(
            AssetRelationship.source_asset_id.in_(active_asset_ids),
            AssetRelationship.target_asset_id.in_(active_asset_ids),
        )
        .order_by(
            AssetRelationship.source_asset_id.asc(),
            AssetRelationship.target_asset_id.asc(),
            AssetRelationship.id.asc(),
        )
    )
    relations = relations_result.scalars().all()
    return {
        "nodes": [{"id": asset.id, "reference": asset.reference, "name": asset.name, "asset_type": asset.asset_type, "criticality": asset.criticality, "direction": asset.direction, "lifecycle_status": asset.lifecycle_status, "owner": asset.owner, "location": asset.location} for asset in assets],
        "edges": [{"id": relation.id, "source": relation.source_asset_id, "target": relation.target_asset_id, "relationship_type": relation.relationship_type, "description": relation.description} for relation in relations],
        "node_count": len(assets), "edge_count": len(relations),
    }


@router.get("/page")
async def list_assets_page(
    q: str | None = Query(default=None, max_length=100),
    asset_type: AssetType | None = None,
    criticality: Level | None = None,
    lifecycle_status: Lifecycle | None = None,
    direction: str | None = Query(default=None, max_length=100),
    owner: str | None = Query(default=None, max_length=150),
    classification: str | None = Query(default=None, max_length=100),
    location: str | None = Query(default=None, max_length=200),
    include_retired: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    """Return a stable, count-bearing page of inventory records."""
    filters = build_asset_inventory_filters(
        q=q, asset_type=asset_type, criticality=criticality,
        lifecycle_status=lifecycle_status, direction=direction, owner=owner,
        classification=classification, location=location,
        include_retired=include_retired,
    )
    total_result = await db.execute(select(func.count(Asset.id)).where(*filters))
    total = total_result.scalar_one()
    stmt = (
        select(Asset).where(*filters)
        .order_by(Asset.name.asc(), Asset.reference.asc(), Asset.id.asc())
        .limit(page_size).offset((page - 1) * page_size)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


def _csv_safe_value(value):
    """Prevent spreadsheet formula execution when opening exported CSV files."""
    if value is None:
        return ""
    text_value = str(value)
    if text_value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text_value
    return text_value


@router.get("/export.csv")
async def export_assets_csv(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    asset_type: AssetType | None = None,
    criticality: Level | None = None,
    lifecycle_status: Lifecycle | None = None,
    direction: str | None = Query(default=None, max_length=100),
    owner: str | None = Query(default=None, max_length=150),
    classification: str | None = Query(default=None, max_length=100),
    location: str | None = Query(default=None, max_length=200),
    include_retired: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "export"),
):
    """Export the filtered inventory as UTF-8 CSV with spreadsheet formula protection."""
    filters = build_asset_inventory_filters(
        q=q, asset_type=asset_type, criticality=criticality,
        lifecycle_status=lifecycle_status, direction=direction, owner=owner,
        classification=classification, location=location,
        include_retired=include_retired,
    )
    result = await db.execute(
        select(Asset).where(*filters).order_by(Asset.name.asc(), Asset.reference.asc(), Asset.id.asc())
    )
    assets = result.scalars().all()
    columns = ["reference", "name", "asset_type", "owner", "custodian", "direction",
               "location", "lifecycle_status", "criticality", "confidentiality",
               "integrity", "availability", "classification", "application_id",
               "hostname", "ip_address", "fqdn", "operating_system", "version",
               "manufacturer", "model", "serial_number", "discovery_source",
               "source_reference", "last_inventory_date", "end_of_support_date",
               "retired_at"]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    for asset in assets:
        writer.writerow([_csv_safe_value(getattr(asset, column)) for column in columns])
    await log_action(
        user_email=current_user.email, action="EXPORT", resource="assets",
        details=f"CSV asset inventory export: {len(assets)} records",
        event_type="ASSET", request=request,
    )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="pgcc_assets_inventory.csv"'},
    )


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
        stmt = stmt.where(*_active_asset_filter())
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
    asset_data = data.model_dump()
    asset_data["retired_at"] = _lifecycle_retirement_marker(asset_data.get("lifecycle_status"), None)
    asset = Asset(**asset_data)
    db.add(asset)
    try:
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action="CREATE", resource="assets",
            resource_id=str(asset.id), details=f"Asset created: {asset.reference}",
            event_type="ASSET", request=request,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Référence d'actif déjà utilisée ou contrainte invalide")
    except Exception:
        await db.rollback()
        raise
    await db.refresh(asset)
    return asset


@router.get("/quality")
async def get_asset_inventory_quality(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    """Return completeness and lifecycle indicators for the active inventory."""
    now = datetime.now(timezone.utc)
    now_plus_90_days = now + timedelta(days=90)
    active_filter = _active_asset_filter()
    result = await db.execute(
        select(
            func.count(Asset.id).label("total_active"),
            func.coalesce(
                func.sum(case((func.coalesce(func.btrim(Asset.owner), "") == "", 1), else_=0)), 0
            ).label("missing_owner"),
            func.coalesce(
                func.sum(case((func.coalesce(func.btrim(Asset.classification), "") == "", 1), else_=0)), 0
            ).label("missing_classification"),
            func.coalesce(
                func.sum(case((Asset.last_inventory_date.is_(None), 1), else_=0)), 0
            ).label("missing_inventory_date"),
            func.coalesce(
                func.sum(case((func.coalesce(func.btrim(Asset.criticality), "") == "", 1), else_=0)), 0
            ).label("missing_criticality"),
            func.coalesce(
                func.sum(case((func.coalesce(func.btrim(Asset.direction), "") == "", 1), else_=0)), 0
            ).label("missing_direction"),
            func.coalesce(
                func.sum(case((Asset.end_of_support_date < now, 1), else_=0)), 0
            ).label("support_overdue"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Asset.end_of_support_date.between(now, now_plus_90_days),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("support_ending_90_days"),
        ).where(*active_filter)
    )
    (
        total,
        missing_owner,
        missing_classification,
        missing_inventory_date,
        missing_criticality,
        missing_direction,
        overdue_support,
        support_ending_90_days,
    ) = result.one()
    return {
        "total_active": total,
        "missing_owner": missing_owner,
        "missing_classification": missing_classification,
        "missing_inventory_date": missing_inventory_date,
        "missing_criticality": missing_criticality,
        "missing_direction": missing_direction,
        "support_overdue": overdue_support,
        "support_ending_90_days": support_ending_90_days,
        "completeness_percent": round(100 * (total * 5 - missing_owner - missing_classification - missing_inventory_date - missing_criticality - missing_direction) / (total * 5), 1) if total else 100.0,
    }


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
    result = await db.execute(select(Asset).where(Asset.id == asset_id).with_for_update())
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    values = data.model_dump(exclude_unset=True)
    if "application_id" in values:
        await _ensure_application_exists(values.get("application_id"), db)
    if values.get("lifecycle_status") in {"Retiré", "Décommissionné"}:
        await _ensure_asset_retirement_allowed(db, asset.id)

    was_retired = _asset_is_retired(asset.lifecycle_status, asset.retired_at)
    reactivated = False
    if "lifecycle_status" in values:
        new_status = values["lifecycle_status"]
        new_retired_at = _lifecycle_retirement_marker(new_status, asset.retired_at)
        reactivated = was_retired and not _asset_is_retired(new_status, new_retired_at)
        values["retired_at"] = new_retired_at

    for key, value in values.items():
        setattr(asset, key, value)
    audit_action = "REACTIVATE" if reactivated else "UPDATE"
    audit_details = (
        f"Asset reactivated: {asset.reference} (new status: {asset.lifecycle_status})"
        if reactivated else f"Asset updated: {asset.reference}"
    )
    try:
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action=audit_action, resource="assets",
            resource_id=str(asset.id), details=audit_details,
            event_type="ASSET", request=request,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Référence d'actif déjà utilisée ou contrainte invalide")
    except Exception:
        await db.rollback()
        raise
    await db.refresh(asset)
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_asset(
    asset_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "delete"),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id).with_for_update())
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")

    await _ensure_asset_retirement_allowed(db, asset.id)

    if asset.lifecycle_status not in {"Retiré", "Décommissionné"} or asset.retired_at is None:
        if asset.retired_at is None:
            asset.retired_at = datetime.now(timezone.utc)
        if asset.lifecycle_status not in {"Retiré", "Décommissionné"}:
            asset.lifecycle_status = "Retiré"
        try:
            await db.flush()
            await enqueue_audit_event(
                db, user_email=current_user.email, action="RETIRE", resource="assets",
                resource_id=str(asset.id), details=f"Asset retired: {asset.reference}",
                event_type="ASSET", request=request,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise




@router.get("/{asset_id}/impact")
async def get_asset_impact(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    """Return transitive assets depending on the selected asset and their linked risks."""
    source_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    source = source_result.scalar_one_or_none()
    if source is None or _asset_is_retired(source.lifecycle_status, source.retired_at):
        raise HTTPException(status_code=404, detail="Actif actif introuvable")
    dependent_asset = aliased(Asset)
    dependency_asset = aliased(Asset)
    rel_result = await db.execute(
        select(AssetRelationship.source_asset_id, AssetRelationship.target_asset_id)
        .join(dependent_asset, dependent_asset.id == AssetRelationship.source_asset_id)
        .join(dependency_asset, dependency_asset.id == AssetRelationship.target_asset_id)
        .where(
            AssetRelationship.relationship_type == "depends_on",
            dependent_asset.retired_at.is_(None),
            dependent_asset.lifecycle_status.notin_(("Retiré", "Décommissionné")),
            dependency_asset.retired_at.is_(None),
            dependency_asset.lifecycle_status.notin_(("Retiré", "Décommissionné")),
        )
    )
    impacted = _compute_asset_impact(asset_id, rel_result.all())
    impacted_ids = [item[0] for item in impacted]
    supplier_links_by_asset: dict[UUID, list[dict]] = {}
    supplier_summary = {"total_suppliers": 0, "active_relationships": 0, "declared_privileged_relationships": 0, "declared_data_access_relationships": 0, "active_authorizations": 0, "authorized_privileged_access": 0, "authorized_data_access": 0}
    authorized_access_by_asset: dict[UUID, list[dict]] = {}
    supplier_access_available = role_has_permission((current_user.role or "").strip().lower(), "suppliers", "read_assets")
    if supplier_access_available:
        relevant_asset_ids = [asset_id, *impacted_ids]
        supplier_result = await db.execute(
            select(
                SupplierAssetLink.asset_id, Supplier.id, Supplier.code, Supplier.legal_name,
                SupplierAssetLink.relationship_type, SupplierAssetLink.access_level,
                SupplierAssetLink.data_access, SupplierAssetLink.status, SupplierAssetLink.review_due_at,
            )
            .join(Supplier, Supplier.id == SupplierAssetLink.supplier_id)
            .where(
                SupplierAssetLink.asset_id.in_(relevant_asset_ids),
                SupplierAssetLink.status == "Actif",
                Supplier.archived_at.is_(None),
                Supplier.status != "Terminé",
            )
        )
        unique_suppliers: set[UUID] = set()
        for asset_link_id, supplier_id, supplier_code, supplier_name, relationship, access_level, data_access, link_status, review_due_at in supplier_result.all():
            supplier_links_by_asset.setdefault(asset_link_id, []).append({
                "supplier_id": supplier_id, "supplier_code": supplier_code,
                "supplier_name": supplier_name, "relationship_type": relationship,
                "access_level": access_level, "data_access": data_access,
                "status": link_status, "review_due_at": review_due_at,
            })
            unique_suppliers.add(supplier_id)
            supplier_summary["active_relationships"] += 1
            if access_level == "Privilégié":
                supplier_summary["declared_privileged_relationships"] += 1
            if data_access:
                supplier_summary["declared_data_access_relationships"] += 1
        supplier_summary["total_suppliers"] = len(unique_suppliers)
        today = date.today()
        authorization_result = await db.execute(
            select(
                SupplierAccessRequest.asset_id, Supplier.id, Supplier.code, Supplier.legal_name,
                SupplierAccessRequest.id, SupplierAccessRequest.access_level,
                SupplierAccessRequest.data_access, SupplierAccessRequest.start_date,
                SupplierAccessRequest.end_date, SupplierAccessRequest.review_due_at,
            )
            .join(Supplier, Supplier.id == SupplierAccessRequest.supplier_id)
            .where(
                SupplierAccessRequest.asset_id.in_(relevant_asset_ids),
                SupplierAccessRequest.status == "Approuvé",
                SupplierAccessRequest.start_date <= today,
                SupplierAccessRequest.end_date >= today,
                Supplier.archived_at.is_(None),
                Supplier.status != "Terminé",
            )
        )
        for linked_asset_id, supplier_id, supplier_code, supplier_name, authorization_id, access_level, data_access, start_date, end_date, review_due_at in authorization_result.all():
            authorized_access_by_asset.setdefault(linked_asset_id, []).append({
                "authorization_id": authorization_id, "supplier_id": supplier_id,
                "supplier_code": supplier_code, "supplier_name": supplier_name,
                "access_level": access_level, "data_access": data_access,
                "start_date": start_date, "end_date": end_date, "review_due_at": review_due_at,
                "status": "Approuvé",
            })
            supplier_summary["active_authorizations"] += 1
            if access_level == "Privilégié":
                supplier_summary["authorized_privileged_access"] += 1
            if data_access:
                supplier_summary["authorized_data_access"] += 1
    source_suppliers = supplier_links_by_asset.get(asset_id, [])
    source_authorizations = authorized_access_by_asset.get(asset_id, [])
    if not impacted:
        empty_summary = {"total": 0, "unacceptable": 0, "critical": 0, "high": 0, "moderate": 0, "low": 0, "by_status": {}}
        return {
            "source": {"id": source.id, "reference": source.reference, "name": source.name, "linked_suppliers": source_suppliers, "active_supplier_authorizations": source_authorizations},
            "impacted_assets": [], "total_impacted": 0, "risk_summary": empty_summary,
            "supplier_summary": supplier_summary, "supplier_access_available": supplier_access_available,
        }
    asset_result = await db.execute(select(Asset).where(Asset.id.in_(impacted_ids)))
    assets_by_id = {asset.id: asset for asset in asset_result.scalars().all()}
    risks_by_asset: dict[UUID, list[dict]] = {}
    risk_summary = {"total": 0, "unacceptable": 0, "critical": 0, "high": 0, "moderate": 0, "low": 0, "by_status": {}}
    if role_has_permission((current_user.role or "").strip().lower(), "risks", "read"):
        risk_result = await db.execute(
            select(AssetRiskLink.asset_id, Risk.id, Risk.ref, Risk.title, Risk.risk_level, Risk.status)
            .join(Risk, Risk.id == AssetRiskLink.risk_id)
            .where(AssetRiskLink.asset_id.in_(impacted_ids))
        )
        unique_risks: dict[UUID, dict] = {}
        for linked_asset_id, risk_id, risk_ref, risk_title, risk_level, risk_status in risk_result.all():
            risks_by_asset.setdefault(linked_asset_id, []).append({
                "id": risk_id, "ref": risk_ref, "title": risk_title,
                "risk_level": risk_level, "status": risk_status,
            })
            unique_risks[risk_id] = {"risk_level": risk_level, "status": risk_status}
        risk_summary["total"] = len(unique_risks)
        for risk in unique_risks.values():
            level = risk["risk_level"]
            bucket = "unacceptable" if level >= 20 else "critical" if level >= 15 else "high" if level >= 10 else "moderate" if level >= 5 else "low"
            risk_summary[bucket] += 1
            status_key = str(risk["status"] or "Non renseigné")
            risk_summary["by_status"][status_key] = risk_summary["by_status"].get(status_key, 0) + 1
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
            "linked_suppliers": supplier_links_by_asset.get(asset.id, []),
            "active_supplier_authorizations": authorized_access_by_asset.get(asset.id, []),
        })
    return {
        "source": {"id": source.id, "reference": source.reference, "name": source.name, "linked_suppliers": source_suppliers, "active_supplier_authorizations": source_authorizations},
        "impacted_assets": results, "total_impacted": len(results), "risk_summary": risk_summary,
        "supplier_summary": supplier_summary, "supplier_access_available": supplier_access_available,
    }


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
        raise HTTPException(status_code=422, detail="Un actif ne peut pas être lié à lui-même")

    # Serialize dependency-edge creation to prevent cycles from disjoint concurrent edges.
    if data.relationship_type == "depends_on":
        await db.execute(select(func.pg_advisory_xact_lock(736291, 1)))
    # Lock endpoint rows in deterministic order to serialize lifecycle changes.
    locked_assets = await db.execute(
        select(Asset.id, Asset.retired_at, Asset.lifecycle_status)
        .where(Asset.id.in_([asset_id, data.target_asset_id]))
        .order_by(Asset.id)
        .with_for_update()
    )
    asset_rows = locked_assets.all()
    if len(asset_rows) != 2:
        raise HTTPException(status_code=404, detail="Actif source ou cible introuvable")
    if not _relationship_assets_are_active(asset_rows):
        raise HTTPException(status_code=409, detail="Les relations ne peuvent pas être créées sur un actif retiré")

    if data.relationship_type == "depends_on" and await _would_create_dependency_cycle(db, asset_id, data.target_asset_id):
        raise HTTPException(status_code=422, detail="Cette relation créerait un cycle de dépendances")
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
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action="CREATE_RELATIONSHIP", resource="asset_relationships",
            resource_id=str(relationship.id),
            details=f"Asset relationship created: {asset_id} -> {data.target_asset_id}",
            event_type="ASSET", request=request,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Relation déjà existante ou contrainte invalide")
    except Exception:
        await db.rollback()
        raise
    await db.refresh(relationship)
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
    try:
        await db.delete(relationship)
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action="DELETE_RELATIONSHIP", resource="asset_relationships",
            resource_id=str(relationship.id),
            details=f"Asset relationship deleted: {relationship.source_asset_id} -> {relationship.target_asset_id}",
            event_type="ASSET", request=request,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise


@router.get("/{asset_id}/risks", response_model=list[AssetRiskLinkResponse])
async def list_asset_risk_links(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "read"),
):
    if not role_has_permission((current_user.role or "").strip().lower(), "risks", "read"):
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
    if not role_has_permission((current_user.role or "").strip().lower(), "risks", "update"):
        raise HTTPException(status_code=403, detail="Accès refusé : permission risks:update requise.")
    asset_result = await db.execute(select(Asset).where(Asset.id == asset_id).with_for_update())
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    if not _asset_allows_risk_link(asset.lifecycle_status, asset.retired_at):
        raise HTTPException(status_code=409, detail="Impossible d'associer un risque à un actif retiré ou décommissionné")
    risk_result = await db.execute(select(Risk).where(Risk.id == data.risk_id).with_for_update())
    risk = risk_result.scalar_one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risque introuvable")
    link = AssetRiskLink(asset_id=asset_id, risk_id=data.risk_id, relationship_context=data.relationship_context, created_by=current_user.email)
    db.add(link)
    try:
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action="LINK_RISK", resource="asset_risk_links",
            resource_id=str(link.id),
            details=f"Asset {asset.reference} linked to risk {risk.ref}",
            event_type="ASSET_RISK", request=request,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Association actif/risque déjà existante ou contrainte invalide")
    except Exception:
        await db.rollback()
        raise
    await db.refresh(link)
    return link


@router.delete("/{asset_id}/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_asset_from_risk(
    asset_id: UUID,
    risk_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("assets", "update"),
):
    if not role_has_permission((current_user.role or "").strip().lower(), "risks", "update"):
        raise HTTPException(status_code=403, detail="Accès refusé : permission risks:update requise.")
    asset_result = await db.execute(select(Asset.id).where(Asset.id == asset_id))
    if asset_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    risk_result = await db.execute(select(Risk.id).where(Risk.id == risk_id))
    if risk_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Risque introuvable")
    result = await db.execute(select(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id, AssetRiskLink.risk_id == risk_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Association actif/risque introuvable")
    try:
        await db.delete(link)
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action="UNLINK_RISK", resource="asset_risk_links",
            resource_id=f"{asset_id}:{risk_id}", details="Asset-risk association removed",
            event_type="ASSET_RISK", request=request,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
