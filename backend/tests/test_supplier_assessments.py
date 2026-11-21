import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.api.v1.endpoints.suppliers import SupplierAssessmentCreate, SupplierAssessmentAnswers
from app.models.supplier import SupplierAssessment
from app.services.supplier_assessment import calculate_assessment_score, validate_answers
from app.utils.rbac import role_has_permission

QUESTIONS = [
    {"id": "access", "label": "Gestion des accès", "weight": 2, "max_score": 5, "required": True},
    {"id": "backup", "label": "Sauvegardes", "weight": 1, "max_score": 5, "required": True},
    {"id": "optional", "label": "Question facultative", "weight": 1, "max_score": 5, "required": False},
]

def test_assessment_create_preserves_questionnaire_snapshot():
    data = SupplierAssessmentCreate(scope="Périmètre de la prestation", questionnaire_version="CTF-TPRM-1.0", questionnaire_snapshot=QUESTIONS)
    assert data.questionnaire_version == "CTF-TPRM-1.0"
    assert data.questionnaire_snapshot[0].weight == 2

def test_assessment_rejects_duplicate_question_ids():
    with pytest.raises(ValidationError):
        SupplierAssessmentCreate(scope="Périmètre de la prestation", questionnaire_version="1.0", questionnaire_snapshot=[QUESTIONS[0], QUESTIONS[0]])

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