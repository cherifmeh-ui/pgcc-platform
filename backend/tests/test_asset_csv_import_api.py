from io import BytesIO
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.datastructures import UploadFile
from fastapi import HTTPException

from app.api.v1.endpoints.assets import confirm_asset_csv_import, preview_asset_csv_import


@pytest.mark.asyncio
async def test_csv_preview_validates_rows_and_duplicate_references():
    csv_data = (
        "reference,name,asset_type,criticality\n"
        "A-001,Serveur 1,hardware,Critique\n"
        "A-001,Serveur doublon,hardware,Moyenne\n"
        "A-003,,hardware,Faible\n"
    )
    upload = UploadFile(filename="assets.csv", file=BytesIO(csv_data.encode("utf-8")))
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result

    response = await preview_asset_csv_import(
        file=upload,
        db=db,
        current_user=MagicMock(email="tester@example.test"),
    )

    assert response["rows_parsed"] == 3
    assert response["rows_valid"] == 1
    assert response["can_import"] is False
    assert len(response["errors"]) == 2
    assert response["preview"][0]["data"]["reference"] == "A-001"


@pytest.mark.asyncio
async def test_csv_preview_rejects_unknown_columns():
    upload = UploadFile(filename="assets.csv", file=BytesIO(b"reference,name,unknown\nA-1,Asset,x"))
    db = AsyncMock()

    with pytest.raises(Exception) as exc:
        await preview_asset_csv_import(
            file=upload,
            db=db,
            current_user=MagicMock(email="tester@example.test"),
        )
    assert "Colonnes inconnues" in str(exc.value)
    db.execute.assert_not_awaited()



def test_csv_export_formula_protection():
    from app.api.v1.endpoints.assets import _csv_safe_value

    assert _csv_safe_value("normal-value") == "normal-value"
    assert _csv_safe_value("=HYPERLINK(\"https://example.test\")").startswith("'=")
    assert _csv_safe_value("+cmd") == "'+cmd"
    assert _csv_safe_value(None) == ""



@pytest.mark.asyncio
async def test_csv_preview_rejects_file_larger_than_one_mib_before_parsing():
    from app.api.v1.endpoints.assets import MAX_ASSET_IMPORT_BYTES

    upload = UploadFile(
        filename="assets.csv",
        file=BytesIO(b"x" * (MAX_ASSET_IMPORT_BYTES + 1)),
    )
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await preview_asset_csv_import(
            file=upload,
            db=db,
            current_user=MagicMock(email="tester@example.test"),
        )

    assert exc.value.status_code == 413
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_csv_preview_rejects_more_than_five_thousand_data_rows():
    from app.api.v1.endpoints.assets import MAX_ASSET_IMPORT_ROWS

    rows = [
        f"ASSET-{index},Asset {index},hardware,Moyenne"
        for index in range(MAX_ASSET_IMPORT_ROWS + 1)
    ]
    csv_data = "reference,name,asset_type,criticality\n" + "\n".join(rows)
    upload = UploadFile(filename="assets.csv", file=BytesIO(csv_data.encode("utf-8")))
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await preview_asset_csv_import(
            file=upload,
            db=db,
            current_user=MagicMock(email="tester@example.test"),
        )

    assert exc.value.status_code == 413
    assert str(MAX_ASSET_IMPORT_ROWS) in exc.value.detail
    db.execute.assert_not_awaited()



@pytest.mark.asyncio
async def test_csv_preview_checks_repeated_application_references_in_one_query():
    application_id = uuid4()
    csv_data = (
        "reference,name,asset_type,criticality,application_id\n"
        f"APP-001,Serveur 1,hardware,Moyenne,{application_id}\n"
        f"APP-002,Serveur 2,hardware,Élevée,{application_id}\n"
    )
    upload = UploadFile(filename="assets.csv", file=BytesIO(csv_data.encode("utf-8")))
    db = AsyncMock()
    application_result = MagicMock()
    application_result.scalars.return_value.all.return_value = [application_id]
    asset_result = MagicMock()
    asset_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [application_result, asset_result]

    response = await preview_asset_csv_import(
        file=upload,
        db=db,
        current_user=MagicMock(email="tester@example.test"),
    )

    assert response["can_import"] is True
    assert response["rows_valid"] == 2
    assert db.execute.await_count == 2



@pytest.mark.asyncio
async def test_csv_preview_rejects_duplicate_normalized_headers():
    upload = UploadFile(
        filename="assets.csv",
        file=BytesIO(b"reference, reference,name,asset_type,criticality\nA-001,A-002,Asset,hardware,Moyenne"),
    )
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await preview_asset_csv_import(
            file=upload,
            db=db,
            current_user=MagicMock(email="tester@example.test"),
        )

    assert exc.value.status_code == 422
    assert "en-têtes dupliqués" in exc.value.detail
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_csv_preview_rejects_rows_with_extra_columns():
    upload = UploadFile(
        filename="assets.csv",
        file=BytesIO(
            b"reference,name,asset_type,criticality\n"
            b"A-001,Asset,hardware,Moyenne,unexpected"
        ),
    )
    db = AsyncMock()

    response = await preview_asset_csv_import(
        file=upload,
        db=db,
        current_user=MagicMock(email="tester@example.test"),
    )

    assert response["can_import"] is False
    assert response["rows_valid"] == 0
    assert response["errors"][0]["row"] == 2
    assert "dépasse" in response["errors"][0]["error"]
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_csv_import_sets_retirement_marker_for_historical_retired_asset(monkeypatch):
    from app.api.v1.endpoints import assets as assets_endpoint

    monkeypatch.setattr(
        assets_endpoint,
        "preview_asset_csv_import",
        AsyncMock(return_value={
            "can_import": True,
            "validated_rows": [{
                "row": 2,
                "data": {
                    "reference": "AST-CSV-RETIRED",
                    "name": "Ancien serveur",
                    "lifecycle_status": "Décommissionné",
                },
            }],
        }),
    )
    monkeypatch.setattr(assets_endpoint, "_ensure_application_exists", AsyncMock())
    db = AsyncMock()
    db.add_all = MagicMock()
    audit = AsyncMock()
    monkeypatch.setattr(assets_endpoint, "enqueue_audit_event", audit)

    response = await confirm_asset_csv_import(
        request=MagicMock(),
        file=MagicMock(filename="assets.csv"),
        db=db,
        current_user=MagicMock(email="tester@example.test"),
    )

    imported_assets = db.add_all.call_args.args[0]
    assert response["imported"] == 1
    assert imported_assets[0].lifecycle_status == "Décommissionné"
    assert imported_assets[0].retired_at is not None
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()



