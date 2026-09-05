import json

from challenges.models import ChallengeStatus
from django.conf import settings
from startups.models import EvidenceType, Startup

from intelligence.ollama import OllamaError, generate_text

from .models import (
    AIEvaluation,
    Application,
    ApplicationStatus,
    EvaluationRecommendation,
    HumanEvaluation,
)


def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lower() for item in value]
    return [str(value).strip().lower()]


def check_application_eligibility(application: Application):
    """MVP deterministic eligibility engine."""
    challenge = application.challenge
    startup = application.startup
    failures = []

    if challenge.status != ChallengeStatus.OPEN:
        failures.append("The challenge is no longer open for applications.")

    if not startup.company_name.strip():
        failures.append("Startup company name is missing from the Startup Passport.")

    requirements = challenge.requirements
    if not isinstance(requirements, dict):
        requirements = {}

    minimum_team_size = requirements.get("minimum_team_size")
    if minimum_team_size is not None:
        if startup.team_size is None:
            failures.append("Startup team size is required for this challenge.")
        elif startup.team_size < minimum_team_size:
            failures.append(
                f"Minimum team size is {minimum_team_size}; startup has {startup.team_size}."
            )

    required_industries = _normalize_list(requirements.get("required_industries"))
    if required_industries:
        startup_industry = (startup.industry or "").strip().lower()
        if startup_industry not in required_industries:
            failures.append(
                "Startup industry does not satisfy the challenge's required industries."
            )

    required_technologies = set(_normalize_list(requirements.get("required_technologies")))
    if required_technologies:
        startup_technologies = set(_normalize_list(startup.technologies))
        missing = sorted(required_technologies - startup_technologies)
        if missing:
            failures.append("Startup is missing required technologies: " + ", ".join(missing) + ".")

    if requirements.get("government_experience_required") is True:
        has_verified_gov_pilot = startup.evidence.filter(
            evidence_type=EvidenceType.GOVERNMENT_PILOT,
            verified=True,
        ).exists()
        if not has_verified_gov_pilot:
            failures.append("Verified government-pilot evidence is required for this challenge.")

    eligible = not failures
    reason = "All configured eligibility requirements passed." if eligible else " ".join(failures)
    application.eligibility_status = eligible
    application.eligibility_reason = reason
    application.transition_to(
        ApplicationStatus.ELIGIBLE if eligible else ApplicationStatus.INELIGIBLE
    )
    application.save(update_fields=["status", "eligibility_status", "eligibility_reason", "updated_at"])
    return application


def _evaluation_context(application: Application) -> str:
    startup = application.startup
    evidence = startup.evidence.filter(verified=True).values(
        "evidence_type", "title", "description"
    )[:15]
    evidence_text = [
        {
            "type": item["evidence_type"],
            "title": item["title"],
            "description": item["description"],
        }
        for item in evidence
    ]
    challenge = application.challenge

    return json.dumps(
        {
            "challenge": {
                "title": challenge.title,
                "problem_statement": challenge.problem_statement,
                "desired_outcome": challenge.desired_outcome,
                "requirements": challenge.requirements,
                "constraints": challenge.constraints,
            },
            "startup": {
                "company_name": startup.company_name,
                "description": startup.description,
                "industry": startup.industry,
                "technologies": startup.technologies,
                "location": startup.location,
                "founded_year": startup.founded_year,
                "team_size": startup.team_size,
            },
            "application": {
                "proposal": application.proposal,
            },
            "verified_evidence": evidence_text,
        },
        ensure_ascii=False,
        indent=2,
    )


def _parse_ai_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama returned invalid JSON for AI evaluation.") from exc

    if not isinstance(data, dict):
        raise OllamaError("Ollama AI evaluation response must be a JSON object.")
    return data


