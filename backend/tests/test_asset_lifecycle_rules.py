"""Unit tests for the asset lifecycle state/marker invariants."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.api.v1.endpoints.assets import (
    _asset_is_retired,
    _lifecycle_retirement_marker,
    _relationship_assets_are_active,
)


@pytest.mark.parametrize(
    "status",
    ["Identifié", "Actif", "En maintenance", "En projet"],
)
def test_non_retired_lifecycle_status_clears_retirement_marker(status):
    previous_marker = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert _lifecycle_retirement_marker(status, previous_marker) is None
    assert not _asset_is_retired(status, None)


@pytest.mark.parametrize("status", ["Retiré", "Décommissionné"])
def test_retired_lifecycle_status_sets_and_preserves_retirement_marker(status):
    previous_marker = datetime(2026, 1, 1, tzinfo=timezone.utc)

    generated = _lifecycle_retirement_marker(status, None)
    assert generated is not None
    assert generated.tzinfo is not None
    assert _lifecycle_retirement_marker(status, previous_marker) == previous_marker
    assert _asset_is_retired(status, generated)


def test_unspecified_lifecycle_status_preserves_current_marker():
    marker = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert _lifecycle_retirement_marker(None, marker) == marker
    assert _lifecycle_retirement_marker(None, None) is None


@pytest.mark.parametrize(
    ("status", "marker", "expected"),
    [
        ("Actif", None, False),
        ("En maintenance", None, False),
        ("En projet", None, False),
        ("Retiré", None, True),
        ("Décommissionné", None, True),
        ("Actif", datetime(2026, 1, 1, tzinfo=timezone.utc), True),
    ],
)
def test_retirement_is_authoritative_from_either_lifecycle_field(status, marker, expected):
    assert _asset_is_retired(status, marker) is expected


def test_relationship_requires_two_active_assets():
    rows = [
        (uuid4(), None, "Actif"),
        (uuid4(), None, "En maintenance"),
    ]

    assert _relationship_assets_are_active(rows)


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [(uuid4(), None, "Actif")],
        [(uuid4(), None, "Actif"), (uuid4(), None, "Retiré")],
        [
            (uuid4(), None, "Actif"),
            (uuid4(), datetime(2026, 1, 1, tzinfo=timezone.utc), "Actif"),
        ],
    ],
)
def test_relationship_rejects_missing_or_retired_endpoint(rows):
    assert not _relationship_assets_are_active(rows)
