import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.suppliers import (
    SupplierCreate, SupplierUpdate, SupplierContactCreate,
)
from app.models.supplier import Supplier, SupplierContact
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
    contact = SupplierContactCreate(full_name="  Contact Sécurité ", email="sec@example.test", contact_type="Sécurité")
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
