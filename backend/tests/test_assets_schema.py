import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.assets import AssetCreate, AssetUpdate, RelationshipCreate
from app.models.asset import Asset, AssetRelationship, AssetRiskLink


def test_asset_create_accepts_application_link_and_classification():
    payload = AssetCreate(
        reference="AST-001",
        name="Serveur applicatif",
        asset_type="hardware",
        criticality="Critique",
        application_id="00000000-0000-0000-0000-000000000001",
        confidentiality="Élevée",
        integrity="Critique",
        availability="Critique",
    )
    assert payload.asset_type == "hardware"
    assert payload.criticality == "Critique"


def test_asset_create_rejects_invalid_type_or_criticality():
    with pytest.raises(ValidationError):
        AssetCreate(reference="AST-002", name="Invalid", asset_type="unknown")
    with pytest.raises(ValidationError):
        AssetCreate(reference="AST-003", name="Invalid", criticality="Unknown")


def test_asset_update_is_partial():
    payload = AssetUpdate(criticality="Élevée")
    assert payload.model_dump(exclude_unset=True) == {"criticality": "Élevée"}


def test_relationship_schema_rejects_invalid_type():
    with pytest.raises(ValidationError):
        RelationshipCreate(
            target_asset_id="00000000-0000-0000-0000-000000000002",
            relationship_type="random",
        )


def test_asset_models_have_expected_tables_and_constraints():
    assert Asset.__tablename__ == "assets"
    assert AssetRelationship.__tablename__ == "asset_relationships"
    assert any(c.name == "uq_assets_reference" for c in Asset.__table__.constraints)
    assert any(c.name == "ck_asset_relationship_not_self" for c in AssetRelationship.__table__.constraints)


def test_asset_risk_link_has_unique_pair_and_explicit_foreign_keys():
    assert AssetRiskLink.__tablename__ == "asset_risk_links"
    assert any(c.name == "uq_asset_risk_link" for c in AssetRiskLink.__table__.constraints)
    foreign_keys = {fk.target_fullname for fk in AssetRiskLink.__table__.foreign_keys}
    assert foreign_keys == {"assets.id", "risks.id"}


def test_asset_application_link_is_many_to_one():
    assert not any(c.name == "uq_assets_application_id" for c in Asset.__table__.constraints)
    fk = next(fk for fk in Asset.__table__.foreign_keys if fk.parent.name == "application_id")
    assert fk.target_fullname == "applications.id"



def test_inventory_filter_fields_have_indexes():
    indexed_fields = {"owner", "location", "lifecycle_status", "criticality", "classification"}
    for field_name in indexed_fields:
        assert Asset.__table__.c[field_name].index is True



def test_asset_reference_is_trimmed_on_create_and_update():
    assert AssetCreate(reference="  AST-010  ", name="Serveur").reference == "AST-010"
    assert AssetUpdate(reference="  AST-011  ").reference == "AST-011"


def test_asset_reference_rejects_whitespace_only_values():
    with pytest.raises(ValidationError):
        AssetCreate(reference="   ", name="Serveur")
    with pytest.raises(ValidationError):
        AssetUpdate(reference="   ")


def test_asset_reference_has_case_insensitive_unique_index():
    indexes = {index.name: index for index in Asset.__table__.indexes}
    assert "uq_assets_reference_ci" in indexes
    assert indexes["uq_assets_reference_ci"].unique is True
