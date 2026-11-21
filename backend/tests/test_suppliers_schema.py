import pytest
from datetime import date
from pydantic import ValidationError

from app.api.v1.endpoints.suppliers import (
    SupplierCreate, SupplierUpdate, SupplierContactCreate, SupplierContractCreate, SupplierContractUpdate,
    SupplierAccessRequestCreate, SupplierAccessDecision, SupplierAccessRevocation,
)
from app.models.supplier import Supplier, SupplierContact, SupplierContract, SupplierAssetLink, SupplierAccessRequest
from app.utils.rbac import role_has_permission


def test_supplier_create_normalizes_code_and_legal_name():
    supplier = SupplierCreate(code=" CTF-IT-001 ", legal_name="  Prestataire SI  ")
    assert supplier.code == "CTF-IT-001"
    assert supplier.legal_name == "Prestataire SI"
    assert supplier.status == "À qualifier"


def test_supplier_create_rejects_blank_identity():
    with pytest.raises(ValidationError):
        SupplierCreate(code="  ", legal_name="Prestataire")
    with pytest.raises(ValidationError):
        SupplierCreate(code="SUP-001", legal_name="  ")


def test_supplier_update_is_partial_and_normalizes_code():
    update = SupplierUpdate(code=" SUP-002 ")
    assert update.model_dump(exclude_unset=True) == {"code": "SUP-002"}


def test_supplier_contact_validates_email_and_name():
    contact = SupplierContactCreate(full_name="  Contact Sécurité ", email="sec@example.com", contact_type="Sécurité")
    assert contact.full_name == "Contact Sécurité"
    with pytest.raises(ValidationError):
        SupplierContactCreate(full_name="Contact", email="not-an-email")


def test_supplier_models_have_expected_constraints():
    assert Supplier.__tablename__ == "suppliers"
    assert SupplierContact.__tablename__ == "supplier_contacts"
    assert any(c.name == "uq_suppliers_code" for c in Supplier.__table__.constraints)
    assert any(c.name == "ck_suppliers_status" for c in Supplier.__table__.constraints)
    assert any(c.name == "ck_supplier_contacts_type" for c in SupplierContact.__table__.constraints)
    contact_fk = next(fk for fk in SupplierContact.__table__.foreign_keys if fk.parent.name == "supplier_id")
    assert contact_fk.ondelete == "RESTRICT"


def test_supplier_code_has_case_insensitive_unique_index():
    indexes = {index.name: index for index in Supplier.__table__.indexes}
    assert indexes["uq_suppliers_code_ci"].unique is True


def test_supplier_permissions_follow_separation_of_duties():
    assert role_has_permission("admin", "suppliers", "create")
    assert role_has_permission("admin", "suppliers", "manage_contacts")
    assert role_has_permission("auditor", "suppliers", "read")
    assert role_has_permission("auditor", "suppliers", "export")
    assert not role_has_permission("executive", "suppliers", "manage_contacts")
    assert not role_has_permission("viewer", "suppliers", "read")


def test_supplier_dependency_level_is_constrained():
    assert any(c.name == "ck_suppliers_dependency_level" for c in Supplier.__table__.constraints)


def test_supplier_contact_read_is_restricted_to_admin_and_auditor():
    assert role_has_permission("admin", "suppliers", "read_contacts")
    assert role_has_permission("auditor", "suppliers", "read_contacts")
    assert not role_has_permission("executive", "suppliers", "read_contacts")
    assert not role_has_permission("viewer", "suppliers", "read_contacts")

def test_supplier_contract_validates_dates_and_normalizes_identity():
    contract = SupplierContractCreate(reference="  CTF-2026-01 ", title="  Support SI ", start_date="2026-01-01", end_date="2026-12-31")
    assert contract.reference == "CTF-2026-01"
    assert contract.title == "Support SI"
    assert contract.notice_period_days == 90
    with pytest.raises(ValidationError):
        SupplierContractCreate(reference="C-1", title="Contrat", start_date="2026-12-31", end_date="2026-01-01")


def test_supplier_contract_update_rejects_invalid_notice_period():
    with pytest.raises(ValidationError):
        SupplierContractUpdate(notice_period_days=5000)


