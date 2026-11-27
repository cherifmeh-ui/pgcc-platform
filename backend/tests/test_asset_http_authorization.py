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
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(assets_endpoint.router, prefix="/api/v1")

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
