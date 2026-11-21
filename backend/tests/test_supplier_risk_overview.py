from datetime import date, datetime, timezone
from uuid import uuid4

from app.services.supplier_risk_overview import build_supplier_risk_overview, compare_supplier_risk_snapshots, build_supplier_risk_concentration


def test_supplier_risk_overview_deduplicates_risks_and_counts_only_current_access():
    today = date(2026, 11, 21)
    supplier_a, supplier_b = uuid4(), uuid4()
    risk_id = uuid4()
    result = build_supplier_risk_overview(
        suppliers=[
            {"id": supplier_a, "criticality": "Critique"},
            {"id": supplier_b, "criticality": "Moyenne"},
            {"id": uuid4(), "criticality": "Critique", "status": "Terminé"},
        ],
        supplier_risks=[
            {"risk_id": risk_id, "risk_level": 18, "status": "En traitement"},
            {"risk_id": risk_id, "risk_level": 18, "status": "En traitement"},
        ],
        assessments=[
            {"supplier_id": supplier_a, "status": "Validée", "next_review_at": date(2026, 12, 1), "created_at": datetime(2026, 10, 1, tzinfo=timezone.utc)},
        ],
        access_requests=[
            {"status": "Approuvé", "access_level": "Privilégié", "start_date": date(2026, 11, 1), "end_date": date(2026, 12, 1), "review_due_at": date(2026, 11, 10)},
            {"status": "Approuvé", "access_level": "Standard", "start_date": date(2026, 10, 1), "end_date": date(2026, 11, 20), "review_due_at": date(2026, 11, 10)},
            {"status": "Révoqué", "access_level": "Privilégié", "start_date": date(2026, 11, 1), "end_date": date(2026, 12, 1), "review_due_at": date(2026, 11, 10)},
        ],
        contracts=[{"status": "Actif", "end_date": date(2027, 1, 1), "clause_confidentiality": False}],
        today=today,
    )
    assert result["suppliers"]["total_active"] == 2
    assert result["suppliers"]["critical_without_current_assessment"] == 0
    assert result["risks"]["distinct_linked"] == 1
    assert result["risks"]["by_level"]["critique"] == 1
    assert result["access"]["active_authorizations"] == 1
    assert result["access"]["privileged_active"] == 1
    assert result["access"]["overdue_reviews"] == 1
    assert result["contracts"]["expiring_within_90_days"] == 1
    assert result["contracts"]["with_missing_security_clauses"] == 1
    assert result["suppliers"]["total_active"] == 2


def test_supplier_risk_overview_flags_critical_supplier_without_valid_assessment():
    result = build_supplier_risk_overview(
        suppliers=[{"id": "supplier-1", "criticality": "Élevée"}],
        supplier_risks=[],
        assessments=[],
        access_requests=[],
        contracts=[],
        today=date(2026, 11, 21),
    )
    assert result["suppliers"]["critical_without_current_assessment"] == 1
    assert result["risks"]["distinct_linked"] == 0
    assert result["access"]["active_authorizations"] == 0