def test_supplier_contract_model_links_supplier_and_document():
    assert SupplierContract.__tablename__ == "supplier_contracts"
    assert any(c.name == "ck_supplier_contracts_dates" for c in SupplierContract.__table__.constraints)
    foreign_keys = {fk.parent.name: fk for fk in SupplierContract.__table__.foreign_keys}
    assert foreign_keys["supplier_id"].ondelete == "RESTRICT"
    assert foreign_keys["document_id"].ondelete == "RESTRICT"


def test_supplier_contract_permissions_separate_read_and_write():
    assert role_has_permission("admin", "suppliers", "manage_contracts")
    assert role_has_permission("auditor", "suppliers", "read_contracts")
    assert not role_has_permission("executive", "suppliers", "read_contracts")
    assert not role_has_permission("auditor", "suppliers", "manage_contracts")



def test_supplier_asset_link_has_integrity_constraints():
    assert SupplierAssetLink.__tablename__ == "supplier_asset_links"
    assert any(c.name == "uq_supplier_asset_link" for c in SupplierAssetLink.__table__.constraints)
    assert any(c.name == "ck_supplier_asset_links_type" for c in SupplierAssetLink.__table__.constraints)
    supplier_fk = next(fk for fk in SupplierAssetLink.__table__.foreign_keys if fk.parent.name == "supplier_id")
    asset_fk = next(fk for fk in SupplierAssetLink.__table__.foreign_keys if fk.parent.name == "asset_id")
    assert supplier_fk.ondelete == "RESTRICT"
    assert asset_fk.ondelete == "RESTRICT"


def test_supplier_asset_link_permissions_are_separated():
    assert role_has_permission("admin", "suppliers", "read_assets")
    assert role_has_permission("auditor", "suppliers", "read_assets")
    assert role_has_permission("admin", "suppliers", "manage_assets")
    assert not role_has_permission("auditor", "suppliers", "manage_assets")
    assert not role_has_permission("executive", "suppliers", "manage_assets")


def test_supplier_asset_reverse_lookup_uses_supplier_permissions():
    from app.api.v1.endpoints.suppliers import list_asset_suppliers
    assert list_asset_suppliers.__name__ == "list_asset_suppliers"
    assert role_has_permission("admin", "suppliers", "read_assets")
    assert role_has_permission("auditor", "suppliers", "read_assets")
    assert not role_has_permission("executive", "suppliers", "read_assets")
    assert role_has_permission("admin", "suppliers", "manage_assets")
    assert not role_has_permission("auditor", "suppliers", "manage_assets")


def test_supplier_access_request_validates_finite_dates_and_review_window():
    request = SupplierAccessRequestCreate(
        supplier_asset_link_id="00000000-0000-0000-0000-000000000001",
        access_level="Privilégié", justification="Maintenance planifiée", scope="Administration du serveur",
        start_date="2026-11-22", end_date="2026-12-22", review_due_at="2026-12-01",
    )
    assert request.access_level == "Privilégié"
    with pytest.raises(ValidationError):
        SupplierAccessRequestCreate(
            supplier_asset_link_id="00000000-0000-0000-0000-000000000001",
            access_level="Standard", justification="Maintenance planifiée", scope="Périmètre",
            start_date="2026-11-22", end_date="2026-11-21", review_due_at="2026-11-22",
        )
    with pytest.raises(ValidationError):
        SupplierAccessRequestCreate(
            supplier_asset_link_id="00000000-0000-0000-0000-000000000001",
            access_level="Standard", justification="Maintenance planifiée", scope="Périmètre",
            start_date="2026-11-22", end_date="2026-12-22", review_due_at="2027-01-01",
        )


def test_supplier_access_decision_and_revocation_require_comments():
    assert SupplierAccessDecision(decision="Approuvé", comment="Validé après revue").decision == "Approuvé"
    assert SupplierAccessRevocation(reason="Fin de prestation").reason == "Fin de prestation"
    with pytest.raises(ValidationError):
        SupplierAccessDecision(decision="Refusé", comment="  ")
    with pytest.raises(ValidationError):
        SupplierAccessRevocation(reason="  ")


