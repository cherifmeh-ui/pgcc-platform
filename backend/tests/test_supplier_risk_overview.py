from datetime import date, datetime, timezone
from uuid import uuid4

from app.services.supplier_risk_overview import build_supplier_risk_overview


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
