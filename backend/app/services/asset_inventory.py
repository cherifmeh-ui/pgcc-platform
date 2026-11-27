"""Shared query construction for the asset inventory."""
from app.models.asset import Asset


def build_asset_inventory_filters(
    *,
    q: str | None = None,
    asset_type: str | None = None,
    criticality: str | None = None,
    lifecycle_status: str | None = None,
    direction: str | None = None,
    owner: str | None = None,
    classification: str | None = None,
    location: str | None = None,
    include_retired: bool = False,
):
    """Build canonical filters shared by inventory listing and CSV export."""
    filters = []
    if not include_retired:
        filters.extend((
            Asset.retired_at.is_(None),
            Asset.lifecycle_status.notin_(("Retiré", "Décommissionné")),
        ))
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            Asset.name.ilike(pattern) | Asset.reference.ilike(pattern)
            | Asset.hostname.ilike(pattern) | Asset.fqdn.ilike(pattern)
        )
    if asset_type:
        filters.append(Asset.asset_type == asset_type)
    if criticality:
        filters.append(Asset.criticality == criticality)
    if lifecycle_status:
        filters.append(Asset.lifecycle_status == lifecycle_status)
    if direction and direction.strip():
        filters.append(Asset.direction.ilike(direction.strip()))
    if owner and owner.strip():
        filters.append(Asset.owner.ilike(f"%{owner.strip()}%"))
    if classification and classification.strip():
        filters.append(Asset.classification == classification)
    if location and location.strip():
        filters.append(Asset.location.ilike(f"%{location.strip()}%"))
    return filters
