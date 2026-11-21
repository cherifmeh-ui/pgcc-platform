import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.suppliers import (
    SupplierCreate, SupplierUpdate, SupplierContactCreate, SupplierContractCreate, SupplierContractUpdate,
)
from app.models.supplier import Supplier, SupplierContact, SupplierContract, SupplierAssetLink
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
