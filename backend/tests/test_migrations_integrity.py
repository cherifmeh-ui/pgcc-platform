"""Static integrity checks for the Alembic revision graph.

These tests intentionally do not require a PostgreSQL instance. Database-backed
upgrade tests remain a separate Phase 0 gate.
"""
from __future__ import annotations

import ast
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _revision_metadata(path: Path) -> tuple[str, str | None]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    metadata: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                    metadata[target.id] = ast.literal_eval(node.value)
    revision = metadata.get("revision")
    down_revision = metadata.get("down_revision")
    assert isinstance(revision, str), f"{path.name}: missing revision"
    assert down_revision is None or isinstance(down_revision, str), (
        f"{path.name}: down_revision must be a string or None"
    )
    return revision, down_revision


def test_alembic_revision_graph_has_one_root_and_no_orphans() -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.py"))
    assert files, "No Alembic migration files found"

    revisions = [_revision_metadata(path) for path in files]
    revision_ids = [revision for revision, _ in revisions]
    assert len(revision_ids) == len(set(revision_ids)), "Duplicate revision IDs"

    roots = [revision for revision, parent in revisions if parent is None]
    assert roots == ["0001_initial"], f"Expected one baseline root, got {roots}"

    known = set(revision_ids)
    for path, (revision, parent) in zip(files, revisions):
        if parent is not None:
            assert parent in known, f"{path.name}: dangling parent {parent}"

    # The current repository intentionally maintains a single linear history.
    children: dict[str, list[str]] = {revision: [] for revision in known}
    for revision, parent in revisions:
        if parent is not None:
            children[parent].append(revision)
    for revision, child_revisions in children.items():
        assert len(child_revisions) <= 1, (
            f"Unexpected migration branch from {revision}: {child_revisions}"
        )


def test_baseline_downgrade_is_explicitly_non_destructive() -> None:
    baseline = MIGRATIONS_DIR / "0001_initial.py"
    source = baseline.read_text(encoding="utf-8")
    assert "def downgrade()" in source
    assert "NotImplementedError" in source
    assert "prevent accidental data loss" in source
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source

def test_asset_reference_migration_has_safe_duplicate_and_downgrade_guards() -> None:
    migration = MIGRATIONS_DIR / "0020_asset_reference_and_type_constraints.py"
    source = migration.read_text(encoding="utf-8")
    assert "lower(btrim(reference))" in source
    assert "ck_assets_reference_nonblank" in source
    assert "cloud_resource" in source
    assert "Cannot downgrade asset type constraint while cloud_resource assets exist" in source

def test_asset_reference_and_type_migration_has_valid_postgresql_downgrade_guard() -> None:
    migration = MIGRATIONS_DIR / "0020_asset_reference_and_type_constraints.py"
    source = migration.read_text(encoding="utf-8")
    assert "DO $pgcc$" in source
    assert "END $pgcc$;" in source
    assert "DO $\\n" not in source
    assert "cloud_resource" in source

def test_supplier_open_access_unique_index_matches_model_and_migration() -> None:
    migration = MIGRATIONS_DIR / "0016_supplier_access_requests.py"
    migration_source = migration.read_text(encoding="utf-8")
    model_source = (
        MIGRATIONS_DIR.parent.parent / "app" / "models" / "supplier.py"
    ).read_text(encoding="utf-8")

    index_name = "uq_supplier_access_requests_open_link"
    predicate = "status IN ('Demandé', 'Approuvé', 'Suspendu')"
    assert index_name in migration_source
    assert index_name in model_source
    assert predicate in migration_source
    assert predicate in model_source
    assert "unique=True" in model_source


def test_supplier_risk_snapshot_month_is_unique_in_model_and_migration() -> None:
    migration = MIGRATIONS_DIR / "0019_supplier_risk_snapshots.py"
    migration_source = migration.read_text(encoding="utf-8")
    model_source = (
        MIGRATIONS_DIR.parent.parent / "app" / "models" / "supplier.py"
    ).read_text(encoding="utf-8")

    constraint = "uq_supplier_risk_snapshots_month"
    assert constraint in migration_source
    assert constraint in model_source
    assert "snapshot_month" in migration_source
    assert "snapshot_month" in model_source


def test_refresh_token_sessions_migration_is_linked_and_revocable():
    migration = MIGRATIONS_DIR / "0021_refresh_token_sessions.py"
    source = migration.read_text(encoding="utf-8")
    assert 'revision = "0021_refresh_token_sessions"' in source
    assert 'down_revision = "0020_asset_reference_and_type_constraints"' in source
    assert "token_jti_hash" in source
    assert "revoked_at" in source
    assert "replaced_by_jti_hash" in source
    assert "expires_at" in source
    assert "ondelete=\"CASCADE\"" in source


def test_refresh_endpoint_uses_persisted_session_and_replay_revocation():
    endpoint = MIGRATIONS_DIR.parent.parent / "app" / "api" / "v1" / "endpoints" / "auth.py"
    source = endpoint.read_text(encoding="utf-8")
    assert "RefreshTokenSession" in source
    assert "with_for_update()" in source
    assert "reused" in source.lower() or "Réutilisation" in source
    assert "@router.post(\"/logout\"" in source


def test_refresh_token_hash_has_unique_constraint_without_redundant_index():
    migration = MIGRATIONS_DIR / "0021_refresh_token_sessions.py"
    source = migration.read_text(encoding="utf-8")
    assert 'sa.UniqueConstraint("token_jti_hash", name="uq_refresh_token_sessions_jti_hash")' in source
    assert 'op.create_index("ix_refresh_token_sessions_token_jti_hash"' not in source


def test_password_change_revokes_existing_refresh_sessions():
    endpoint = MIGRATIONS_DIR.parent.parent / "app" / "api" / "v1" / "endpoints" / "auth.py"
    source = endpoint.read_text(encoding="utf-8")
    change_password = source.split('@router.post("/change-password"', 1)[1].split('@router.post("/refresh"', 1)[0]
    assert "RefreshTokenSession.user_id == user.id" in change_password
    assert "revoked_at=user.password_changed_at" in change_password
