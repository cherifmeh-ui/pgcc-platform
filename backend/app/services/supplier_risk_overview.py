"""Deterministic aggregation for the supplier risk overview."""
from datetime import date, timedelta
from typing import Any


def build_supplier_risk_overview(
    suppliers: list[dict[str, Any]],
    supplier_risks: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    access_requests: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    """Build aggregate-only TPRM KPIs; never changes enterprise risk scores."""
    today = today or date.today()
    active_suppliers = [item for item in suppliers if not item.get("archived") and item.get("status") != "Terminé"]
    critical_suppliers = [
        item for item in active_suppliers
        if item.get("criticality") in ("Élevée", "Critique")
    ]

    latest_assessment: dict[Any, dict[str, Any]] = {}
    for item in assessments:
        supplier_id = item["supplier_id"]
        previous = latest_assessment.get(supplier_id)
        if previous is None or item.get("created_at") > previous.get("created_at"):
            latest_assessment[supplier_id] = item

    validated_latest = {
        supplier_id: item
        for supplier_id, item in latest_assessment.items()
        if item.get("status") == "Validée"
    }
    overdue_assessments = sum(
        1 for item in validated_latest.values()
        if item.get("next_review_at") is not None and item["next_review_at"] < today
    )
    suppliers_without_current_assessment = sum(
        1 for supplier in critical_suppliers
        if supplier["id"] not in validated_latest
        or validated_latest[supplier["id"]].get("next_review_at") is None
        or validated_latest[supplier["id"]]["next_review_at"] < today
    )

    unique_risks: dict[Any, dict[str, Any]] = {}
    for item in supplier_risks:
        unique_risks[item["risk_id"]] = item
    risk_distribution = {"inacceptable": 0, "critique": 0, "eleve": 0, "modere": 0, "faible": 0}
    risk_by_status: dict[str, int] = {}
    for item in unique_risks.values():
        score = item.get("risk_level")
        if isinstance(score, (int, float)):
            bucket = "inacceptable" if score >= 20 else "critique" if score >= 15 else "eleve" if score >= 10 else "modere" if score >= 5 else "faible"
            risk_distribution[bucket] += 1
        status = str(item.get("status") or "Non renseigné")
        risk_by_status[status] = risk_by_status.get(status, 0) + 1

    active_accesses = [
        item for item in access_requests
        if item.get("status") == "Approuvé"
        and item.get("start_date") <= today <= item.get("end_date")
    ]
    required_security_clauses = (
        "clause_confidentiality", "clause_incident_notification",
        "clause_audit_right", "clause_business_continuity",
        "clause_reversibility", "clause_data_location",
        "clause_subcontracting", "clause_data_return_destruction",
    )
    active_contracts = [
        item for item in contracts
        if item.get("status") in ("Actif", "À renouveler")
    ]
    contracts_with_missing_security_clauses = sum(
        1 for item in active_contracts
        if any(not item.get(clause, False) for clause in required_security_clauses)
    )
    expiring_contracts = sum(
        1 for item in contracts
        if item.get("status") in ("Actif", "À renouveler")
        and item.get("end_date") is not None
        and today <= item["end_date"] <= today + timedelta(days=90)
    )

    return {
        "as_of": today.isoformat(),
        "suppliers": {
            "total_active": len(active_suppliers),
            "critical_or_high": len(critical_suppliers),
            "critical_without_current_assessment": suppliers_without_current_assessment,
        },
        "assessments": {
            "latest_validated": len(validated_latest),
            "overdue_reviews": overdue_assessments,
        },
        "risks": {
            "distinct_linked": len(unique_risks),
            "by_level": risk_distribution,
            "by_status": risk_by_status,
        },
        "access": {
            "active_authorizations": len(active_accesses),
            "privileged_active": sum(1 for item in active_accesses if item.get("access_level") == "Privilégié"),
            "overdue_reviews": sum(
                1 for item in active_accesses
                if item.get("review_due_at") is not None and item["review_due_at"] < today
            ),
        },
        "contracts": {\n            "expiring_within_90_days": expiring_contracts,\n            "active_or_renewal": len(active_contracts),\n            "with_missing_security_clauses": contracts_with_missing_security_clauses,\n        },
        "scoring_policy": "Les scores des risques centraux ne sont jamais recalculés par cette synthèse.",
    }
