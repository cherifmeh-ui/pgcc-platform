from uuid import UUID

from app.api.v1.endpoints.assets import _compute_asset_impact


A = UUID("00000000-0000-0000-0000-000000000001")
B = UUID("00000000-0000-0000-0000-000000000002")
C = UUID("00000000-0000-0000-0000-000000000003")
D = UUID("00000000-0000-0000-0000-000000000004")


def test_impact_returns_transitive_dependents_nearest_first():
    # B depends on A, C depends on B, D depends on C
    result = _compute_asset_impact(A, [(B, A), (C, B), (D, C)])
    assert result == [(B, 1), (C, 2), (D, 3)]


def test_impact_does_not_include_unrelated_assets():
    result = _compute_asset_impact(A, [(B, A), (D, C)])
    assert result == [(B, 1)]


def test_impact_handles_multiple_paths_and_cycles_without_duplicates():
    result = _compute_asset_impact(A, [(B, A), (C, A), (D, B), (D, C), (A, D)])
    assert result == [(B, 1), (C, 1), (D, 2)]