def _score(data: dict, field: str) -> int:
    value = data.get(field)
    if isinstance(value, bool):
        raise OllamaError(f"AI evaluation field '{field}' must be a score from 0 to 10.")
    try:
        score = int(value)
    except (TypeError, ValueError) as exc:
        raise OllamaError(f"AI evaluation field '{field}' must be a score from 0 to 10.") from exc
    if not 0 <= score <= 10:
        raise OllamaError(f"AI evaluation field '{field}' must be a score from 0 to 10.")
    return score


def _string_list(data: dict, field: str) -> list[str]:
    value = data.get(field, [])
    if not isinstance(value, list):
        raise OllamaError(f"AI evaluation field '{field}' must be an array.")
    return [str(item).strip() for item in value if str(item).strip()]


def generate_ai_evaluation(application: Application) -> AIEvaluation:
    """Generate an advisory AI evaluation using local Ollama/Qwen."""
    prompt = f"""You are an evaluation assistant for a government innovation procurement platform.
Use ONLY the supplied challenge, startup, application, and verified evidence.
Do not invent qualifications, deployments, certifications, technologies, costs, or outcomes.
Do not make the final procurement decision. Recommend SELECT, REJECT, or REVIEW as advisory guidance only.
Return ONLY valid JSON. Keep arrays concise and the explanation under 120 words.
All scores must be integers from 0 to 10.

Required JSON schema:
{{
  "technical_score": 0,
  "innovation_score": 0,
  "feasibility_score": 0,
  "scalability_score": 0,
  "evidence_score": 0,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "missing_evidence": ["..."],
  "recommendation": "SELECT|REJECT|REVIEW",
  "explanation": "..."
}}

Source data:
{_evaluation_context(application)}
"""
    raw = generate_text(prompt)
    data = _parse_ai_json(raw)
    recommendation = str(data.get("recommendation", "REVIEW")).upper()
    if recommendation not in EvaluationRecommendation.values:
        raise OllamaError("AI evaluation recommendation must be SELECT, REJECT, or REVIEW.")

    evaluation, _ = AIEvaluation.objects.update_or_create(
        application=application,
        defaults={
            "technical_score": _score(data, "technical_score"),
            "innovation_score": _score(data, "innovation_score"),
            "feasibility_score": _score(data, "feasibility_score"),
            "scalability_score": _score(data, "scalability_score"),
            "evidence_score": _score(data, "evidence_score"),
            "strengths": _string_list(data, "strengths"),
            "weaknesses": _string_list(data, "weaknesses"),
            "missing_evidence": _string_list(data, "missing_evidence"),
            "recommendation": recommendation,
            "explanation": str(data.get("explanation", "")).strip(),
            "model_name": settings.OLLAMA_GENERATION_MODEL,
        },
    )
    if not evaluation.explanation:
        raise OllamaError("AI evaluation explanation cannot be empty.")
    return evaluation


def human_evaluation_summary(application: Application) -> dict:
    evaluations = list(application.human_evaluations.all())
    count = len(evaluations)
    if not count:
        return {
            "count": 0,
            "average_score": None,
            "recommendations": {value: 0 for value in EvaluationRecommendation.values},
        }

    average = round(sum(item.overall_score for item in evaluations) / count, 2)
    recommendations = {value: 0 for value in EvaluationRecommendation.values}
    for item in evaluations:
        recommendations[item.recommendation] += 1

    return {
        "count": count,
        "average_score": average,
        "recommendations": recommendations,
    }


def selection_summary(application: Application) -> dict:
    ai = getattr(application, "ai_evaluation", None)
    human = human_evaluation_summary(application)
    human_average = human["average_score"]
    ai_score = ai.overall_score if ai else None

    combined = None
    if ai_score is not None and human_average is not None:
        combined = round((ai_score + human_average) / 2, 2)
    elif human_average is not None:
        combined = human_average
    elif ai_score is not None:
        combined = ai_score

    return {
        "application_id": str(application.id),
        "status": application.status,
        "ai_score": ai_score,
        "human_evaluation_count": human["count"],
        "human_average_score": human_average,
        "combined_score": combined,
        "human_recommendations": human["recommendations"],
        "selection_ready": human["count"] > 0,
    }
