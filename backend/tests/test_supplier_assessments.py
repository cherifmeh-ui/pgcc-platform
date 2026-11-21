import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.api.v1.endpoints.suppliers import SupplierAssessmentCreate, SupplierAssessmentAnswers
from app.models.supplier import SupplierAssessment
from app.services.supplier_assessment import calculate_assessment_score, get_questionnaire_snapshot, validate_answers
from app.utils.rbac import role_has_permission

QUESTIONS = [
    {"id": "access", "label": "Gestion des accès", "weight": 2, "max_score": 5, "required": True},
    {"id": "backup", "label": "Sauvegardes", "weight": 1, "max_score": 5, "required": True},
    {"id": "optional", "label": "Question facultative", "weight": 1, "max_score": 5, "required": False},
]

def test_assessment_create_preserves_questionnaire_snapshot():
    data = SupplierAssessmentCreate(scope="Périmètre de la prestation", questionnaire_version="CTF-TPRM-1.0")
    snapshot = get_questionnaire_snapshot(data.questionnaire_version)
    assert data.questionnaire_version == "CTF-TPRM-1.0"
    assert snapshot[0]["weight"] == 3
    snapshot[0]["weight"] = 1
    assert get_questionnaire_snapshot(data.questionnaire_version)[0]["weight"] == 3

def test_assessment_rejects_unpublished_questionnaire_version():
    with pytest.raises(ValueError, match="inconnue"):
        get_questionnaire_snapshot("CUSTOM-UNTRUSTED")


def test_assessment_rejects_duplicate_answers():
    with pytest.raises(ValidationError):
        SupplierAssessmentAnswers(answers=[{"question_id": "access", "score": 4}, {"question_id": "access", "score": 3}])

def test_assessment_score_is_weighted_and_reproducible():
    score, risk = calculate_assessment_score(QUESTIONS, [{"question_id": "access", "score": 4}, {"question_id": "backup", "score": 3}])
    assert score == Decimal("73.33")
    assert risk == "Moyen"

def test_assessment_requires_mandatory_answers_before_submission():
    with pytest.raises(ValueError, match="obligatoires"):
        validate_answers(QUESTIONS, [{"question_id": "access", "score": 5}], True)

def test_assessment_rejects_score_above_question_maximum():
    with pytest.raises(ValueError, match="hors limites"):
        validate_answers(QUESTIONS, [{"question_id": "access", "score": 6}], False)

def test_assessment_model_constraints_and_permissions():
    assert SupplierAssessment.__tablename__ == "supplier_assessments"
    assert any(c.name == "ck_supplier_assessments_lifecycle" for c in SupplierAssessment.__table__.constraints)
    assert role_has_permission("admin", "suppliers", "assess")
    assert role_has_permission("admin", "suppliers", "validate_assessment")
    assert role_has_permission("auditor", "suppliers", "read_assessments")
    assert not role_has_permission("auditor", "suppliers", "assess")
    assert not role_has_permission("auditor", "suppliers", "validate_assessment")
@pytest.mark.asyncio
async def test_high_risk_assessment_cannot_be_approved():
    from unittest.mock import AsyncMock, MagicMock
    from uuid import UUID
    from fastapi import HTTPException
    from app.api.v1.endpoints.suppliers import validate_supplier_assessment, SupplierAssessmentValidation

    supplier_id = UUID("00000000-0000-0000-0000-000000000010")
    assessment_id = UUID("00000000-0000-0000-0000-000000000011")
    assessment = MagicMock(
        id=assessment_id, supplier_id=supplier_id, status="À valider",
        assessed_by_id=UUID("00000000-0000-0000-0000-000000000012"),
        risk_level="Critique",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = assessment
    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc:
        await validate_supplier_assessment(
            supplier_id=supplier_id, assessment_id=assessment_id,
            data=SupplierAssessmentValidation(decision="Approuvé", validation_comment="Validation test"),
            request=MagicMock(), db=db,
            current_user=MagicMock(id=UUID("00000000-0000-0000-0000-000000000013"), email="validator@example.test"),
        )
    assert exc.value.status_code == 422
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_assessment_evaluator_cannot_validate_own_assessment():
    from unittest.mock import AsyncMock, MagicMock
    from uuid import UUID
    from fastapi import HTTPException
    from app.api.v1.endpoints.suppliers import validate_supplier_assessment, SupplierAssessmentValidation

    supplier_id = UUID("00000000-0000-0000-0000-000000000010")
    assessment_id = UUID("00000000-0000-0000-0000-000000000011")
    evaluator_id = UUID("00000000-0000-0000-0000-000000000012")
    assessment = MagicMock(
        id=assessment_id, supplier_id=supplier_id, status="À valider",
        assessed_by_id=evaluator_id, risk_level="Moyen",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = assessment
    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc:
        await validate_supplier_assessment(
            supplier_id=supplier_id, assessment_id=assessment_id,
            data=SupplierAssessmentValidation(decision="Approuvé", validation_comment="Validation test"),
            request=MagicMock(), db=db,
            current_user=MagicMock(id=evaluator_id, email="evaluator@example.test"),
        )
    assert exc.value.status_code == 403
    db.commit.assert_not_awaited()
