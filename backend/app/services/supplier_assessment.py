"""Deterministic scoring and validation for versioned supplier questionnaires."""
from decimal import Decimal, ROUND_HALF_UP
from copy import deepcopy

QUESTIONNAIRES = {
    "CTF-TPRM-1.0": [
        {"id": "governance", "label": "Gouvernance SSI et responsabilités définies", "weight": 3, "max_score": 5, "required": True},
        {"id": "access", "label": "Gestion des identités, authentification et accès privilégiés", "weight": 3, "max_score": 5, "required": True},
        {"id": "incident", "label": "Détection, gestion et notification des incidents", "weight": 3, "max_score": 5, "required": True},
        {"id": "continuity", "label": "Continuité d’activité, sauvegardes et reprise", "weight": 3, "max_score": 5, "required": True},
        {"id": "vulnerability", "label": "Gestion des vulnérabilités et mises à jour", "weight": 2, "max_score": 5, "required": True},
        {"id": "data", "label": "Protection, confidentialité et localisation des données", "weight": 3, "max_score": 5, "required": True},
        {"id": "subcontracting", "label": "Maîtrise des sous-traitants ultérieurs", "weight": 2, "max_score": 5, "required": True},
        {"id": "audit", "label": "Preuves, auditabilité et conformité contractuelle", "weight": 2, "max_score": 5, "required": True},
    ],
}


def get_questionnaire_snapshot(version: str) -> list[dict]:
    if version not in QUESTIONNAIRES:
        raise ValueError("Version de questionnaire inconnue ou non publiée")
    return deepcopy(QUESTIONNAIRES[version])

def validate_questionnaire(questions: list[dict]) -> None:
    if not questions:
        raise ValueError("Le questionnaire doit contenir au moins une question")
    ids = set()
    for question in questions:
        question_id = question.get("id")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError("Chaque question doit avoir un identifiant")
        if question_id in ids:
            raise ValueError("Les identifiants de questions doivent être uniques")
        ids.add(question_id)
        weight, maximum = question.get("weight"), question.get("max_score", 5)
        if not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= 10:
            raise ValueError(f"Pondération invalide pour la question {question_id}")
        if not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= 5:
            raise ValueError(f"Score maximal invalide pour la question {question_id}")

def validate_answers(questions: list[dict], answers: list[dict], require_all_required: bool) -> None:
    validate_questionnaire(questions)
    question_map = {q["id"]: q for q in questions}
    seen = set()
    for answer in answers:
        qid = answer.get("question_id")
        if qid not in question_map:
            raise ValueError(f"Question inconnue : {qid}")
        if qid in seen:
            raise ValueError(f"Réponse dupliquée : {qid}")
        seen.add(qid)
        score, maximum = answer.get("score"), question_map[qid].get("max_score", 5)
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= maximum:
            raise ValueError(f"Score hors limites pour la question {qid}")
    if require_all_required:
        missing = [q["id"] for q in questions if q.get("required", True) and q["id"] not in seen]
        if missing:
            raise ValueError("Réponses obligatoires manquantes : " + ", ".join(missing))

def calculate_assessment_score(questions: list[dict], answers: list[dict]) -> tuple[Decimal, str]:
    validate_answers(questions, answers, require_all_required=True)
    question_map = {q["id"]: q for q in questions}
    weighted, total_weight = Decimal("0"), Decimal("0")
    for answer in answers:
        q = question_map[answer["question_id"]]
        weight, maximum = Decimal(str(q["weight"])), Decimal(str(q.get("max_score", 5)))
        weighted += Decimal(str(answer["score"])) / maximum * weight
        total_weight += weight
    if not total_weight:
        raise ValueError("Impossible de calculer un score sans réponse")
    score = (weighted / total_weight * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    risk = "Faible" if score >= 85 else "Moyen" if score >= 70 else "Élevé" if score >= 50 else "Critique"
    return score, risk