def test_newer_closed_assessment_supersedes_older_validated_assessment():
    supplier_id = uuid4()
    result = build_supplier_risk_overview(
        suppliers=[{"id": supplier_id, "criticality": "Critique"}],
        supplier_risks=[],
        assessments=[
            {
                "supplier_id": supplier_id,
                "status": "Validée",
                "next_review_at": date(2027, 1, 1),
                "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            },
            {
                "supplier_id": supplier_id,
                "status": "Clôturée",
                "next_review_at": date(2027, 1, 1),
                "created_at": datetime(2026, 11, 1, tzinfo=timezone.utc),
            },
        ],
        access_requests=[],
        contracts=[],
        today=date(2026, 11, 21),
    )
    assert result["assessments"]["latest_validated"] == 0
    assert result["suppliers"]["critical_without_current_assessment"] == 1


def test_monthly_snapshot_comparison_classifies_adverse_trends():
    snapshots = [
        {
            "snapshot_month": date(2026, 11, 1),
            "indicators": {
                "suppliers": {"critical_without_current_assessment": 3},
                "assessments": {"overdue_reviews": 2},
                "access": {"overdue_reviews": 1, "privileged_active": 4},
                "contracts": {"with_missing_security_clauses": 5, "expiring_within_90_days": 2},
                "risks": {"distinct_linked": 7},
            },
        },
        {
            "snapshot_month": date(2026, 10, 1),
            "indicators": {
                "suppliers": {"critical_without_current_assessment": 1},
                "assessments": {"overdue_reviews": 3},
                "access": {"overdue_reviews": 1, "privileged_active": 2},
                "contracts": {"with_missing_security_clauses": 5, "expiring_within_90_days": 4},
                "risks": {"distinct_linked": 6},
            },
        },
    ]
    result = compare_supplier_risk_snapshots(snapshots)
    metrics = {item["key"]: item for item in result["metrics"]}
    assert result["comparison_available"] is True
    assert metrics["critical_without_current_assessment"]["trend"] == "deteriorating"
    assert metrics["critical_without_current_assessment"]["delta"] == 2
    assert metrics["overdue_assessments"]["trend"] == "improving"
    assert metrics["missing_security_clauses"]["trend"] == "stable"
    assert metrics["privileged_active_access"]["trend"] == "change"
    assert metrics["distinct_linked_risks"]["trend"] == "change"


def test_monthly_snapshot_comparison_handles_missing_history_and_missing_values():
    current = {
        "snapshot_month": date(2026, 11, 1),
        "indicators": {"suppliers": {"critical_without_current_assessment": 2}},
    }
    result = compare_supplier_risk_snapshots([current])
    assert result["available"] is True
    assert result["comparison_available"] is False
    assert all(item["trend"] == "insufficient_data" for item in result["metrics"])
    assert compare_supplier_risk_snapshots([]) == {
        "available": False,
        "reason": "Aucun instantané mensuel disponible.",
        "metrics": [],
    }


def test_supplier_risk_concentration_deduplicates_risks_and_counts_privileged_access():
    supplier_a, supplier_b = uuid4(), uuid4()
    shared_risk = uuid4()
    rows = [
        {"supplier_id": supplier_a, "supplier_code": "SUP-A", "supplier_name": "Alpha",
         "criticality": "Critique", "risk_id": shared_risk, "risk_level": 18},
        {"supplier_id": supplier_a, "supplier_code": "SUP-A", "supplier_name": "Alpha",
         "criticality": "Critique", "risk_id": shared_risk, "risk_level": 18},
        {"supplier_id": supplier_a, "supplier_code": "SUP-A", "supplier_name": "Alpha",
         "criticality": "Critique", "risk_id": uuid4(), "risk_level": 7},
        {"supplier_id": supplier_b, "supplier_code": "SUP-B", "supplier_name": "Beta",
         "criticality": "Élevée", "risk_id": uuid4(), "risk_level": 21},
    ]
    result = build_supplier_risk_concentration(
        rows,
        [
            {"supplier_id": supplier_a, "access_level": "Privilégié"},
            {"supplier_id": supplier_a, "access_level": "Privilégié"},
            {"supplier_id": supplier_b, "access_level": "Standard"},
        ],
    )
    assert result[0]["supplier_id"] == str(supplier_b)
    alpha = next(item for item in result if item["supplier_id"] == str(supplier_a))
    assert alpha["linked_risk_count"] == 2
    assert alpha["highest_linked_risk_level"] == 18
    assert alpha["risk_levels"]["critique"] == 1
    assert alpha["active_privileged_accesses"] == 2


def test_supplier_risk_concentration_does_not_invent_a_score_for_unrated_risks():
    result = build_supplier_risk_concentration(
        [{"supplier_id": "s-1", "supplier_code": "S1", "supplier_name": "Supplier",
          "criticality": "Moyenne", "risk_id": "r-1", "risk_level": None}],
        [],
    )
    assert result[0]["highest_linked_risk_level"] is None
    assert result[0]["linked_risk_count"] == 1
    assert sum(result[0]["risk_levels"].values()) == 0
