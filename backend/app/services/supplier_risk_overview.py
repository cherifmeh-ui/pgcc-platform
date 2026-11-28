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
        "contracts": {
            "expiring_within_90_days": expiring_contracts,
            "active_or_renewal": len(active_contracts),
            "with_missing_security_clauses": contracts_with_missing_security_clauses,
        },
        "scoring_policy": "Les scores des risques centraux ne sont jamais recalculés par cette synthèse.",
    }


def compare_supplier_risk_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the two most recent snapshots without inventing an overall risk score.

    Input order is irrelevant. Only metrics with an explicit adverse direction are
    classified as improving/deteriorating; contextual metrics are reported neutrally.
    """
    ordered = sorted(
        snapshots,
        key=lambda item: item.get("snapshot_month") or date.min,
        reverse=True,
    )
    if not ordered:
        return {"available": False, "reason": "Aucun instantané mensuel disponible.", "metrics": []}

    current = ordered[0]
    previous = ordered[1] if len(ordered) > 1 else None
    definitions = (
        ("critical_without_current_assessment", "Fournisseurs critiques sans évaluation à jour",
         ("suppliers", "critical_without_current_assessment"), "higher_is_worse"),
        ("overdue_assessments", "Revues d'évaluation en retard",
         ("assessments", "overdue_reviews"), "higher_is_worse"),
        ("overdue_access_reviews", "Revues d'accès en retard",
         ("access", "overdue_reviews"), "higher_is_worse"),
        ("missing_security_clauses", "Contrats avec clauses SSI manquantes",
         ("contracts", "with_missing_security_clauses"), "higher_is_worse"),
        ("contracts_expiring_90d", "Contrats arrivant à échéance sous 90 jours",
         ("contracts", "expiring_within_90_days"), "context"),
        ("privileged_active_access", "Autorisations d'accès privilégié actives",
         ("access", "privileged_active"), "context"),
        ("distinct_linked_risks", "Risques distincts liés aux fournisseurs",
         ("risks", "distinct_linked"), "context"),
    )

    def read_metric(snapshot: dict[str, Any], path: tuple[str, str]) -> int | float | None:
        value: Any = snapshot.get("indicators", {})
        for part in path:
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    metrics = []
    for key, label, path, direction in definitions:
        current_value = read_metric(current, path)
        previous_value = read_metric(previous, path) if previous else None
        delta = current_value - previous_value if current_value is not None and previous_value is not None else None
        if delta is None:
            trend = "insufficient_data"
        elif delta == 0:
            trend = "stable"
        elif direction == "higher_is_worse":
            trend = "deteriorating" if delta > 0 else "improving"
        else:
            trend = "change"
        metrics.append({
            "key": key, "label": label, "current": current_value,
            "previous": previous_value, "delta": delta,
            "direction": direction, "trend": trend,
        })

    return {
        "available": True,
        "current_month": current.get("snapshot_month"),
        "previous_month": previous.get("snapshot_month") if previous else None,
        "comparison_available": previous is not None,
        "metrics": metrics,
        "interpretation": (
            "La comparaison décrit des évolutions d'indicateurs. "
            "Elle ne constitue pas une cotation automatique et ne modifie pas le registre central des risques."
        ),
    }


def build_supplier_risk_concentration(
    supplier_risk_rows: list[dict[str, Any]],
    supplier_access_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank active suppliers by linked central-risk exposure, without scoring suppliers."""
    grouped: dict[Any, dict[str, Any]] = {}
    for row in supplier_risk_rows:
        supplier_id = row["supplier_id"]
        item = grouped.setdefault(supplier_id, {
            "supplier_id": str(supplier_id),
            "supplier_code": row["supplier_code"],
            "supplier_name": row["supplier_name"],
            "criticality": row["criticality"],
            "linked_risk_ids": set(),
            "highest_linked_risk_level": None,
            "risk_levels": {"inacceptable": 0, "critique": 0, "eleve": 0, "modere": 0, "faible": 0},
            "active_privileged_accesses": 0,
        })
        risk_id = row.get("risk_id")
        if risk_id is not None and risk_id not in item["linked_risk_ids"]:
            item["linked_risk_ids"].add(risk_id)
            score = row.get("risk_level")
            if isinstance(score, (int, float)):
                item["highest_linked_risk_level"] = (
                    score if item["highest_linked_risk_level"] is None
                    else max(item["highest_linked_risk_level"], score)
                )
                bucket = "inacceptable" if score >= 20 else "critique" if score >= 15 else "eleve" if score >= 10 else "modere" if score >= 5 else "faible"
                item["risk_levels"][bucket] += 1

    for row in supplier_access_rows:
        item = grouped.get(row["supplier_id"])
        if item is not None and row.get("access_level") == "Privilégié":
            item["active_privileged_accesses"] += 1

    result = []
    for item in grouped.values():
        item["linked_risk_count"] = len(item.pop("linked_risk_ids"))
        result.append(item)
    result.sort(
        key=lambda item: (
            item["highest_linked_risk_level"] if item["highest_linked_risk_level"] is not None else -1,
            item["linked_risk_count"],
            item["active_privileged_accesses"],
            item["supplier_name"].casefold(),
        ),
        reverse=True,
    )
    return result
