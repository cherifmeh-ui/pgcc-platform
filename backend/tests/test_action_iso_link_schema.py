from app.api.v1.endpoints.actions import ActionCreate, ActionUpdate


def test_action_create_accepts_iso_control_reference():
    payload = ActionCreate(
        risk_id="00000000-0000-0000-0000-000000000001",
        title="Mettre en place une revue des accès",
        iso_control_ref="A.5.18",
        iso_assessment_id="00000000-0000-0000-0000-000000000002",
    )
    assert payload.iso_control_ref == "A.5.18"
    assert payload.iso_assessment_id is not None


def test_action_update_allows_clearing_iso_traceability():
    payload = ActionUpdate(iso_control_ref=None, iso_assessment_id=None)
    assert "iso_control_ref" in payload.model_fields_set
    assert payload.iso_control_ref is None
