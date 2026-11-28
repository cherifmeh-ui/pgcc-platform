"""HTTP regression tests for asset CSV import input boundaries and validation."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.endpoints import assets as assets_endpoint
from app.core.database import get_db


def _csv_client(db):
    app = FastAPI()
    app.include_router(assets_endpoint.router, prefix="/api/v1")

    async def override_current_user():
        return MagicMock(role="admin", email="csv-import-admin@example.test")

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _empty_result():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


def test_csv_preview_rejects_non_csv_filename_before_database_access():
    db = AsyncMock()

    with _csv_client(db) as client:
        response = client.post(
            "/api/v1/assets/import/preview",
            files={"file": ("inventory.txt", b"reference,name\nA,Asset\n", "text/plain")},
        )

    assert response.status_code == 415
    db.execute.assert_not_awaited()


def test_csv_preview_rejects_payload_over_one_megabyte_before_database_access():
    db = AsyncMock()
    payload = b"reference,name,asset_type\n" + b"A" * (1_048_576 + 1)

    with _csv_client(db) as client:
        response = client.post(
            "/api/v1/assets/import/preview",
            files={"file": ("inventory.csv", payload, "text/csv")},
        )

    assert response.status_code == 413
    db.execute.assert_not_awaited()


def test_csv_preview_rejects_invalid_utf8_before_database_access():
    db = AsyncMock()

    with _csv_client(db) as client:
        response = client.post(
            "/api/v1/assets/import/preview",
            files={"file": ("inventory.csv", b"reference,name\n\xff,Asset\n", "text/csv")},
        )

    assert response.status_code == 400
    db.execute.assert_not_awaited()


def test_csv_preview_rejects_duplicate_headers_after_whitespace_normalization():
    db = AsyncMock()

    with _csv_client(db) as client:
        response = client.post(
            "/api/v1/assets/import/preview",
            files={
                "file": (
                    "inventory.csv",
                    b"reference, name ,name\nA,Asset,Other\n",
                    "text/csv",
                )
            },
        )

    assert response.status_code == 422
    assert "en-têtes dupliqués" in response.json()["detail"]
    db.execute.assert_not_awaited()


def test_csv_preview_rejects_more_than_five_thousand_data_rows_before_database_access():
    db = AsyncMock()
    rows = ["reference,name,asset_type"]
    rows.extend(
        f"CSV-LIMIT-{index:05d},Asset {index},hardware"
        for index in range(5_001)
    )
    payload = ("\n".join(rows) + "\n").encode("utf-8")

    with _csv_client(db) as client:
        response = client.post(
            "/api/v1/assets/import/preview",
            files={"file": ("inventory.csv", payload, "text/csv")},
        )

    assert response.status_code == 413
    assert "5000 lignes" in response.json()["detail"]
    db.execute.assert_not_awaited()


@pytest.mark.parametrize(
    ("field", "first_value", "second_value", "expected_error"),
    [
        ("hostname", "SRV-APP-01", "srv-app-01", "Hostname dupliqué"),
        ("serial_number", "SN-ABC-123", "sn-abc-123", "Numéro de série dupliqué"),
    ],
)
def test_csv_preview_detects_case_insensitive_duplicate_identifiers_in_same_file(
    field, first_value, second_value, expected_error
):
    db = AsyncMock()
    db.execute.return_value = _empty_result()
    csv_content = (
        f"reference,name,asset_type,{field}\n"
        f"CSV-DUP-001,First asset,hardware,{first_value}\n"
        f"CSV-DUP-002,Second asset,hardware,{second_value}\n"
    )

    with _csv_client(db) as client:
        response = client.post(
            "/api/v1/assets/import/preview",
            files={"file": ("inventory.csv", csv_content.encode(), "text/csv")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_import"] is False
    assert payload["rows_parsed"] == 2
    assert any(expected_error in error["error"] for error in payload["errors"])
    db.commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("payload", "expected_name"),
    [
        (
            b"\xef\xbb\xbfreference,name,asset_type,comment\r\n"
            b"CSV-BOM-001,\"Serveur, principal\",hardware,\"ligne 1\r\nligne 2\"\r\n"
            b"\r\n",
            "Serveur, principal",
        ),
        (
            (
                "reference,name,asset_type,comment\n"
            "CSV-UTF8-001,\"Serveur réseau\",hardware,\"valeur avec ; séparateur\"\n"
            "\n"
        ).encode("utf-8"),
            "Serveur réseau",
        ),
    ],
)
def test_csv_preview_accepts_utf8_bom_crlf_quoted_fields_and_blank_lines(
    payload, expected_name
):
    db = AsyncMock()
    db.execute.return_value = _empty_result()

    with _csv_client(db) as client:
        response = client.post(
            "/api/v1/assets/import/preview",
            files={"file": ("inventory.csv", payload, "text/csv")},
        )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["can_import"] is True
    assert result["rows_parsed"] == 1
    assert result["rows_valid"] == 1
    assert result["validated_rows"][0]["data"]["name"] == expected_name
    assert db.commit.await_count == 0


def test_csv_preview_does_not_echo_rejected_field_values():
    db = AsyncMock()
    db.execute.return_value = _empty_result()
    sentinel = "DO_NOT_DISCLOSE_CSV_SECRET_7f3a91"
    csv_content = (
        "reference,name,asset_type,criticality\n"
        f"CSV-INVALID-001,Invalid asset,hardware,{sentinel}\n"
    )

    with _csv_client(db) as client:
        response = client.post(
            "/api/v1/assets/import/preview",
            files={
                "file": (
                    "inventory.csv",
                    csv_content.encode("utf-8"),
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_import"] is False
    assert sentinel not in response.text
    assert "criticality" in payload["errors"][0]["error"]
    assert "input_value" not in response.text
    db.commit.assert_not_awaited()
