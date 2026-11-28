import pytest

from app.services.risk_scoring import calculate_risk_level


@pytest.mark.parametrize(
    "impact,likelihood,expected",
    [(1, 1, 1), (3, 4, 12), (5, 5, 25)],
)
def test_calculate_risk_level_valid_values(impact, likelihood, expected):
    assert calculate_risk_level(impact, likelihood) == expected


@pytest.mark.parametrize("impact,likelihood", [(0, 3), (6, 2), (2, -1), (3, 8)])
def test_calculate_risk_level_rejects_out_of_range_values(impact, likelihood):
    with pytest.raises(ValueError):
        calculate_risk_level(impact, likelihood)


@pytest.mark.parametrize("impact,likelihood", [(1.5, 3), (3, "4"), (True, 2)])
def test_calculate_risk_level_rejects_non_integer_values(impact, likelihood):
    with pytest.raises(ValueError):
        calculate_risk_level(impact, likelihood)
