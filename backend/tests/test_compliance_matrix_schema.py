from app.api.v1.endpoints.compliance import ComplianceMatrixRow


def test_compliance_matrix_row_includes_explicit_action_links():
    row = ComplianceMatrixRow(
        control_id=12,
        ref_code="A.5.18",
        title="Access rights",
        domain="Organisation",
        status="À vérifier",
        linked_risks_count=2,
        linked_actions_count=3,
        last_update=None,
        evidence_count=1,
        verified_evidence_count=1,
        expired_evidence_count=0,
    )
    assert row.control_id == 12
    assert row.linked_actions_count == 3
