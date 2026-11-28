"""HTTP-level authorization tests for the asset inventory routes."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.database import get_db
from app.api.v1.endpoints import assets as assets_endpoint
from app.api.v1.endpoints import risks as risks_endpoint
from app.api.v1.endpoints import suppliers as suppliers_endpoint


def _client_for_role(role: str, db):
    app = FastAPI()
    app.include_router(assets_endpoint.router, prefix="/api/v1")
    app.include_router(risks_endpoint.router, prefix="/api/v1")
    app.include_router(suppliers_endpoint.router, prefix="/api/v1")

    async def override_current_user():
        return MagicMock(role=role, email=f"{role}@example.test")

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _empty_result():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


def test_viewer_is_denied_asset_graph_over_http_without_database_query():
    db = AsyncMock()
    with _client_for_role("viewer", db) as client:
        response = client.get("/api/v1/assets/graph")

    assert response.status_code == 403
    db.execute.assert_not_awaited()


def test_auditor_can_read_asset_graph_over_http():
    db = AsyncMock()
    db.execute.side_effect = [_empty_result(), _empty_result()]

    with _client_for_role("auditor", db) as client:
        response = client.get("/api/v1/assets/graph")

    assert response.status_code == 200
    assert response.json() == {
        "nodes": [], "edges": [], "node_count": 0, "edge_count": 0,
    }
    assert db.execute.await_count == 2


def test_auditor_can_export_assets_over_http(monkeypatch):
    db = AsyncMock()
    db.execute.return_value = _empty_result()
    audit = AsyncMock()
    monkeypatch.setattr(assets_endpoint, "log_action", audit)

    with _client_for_role("auditor", db) as client:
        response = client.get("/api/v1/assets/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("\ufeffreference,name,asset_type")
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["action"] == "EXPORT"


@pytest.mark.parametrize("role", ["executive", "viewer"])
def test_non_export_roles_are_denied_export_over_http(role):
    db = AsyncMock()
    with _client_for_role(role, db) as client:
        response = client.get("/api/v1/assets/export.csv")

    assert response.status_code == 403
    db.execute.assert_not_awaited()


def test_auditor_cannot_create_asset_over_http():
    db = AsyncMock()
    payload = {
        "reference": "AST-HTTP-001",
        "name": "Asset test",
        "asset_type": "hardware",
    }

    with _client_for_role("auditor", db) as client:
        response = client.post("/api/v1/assets/", json=payload)

    assert response.status_code == 403
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()



def test_viewer_cannot_read_assets_linked_to_a_risk_over_http_without_database_query():
    db = AsyncMock()
    risk_id = "00000000-0000-0000-0000-000000000001"

    with _client_for_role("viewer", db) as client:
        response = client.get(f"/api/v1/risks/{risk_id}/assets")

    assert response.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.parametrize("role", ["executive", "viewer"])
def test_roles_without_supplier_asset_scope_are_denied_over_http(role):
    db = AsyncMock()
    asset_id = "00000000-0000-0000-0000-000000000002"

    with _client_for_role(role, db) as client:
        response = client.get(f"/api/v1/suppliers/assets/{asset_id}/suppliers")

    assert response.status_code == 403
    db.execute.assert_not_awaited()


def test_auditor_can_read_suppliers_linked_to_an_asset_over_http():
    db = AsyncMock()
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = "00000000-0000-0000-0000-000000000002"
    links_result = MagicMock()
    links_result.all.return_value = []
    db.execute.side_effect = [asset_result, links_result]
    asset_id = "00000000-0000-0000-0000-000000000002"

    with _client_for_role("auditor", db) as client:
        response = client.get(f"/api/v1/suppliers/assets/{asset_id}/suppliers")

    assert response.status_code == 200
    assert response.json() == []
    assert db.execute.await_count == 2



def _jwt_client(db):
    from fastapi import FastAPI
    from app.api.deps import get_current_user
    from app.api.v1.endpoints import assets as assets_endpoint
    from app.api.v1.endpoints import risks as risks_endpoint
    from app.api.v1.endpoints import suppliers as suppliers_endpoint
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(assets_endpoint.router, prefix="/api/v1")
    app.include_router(risks_endpoint.router, prefix="/api/v1")
    app.include_router(suppliers_endpoint.router, prefix="/api/v1")

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _jwt_user_result(user):
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    return result


def test_real_jwt_access_token_authorizes_asset_graph_and_checks_database_state(monkeypatch):
    from app.core.config import settings
    from app.core.security import create_access_token

    monkeypatch.setattr(settings, "JWT_SECRET", "pgcc-jwt-integration-secret-long-enough-for-tests")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    user = MagicMock(
        id="jwt-user-id", email="jwt-auditor@example.test", role="auditor",
        is_active=True, must_change_password=False, mfa_enabled=False, auth_version=3,
    )
    db = AsyncMock()
    db.execute.side_effect = [
        _jwt_user_result(user),
        _empty_result(),
        _empty_result(),
    ]
    token = create_access_token(
        subject=user.email, role="auditor", auth_version=3
    )

    with _jwt_client(db) as client:
        response = client.get(
            "/api/v1/assets/graph",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["node_count"] == 0
    assert db.execute.await_count == 3


def test_real_jwt_with_stale_auth_version_is_rejected_before_asset_query(monkeypatch):
    from app.core.config import settings
    from app.core.security import create_access_token

    monkeypatch.setattr(settings, "JWT_SECRET", "pgcc-jwt-integration-secret-long-enough-for-tests")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    user = MagicMock(
        email="stale-jwt@example.test", role="auditor",
        is_active=True, must_change_password=False, mfa_enabled=False, auth_version=4,
    )
    db = AsyncMock()
    db.execute.return_value = _jwt_user_result(user)
    token = create_access_token(
        subject=user.email, role="auditor", auth_version=3
    )

    with _jwt_client(db) as client:
        response = client.get(
            "/api/v1/assets/graph",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    db.execute.assert_awaited_once()


def test_real_jwt_role_claim_mismatch_is_rejected_before_asset_query(monkeypatch):
    from app.core.config import settings
    from app.core.security import create_access_token

    monkeypatch.setattr(settings, "JWT_SECRET", "pgcc-jwt-integration-secret-long-enough-for-tests")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    user = MagicMock(
        email="role-change@example.test", role="auditor",
        is_active=True, must_change_password=False, mfa_enabled=False, auth_version=1,
    )
    db = AsyncMock()
    db.execute.return_value = _jwt_user_result(user)
    token = create_access_token(
        subject=user.email, role="executive", auth_version=1
    )

    with _jwt_client(db) as client:
        response = client.get(
            "/api/v1/assets/graph",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    db.execute.assert_awaited_once()



def test_real_jwt_auditor_can_read_assets_linked_to_risk(monkeypatch):
    from app.core.config import settings
    from app.core.security import create_access_token

    monkeypatch.setattr(settings, "JWT_SECRET", "pgcc-jwt-integration-secret-long-enough-for-tests")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    user = MagicMock(
        email="jwt-risk-auditor@example.test", role="auditor",
        is_active=True, must_change_password=False, mfa_enabled=False, auth_version=7,
    )
    risk_result = MagicMock()
    risk_result.scalar_one_or_none.return_value = "00000000-0000-0000-0000-000000000010"
    links_result = MagicMock()
    links_result.all.return_value = []
    db = AsyncMock()
    db.execute.side_effect = [_jwt_user_result(user), risk_result, links_result]
    token = create_access_token(subject=user.email, role="auditor", auth_version=7)

    with _jwt_client(db) as client:
        response = client.get(
            "/api/v1/risks/00000000-0000-0000-0000-000000000010/assets",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == []
    assert db.execute.await_count == 3


def test_real_jwt_auditor_can_read_suppliers_linked_to_asset(monkeypatch):
    from app.core.config import settings
    from app.core.security import create_access_token

    monkeypatch.setattr(settings, "JWT_SECRET", "pgcc-jwt-integration-secret-long-enough-for-tests")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    user = MagicMock(
        email="jwt-supplier-auditor@example.test", role="auditor",
        is_active=True, must_change_password=False, mfa_enabled=False, auth_version=8,
    )
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = "00000000-0000-0000-0000-000000000011"
    links_result = MagicMock()
    links_result.all.return_value = []
    db = AsyncMock()
    db.execute.side_effect = [_jwt_user_result(user), asset_result, links_result]
    token = create_access_token(subject=user.email, role="auditor", auth_version=8)

    with _jwt_client(db) as client:
        response = client.get(
            "/api/v1/suppliers/assets/00000000-0000-0000-0000-000000000011/suppliers",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == []
    assert db.execute.await_count == 3


def test_real_jwt_executive_cannot_read_suppliers_linked_to_asset(monkeypatch):
    from app.core.config import settings
    from app.core.security import create_access_token

    monkeypatch.setattr(settings, "JWT_SECRET", "pgcc-jwt-integration-secret-long-enough-for-tests")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    user = MagicMock(
        email="jwt-executive@example.test", role="executive",
        is_active=True, must_change_password=False, mfa_enabled=False, auth_version=2,
    )
    db = AsyncMock()
    db.execute.return_value = _jwt_user_result(user)
    token = create_access_token(subject=user.email, role="executive", auth_version=2)

    with _jwt_client(db) as client:
        response = client.get(
            "/api/v1/suppliers/assets/00000000-0000-0000-0000-000000000011/suppliers",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    db.execute.assert_awaited_once()


def _real_jwt_headers(monkeypatch, *, email: str, role: str, auth_version: int = 1):
    from app.core.config import settings
    from app.core.security import create_access_token

    monkeypatch.setattr(settings, "JWT_SECRET", "pgcc-jwt-integration-secret-long-enough-for-tests")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    token = create_access_token(
        subject=email, role=role, auth_version=auth_version
    )
    return {"Authorization": f"Bearer {token}"}


def test_supplier_access_requests_are_readable_by_auditor_with_real_jwt(monkeypatch):
    supplier_id = "00000000-0000-0000-0000-000000000021"
    user = MagicMock(
        email="supplier-auditor@example.test", role="auditor",
        is_active=True, must_change_password=False, mfa_enabled=False, auth_version=1,
    )
    supplier_result = MagicMock()
    supplier_result.scalar_one_or_none.return_value = supplier_id
    requests_result = MagicMock()
    requests_result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute.side_effect = [_jwt_user_result(user), supplier_result, requests_result]
    headers = _real_jwt_headers(
        monkeypatch, email=user.email, role="auditor", auth_version=1
    )

    with _jwt_client(db) as client:
        response = client.get(
            f"/api/v1/suppliers/{supplier_id}/access-requests",
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json() == []
    assert db.execute.await_count == 3


@pytest.mark.parametrize("role", ["executive", "viewer"])
def test_supplier_access_requests_are_denied_to_roles_without_scope_with_real_jwt(
    monkeypatch, role
):
    supplier_id = "00000000-0000-0000-0000-000000000022"
    email = f"{role}-supplier@example.test"
    user = MagicMock(
        email=email, role=role, is_active=True,
        must_change_password=False, mfa_enabled=False, auth_version=2,
    )
    db = AsyncMock()
    db.execute.return_value = _jwt_user_result(user)
    headers = _real_jwt_headers(
        monkeypatch, email=email, role=role, auth_version=2
    )

    with _jwt_client(db) as client:
        response = client.get(
            f"/api/v1/suppliers/{supplier_id}/access-requests",
            headers=headers,
        )

    assert response.status_code == 403
    db.execute.assert_awaited_once()


def test_auditor_cannot_create_supplier_access_request_over_http_with_real_jwt(
    monkeypatch,
):
    supplier_id = "00000000-0000-0000-0000-000000000023"
    email = "auditor-no-write@example.test"
    user = MagicMock(
        email=email, role="auditor", is_active=True,
        must_change_password=False, mfa_enabled=False, auth_version=3,
    )
    db = AsyncMock()
    db.execute.return_value = _jwt_user_result(user)
    headers = _real_jwt_headers(
        monkeypatch, email=email, role="auditor", auth_version=3
    )
    payload = {
        "supplier_asset_link_id": "00000000-0000-0000-0000-000000000024",
        "access_level": "Standard",
        "data_access": False,
        "justification": "Intervention technique planifiée",
        "scope": "Maintenance applicative",
        "start_date": "2026-12-01",
        "end_date": "2026-12-31",
        "review_due_at": "2026-12-15",
    }

    with _jwt_client(db) as client:
        response = client.post(
            f"/api/v1/suppliers/{supplier_id}/access-requests",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 403
    db.execute.assert_awaited_once()
    db.commit.assert_not_awaited()


def test_supplier_access_requests_require_authentication_over_http():
    db = AsyncMock()
    supplier_id = "00000000-0000-0000-0000-000000000025"

    with _jwt_client(db) as client:
        response = client.get(f"/api/v1/suppliers/{supplier_id}/access-requests")

    assert response.status_code == 401
    db.execute.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "POST",
            "/api/v1/suppliers/00000000-0000-0000-0000-000000000031/access-requests/00000000-0000-0000-0000-000000000032/decision",
            {"decision": "Approuvé", "comment": "Validation de sécurité"},
        ),
        (
            "POST",
            "/api/v1/suppliers/00000000-0000-0000-0000-000000000031/access-requests/00000000-0000-0000-0000-000000000032/reviews",
            {"outcome": "Maintenue", "comment": "Revue périodique conforme"},
        ),
        (
            "POST",
            "/api/v1/suppliers/00000000-0000-0000-0000-000000000031/access-requests/00000000-0000-0000-0000-000000000032/revoke",
            {"reason": "Fin de besoin opérationnel"},
        ),
        (
            "POST",
            "/api/v1/suppliers/00000000-0000-0000-0000-000000000031/access-requests/00000000-0000-0000-0000-000000000032/expire",
            None,
        ),
        (
            "POST",
            "/api/v1/suppliers/00000000-0000-0000-0000-000000000031/assets/00000000-0000-0000-0000-000000000033/terminate",
            None,
        ),
    ],
)
def test_auditor_cannot_mutate_supplier_access_lifecycle_over_http_with_real_jwt(
    monkeypatch, method, path, payload
):
    email = "auditor-lifecycle-readonly@example.test"
    user = MagicMock(
        id="auditor-lifecycle-user-id",
        email=email,
        role="auditor",
        is_active=True,
        must_change_password=False,
        mfa_enabled=False,
        auth_version=4,
    )
    db = AsyncMock()
    db.execute.return_value = _jwt_user_result(user)
    headers = _real_jwt_headers(
        monkeypatch, email=email, role="auditor", auth_version=4
    )

    with _jwt_client(db) as client:
        response = client.request(
            method, path, json=payload, headers=headers
        )

    assert response.status_code == 403
    # Only the user lookup needed to validate the JWT is allowed to reach the DB.
    db.execute.assert_awaited_once()
    db.commit.assert_not_awaited()
    db.flush.assert_not_awaited()


@pytest.mark.parametrize("role", ["auditor", "executive"])
def test_authorized_roles_can_read_paginated_asset_inventory_over_http(role):
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    db.execute.side_effect = [count_result, _empty_result()]

    with _client_for_role(role, db) as client:
        response = client.get("/api/v1/assets/page", params={"page": 1, "page_size": 25})

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 25,
        "pages": 0,
    }
    assert db.execute.await_count == 2


def test_viewer_is_denied_paginated_asset_inventory_over_http_without_database_query():
    db = AsyncMock()

    with _client_for_role("viewer", db) as client:
        response = client.get("/api/v1/assets/page")

    assert response.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "params",
    [
        {"page": "0"},
        {"page_size": "0"},
        {"page_size": "201"},
        {"q": "x" * 101},
        {"owner": "x" * 151},
        {"location": "x" * 201},
    ],
)
def test_asset_inventory_pagination_rejects_out_of_range_filters_before_database_query(params):
    db = AsyncMock()

    with _client_for_role("auditor", db) as client:
        response = client.get("/api/v1/assets/page", params=params)

    assert response.status_code == 422
    db.execute.assert_not_awaited()


@pytest.mark.parametrize("role", ["auditor", "executive", "viewer"])
@pytest.mark.parametrize(
    ("method", "path", "payload", "upload"),
    [
        (
            "PATCH",
            "/api/v1/assets/00000000-0000-0000-0000-000000000041",
            {"name": "Forbidden update"},
            False,
        ),
        (
            "DELETE",
            "/api/v1/assets/00000000-0000-0000-0000-000000000041",
            None,
            False,
        ),
        (
            "POST",
            "/api/v1/assets/import/preview",
            None,
            True,
        ),
        (
            "POST",
            "/api/v1/assets/import/confirm",
            None,
            True,
        ),
        (
            "POST",
            "/api/v1/assets/00000000-0000-0000-0000-000000000041/relationships",
            {
                "target_asset_id": "00000000-0000-0000-0000-000000000042",
                "relationship_type": "depends_on",
            },
            False,
        ),
        (
            "POST",
            "/api/v1/assets/00000000-0000-0000-0000-000000000041/risks",
            {"risk_id": "00000000-0000-0000-0000-000000000043"},
            False,
        ),
    ],
)
def test_non_admin_roles_cannot_mutate_assets_or_import_over_http(
    role, method, path, payload, upload
):
    """Read-only roles must be rejected before asset-domain database queries."""
    db = AsyncMock()
    files = (
        {"file": ("assets.csv", "reference,name,asset_type\nAUTH-001,Test,hardware\n", "text/csv")}
        if upload
        else None
    )

    with _client_for_role(role, db) as client:
        response = client.request(
            method,
            path,
            json=payload,
            files=files,
        )

    assert response.status_code == 403
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()
    db.flush.assert_not_awaited()
