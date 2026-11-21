"""Risk scoring utilities. Current methodology: impact x likelihood, scales 1-5.

This is the project's initial matrix and should be versioned before organization-wide
use. It is not a universal risk calculation standard.
"""


def calculate_risk_level(impact: int, likelihood: int) -> int:
    """Return the 1-25 score after validating the matrix inputs."""
    if not isinstance(impact, int) or not isinstance(likelihood, int):
        raise ValueError("Impact and likelihood must be integers.")
    if not 1 <= impact <= 5 or not 1 <= likelihood <= 5:
        raise ValueError("Impact and likelihood must be between 1 and 5.")
    return impact * likelihood