def test_supplier_access_request_model_integrity_and_permissions():
    assert SupplierAccessRequest.__tablename__ == "supplier_access_requests"
    assert any(c.name == "ck_supplier_access_requests_decision_trace" for c in SupplierAccessRequest.__table__.constraints)
    assert any(c.name == "ck_supplier_access_requests_review_window" for c in SupplierAccessRequest.__table__.constraints)
    assert role_has_permission("admin", "suppliers", "read_access_requests")
    assert role_has_permission("auditor", "suppliers", "read_access_requests")
    assert role_has_permission("admin", "suppliers", "request_access")
    assert role_has_permission("admin", "suppliers", "decide_access")
    assert role_has_permission("admin", "suppliers", "revoke_access")
    assert not role_has_permission("auditor", "suppliers", "decide_access")
    assert not role_has_permission("executive", "suppliers", "read_access_requests")


def test_supplier_access_open_link_has_database_uniqueness():
    indexes = {index.name: index for index in SupplierAccessRequest.__table__.indexes}
    assert indexes["uq_supplier_access_requests_open_link"].unique is True
    assert "Demandé" in str(indexes["uq_supplier_access_requests_open_link"].dialect_options["postgresql"]["where"])


def test_supplier_access_expiry_permission_is_admin_only():
    assert role_has_permission("admin", "suppliers", "expire_access")
    assert not role_has_permission("auditor", "suppliers", "expire_access")


def test_supplier_access_api_routes_are_registered_with_separate_permissions():
    from app.api.v1.endpoints.suppliers import (
        list_supplier_access_requests, create_supplier_access_request,
        decide_supplier_access_request, revoke_supplier_access_request,
        expire_supplier_access_request,
    )
    assert all(callable(route) for route in (
        list_supplier_access_requests, create_supplier_access_request,
        decide_supplier_access_request, revoke_supplier_access_request,
        expire_supplier_access_request,
    ))
    assert role_has_permission("admin", "suppliers", "decide_access")
    assert not role_has_permission("auditor", "suppliers", "decide_access")
    assert role_has_permission("admin", "suppliers", "revoke_access")
    assert role_has_permission("admin", "suppliers", "expire_access")


def test_supplier_access_review_schema_requires_comment_and_valid_outcome():
    from app.api.v1.endpoints.suppliers import SupplierAccessReviewCreate
    valid = SupplierAccessReviewCreate(outcome="Maintenue", comment="Accès toujours justifié", next_review_at=date(2027, 1, 1))
    assert valid.outcome == "Maintenue"
    with pytest.raises(ValidationError):
        SupplierAccessReviewCreate(outcome="Maintenue", comment="   ")


def test_supplier_access_review_model_is_append_only_and_permission_is_restricted():
    from app.models.supplier import SupplierAccessReview
    assert SupplierAccessReview.__tablename__ == "supplier_access_reviews"
    assert role_has_permission("admin", "suppliers", "review_access")
    assert not role_has_permission("auditor", "suppliers", "review_access")
    assert role_has_permission("auditor", "suppliers", "read_access_requests")


def test_supplier_access_review_routes_are_registered():
    from app.api.v1.endpoints.suppliers import list_supplier_access_reviews, review_supplier_access
    assert callable(list_supplier_access_reviews)
    assert callable(review_supplier_access)


def test_supplier_risk_link_schema_validates_context_and_type():
    from app.api.v1.endpoints.suppliers import SupplierRiskLinkCreate
    from uuid import uuid4
    valid = SupplierRiskLinkCreate(
        risk_id=uuid4(), relationship_type="Dépendance opérationnelle",
        relationship_context="Le fournisseur assure l'exploitation du système critique",
    )
    assert valid.relationship_type == "Dépendance opérationnelle"
    with pytest.raises(ValidationError):
        SupplierRiskLinkCreate(
            risk_id=uuid4(), relationship_type="Dépendance opérationnelle",
            relationship_context="   ",
        )


def test_supplier_risk_link_model_and_cross_module_permissions():
    from app.models.supplier import SupplierRiskLink
    assert SupplierRiskLink.__tablename__ == "supplier_risk_links"
    assert role_has_permission("admin", "suppliers", "manage_risks")
    assert not role_has_permission("auditor", "suppliers", "manage_risks")
    assert role_has_permission("admin", "risks", "update")
    assert not role_has_permission("auditor", "risks", "update")


def test_supplier_risk_link_routes_are_registered():
    from app.api.v1.endpoints.suppliers import list_supplier_risk_links, link_supplier_to_risk
    assert callable(list_supplier_risk_links)
    assert callable(link_supplier_to_risk)
