from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.datastructures import UploadFile
from fastapi import HTTPException

from app.api.v1.endpoints.assets import preview_asset_csv_import


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