@pytest.mark.asyncio
async def test_csv_import_refuses_confirmation_when_preview_contains_errors(monkeypatch):
    from app.api.v1.endpoints import assets as assets_endpoint

    preview = AsyncMock(return_value={
        "can_import": False,
        "errors": [{"row": 3, "error": "Référence déjà existante"}],
        "validated_rows": [],
    })
    monkeypatch.setattr(assets_endpoint, "preview_asset_csv_import", preview)
    db = AsyncMock()
    db.add_all = MagicMock()

    with pytest.raises(HTTPException) as exc:
        await confirm_asset_csv_import(
            request=MagicMock(),
            file=MagicMock(filename="assets.csv"),
            db=db,
            current_user=MagicMock(email="tester@example.test"),
        )

    assert exc.value.status_code == 422
    assert exc.value.detail["errors"][0]["row"] == 3
    db.add_all.assert_not_called()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_csv_import_rolls_back_all_rows_on_database_integrity_conflict(monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from app.api.v1.endpoints import assets as assets_endpoint

    preview = AsyncMock(return_value={
        "can_import": True,
        "errors": [],
        "validated_rows": [
            {"row": 2, "data": {"reference": "AST-ATOMIC-1", "name": "Asset 1", "asset_type": "hardware"}},
            {"row": 3, "data": {"reference": "AST-ATOMIC-2", "name": "Asset 2", "asset_type": "hardware"}},
        ],
    })
    monkeypatch.setattr(assets_endpoint, "preview_asset_csv_import", preview)
    db = AsyncMock()
    db.add_all = MagicMock()
    db.flush.side_effect = IntegrityError("insert assets", {}, Exception("unique violation"))

    with pytest.raises(HTTPException) as exc:
        await confirm_asset_csv_import(
            request=MagicMock(),
            file=MagicMock(filename="assets.csv"),
            db=db,
            current_user=MagicMock(email="tester@example.test"),
        )

    assert exc.value.status_code == 409
    assert "Aucun actif n'a été importé" in exc.value.detail
    assert len(db.add_all.call_args.args[0]) == 2
    db.flush.assert_awaited_once()
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_csv_import_rolls_back_assets_when_audit_outbox_enqueue_fails(monkeypatch):
    from app.api.v1.endpoints import assets as assets_endpoint

    preview = AsyncMock(return_value={
        "can_import": True,
        "errors": [],
        "validated_rows": [
            {"row": 2, "data": {"reference": "AST-AUDIT-ROLLBACK", "name": "Asset audit", "asset_type": "hardware"}},
        ],
    })
    audit = AsyncMock(side_effect=RuntimeError("simulated audit outbox failure"))
    monkeypatch.setattr(assets_endpoint, "preview_asset_csv_import", preview)
    monkeypatch.setattr(assets_endpoint, "enqueue_audit_event", audit)
    db = AsyncMock()
    db.add_all = MagicMock()

    with pytest.raises(RuntimeError, match="simulated audit outbox failure"):
        await confirm_asset_csv_import(
            request=MagicMock(),
            file=MagicMock(filename="assets.csv"),
            db=db,
            current_user=MagicMock(email="tester@example.test"),
        )

    db.add_all.assert_called_once()
    db.flush.assert_awaited_once()
    audit.assert_awaited_once()
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_csv_preview_rejects_unknown_application_id():
    application_id = uuid4()
    csv_data = (
        "reference,name,asset_type,criticality,application_id\\n"
        f"APP-UNKNOWN-001,Serveur orphelin,hardware,Moyenne,{application_id}\\n"
    )
    upload = UploadFile(filename="assets.csv", file=BytesIO(csv_data.encode("utf-8")))
    db = AsyncMock()
    application_result = MagicMock()
    application_result.scalars.return_value.all.return_value = []
    asset_result = MagicMock()
    asset_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [application_result, asset_result]

    response = await preview_asset_csv_import(
        file=upload,
        db=db,
        current_user=MagicMock(email="tester@example.test"),
    )

    assert response["can_import"] is False
    assert response["rows_valid"] == 0
    assert any(
        error["error"] == "Application associée introuvable"
        for error in response["errors"]
    )
    assert db.execute.await_count == 2
    db.commit.assert_not_awaited()
    db.add.assert_not_called()
    db.add_all.assert_not_called()
