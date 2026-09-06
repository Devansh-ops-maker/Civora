import json
from typing import Iterable

from django.conf import settings
from django.db.models import F
from pgvector.django import CosineDistance

from challenges.models import Challenge
from startups.models import Startup, StartupEvidence

from .ollama import OllamaError, embed_text, generate_text


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _lower_set(value):
    return {item.lower() for item in _as_list(value)}


def challenge_embedding_text(challenge: Challenge) -> str:
    requirements = challenge.requirements
    constraints = challenge.constraints
    return "\n".join(
        [
            f"Title: {challenge.title}",
            f"Problem: {challenge.problem_statement}",
            f"Desired outcome: {challenge.desired_outcome}",
            f"Requirements: {json.dumps(requirements, sort_keys=True, ensure_ascii=False)}",
            f"Constraints: {json.dumps(constraints, sort_keys=True, ensure_ascii=False)}",
        ]
    )


def startup_embedding_text(startup: Startup) -> str:
    evidence = startup.evidence.filter(verified=True).values_list(
        "title", "description", "evidence_type"
    )[:10]
    evidence_lines = [
        f"{kind}: {title} - {description}"
        for title, description, kind in evidence
    ]
    return "\n".join(
        [
            f"Company: {startup.company_name}",
            f"Description: {startup.description}",
            f"Industry: {startup.industry}",
            f"Technologies: {json.dumps(startup.technologies, ensure_ascii=False)}",
            f"Location: {startup.location}",
            f"Founded: {startup.founded_year}",
            f"Team size: {startup.team_size}",
            "Verified evidence:",
            *evidence_lines,
        ]
    )


def update_challenge_embedding(challenge: Challenge) -> Challenge:
    challenge.embedding = embed_text(challenge_embedding_text(challenge))
    challenge.save(update_fields=["embedding", "updated_at"])
    return challenge


def update_startup_embedding(startup: Startup) -> Startup:
    startup.embedding = embed_text(startup_embedding_text(startup))
    startup.save(update_fields=["embedding", "updated_at"])
    return startup


def _passes_hard_eligibility(challenge: Challenge, startup: Startup) -> bool:
    requirements = challenge.requirements if isinstance(challenge.requirements, dict) else {}

    minimum_team_size = requirements.get("minimum_team_size")
    if minimum_team_size is not None:
        if startup.team_size is None or startup.team_size < minimum_team_size:
            return False

    required_industries = _lower_set(requirements.get("required_industries"))
    if required_industries and startup.industry.strip().lower() not in required_industries:
        return False

    required_technologies = _lower_set(requirements.get("required_technologies"))
    startup_technologies = _lower_set(startup.technologies)
    if required_technologies - startup_technologies:
        return False

    if requirements.get("government_experience_required") is True:
        has_verified_gov_pilot = startup.evidence.filter(
            evidence_type="GOVERNMENT_PILOT", verified=True
        ).exists()
        if not has_verified_gov_pilot:
            return False

    return True


def _technology_fit(challenge: Challenge, startup: Startup) -> tuple[float, list[str]]:
    requirements = challenge.requirements if isinstance(challenge.requirements, dict) else {}
    required = _lower_set(requirements.get("required_technologies"))
    actual = _lower_set(startup.technologies)
    if not required:
        return 50.0, []
    overlap = sorted(required & actual)
    return (len(overlap) / len(required) * 100.0), overlap


def _domain_fit(challenge: Challenge, startup: Startup) -> float:
    requirements = challenge.requirements if isinstance(challenge.requirements, dict) else {}
    required = _lower_set(requirements.get("required_industries"))
    if not required:
        return 50.0
    return 100.0 if startup.industry.strip().lower() in required else 0.0


def _pilot_readiness(startup: Startup) -> float:
    profile_fields = [
        bool(startup.company_name.strip()),
        bool(startup.description.strip()),
        bool(startup.industry.strip()),
        bool(startup.technologies),
        bool(startup.location.strip()),
        startup.founded_year is not None,
        startup.team_size is not None,
    ]
    profile_score = sum(profile_fields) / len(profile_fields) * 60.0
    evidence_score = min(startup.verified_evidence_count * 10.0, 40.0)
    return min(profile_score + evidence_score, 100.0)


def _evidence_score(startup: Startup) -> float:
    # 10 verified evidence records saturate the score at 100.
    return min(startup.verified_evidence_count * 10.0, 100.0)


def rank_startups(challenge: Challenge, limit: int = 10) -> list[dict]:
    if challenge.embedding is None:
        try:
            update_challenge_embedding(challenge)
        except OllamaError as exc:
            raise OllamaError(
                "Challenge embedding is missing and could not be generated automatically. "
                "Ensure Ollama is running."
            ) from exc

    candidates = (
        Startup.objects.select_related("user")
        .prefetch_related("evidence")
        .filter(embedding__isnull=False)
        .annotate(distance=CosineDistance("embedding", challenge.embedding))
        .order_by("distance")[: max(limit * 3, 20)]
    )

    matches = []
    for startup in candidates:
        if not _passes_hard_eligibility(challenge, startup):
            continue

        semantic = max(0.0, min(100.0, (1.0 - float(startup.distance)) * 100.0))
        technology, overlap = _technology_fit(challenge, startup)
        domain = _domain_fit(challenge, startup)
        readiness = _pilot_readiness(startup)
        evidence = _evidence_score(startup)

        # Explainable deterministic score. Semantic similarity is the first
        # filter and remains the largest single component.
        match_score = (
            semantic * 0.40
            + technology * 0.25
            + domain * 0.15
            + readiness * 0.10
            + evidence * 0.10
        )

        reasons = []
        risks = []
        if semantic >= 75:
            reasons.append("Strong semantic match with the challenge.")
        elif semantic >= 55:
            reasons.append("Moderate semantic match with the challenge.")
        else:
            risks.append("Lower semantic similarity than other candidates.")

        if overlap:
            reasons.append("Matches required technologies: " + ", ".join(overlap) + ".")
        elif isinstance(challenge.requirements, dict) and challenge.requirements.get("required_technologies"):
            risks.append("Does not match all required technologies.")

        if domain == 100:
            reasons.append("Industry matches the challenge requirements.")
        elif isinstance(challenge.requirements, dict) and challenge.requirements.get("required_industries"):
            risks.append("Industry does not match the configured challenge requirement.")

        if startup.verified_evidence_count == 0:
            risks.append("No verified startup evidence is available.")

        matches.append(
            {
                "startup_id": startup.id,
                "company_name": startup.company_name,
                "industry": startup.industry,
                "technologies": _as_list(startup.technologies),
                "semantic_similarity": round(semantic, 2),
                "technology_fit": round(technology, 2),
                "domain_fit": round(domain, 2),
                "pilot_readiness": round(readiness, 2),
                "evidence_score": round(evidence, 2),
                "match_score": round(match_score, 2),
                "match_reasons": reasons,
                "risks": risks,
            }
        )

    matches.sort(key=lambda item: (-item["match_score"], -item["semantic_similarity"], item["company_name"].lower()))
    return matches[:limit]


def explain_matches(challenge: Challenge, matches: Iterable[dict]) -> list[dict]:
    compact = []
    for match in matches:
        compact.append(
            {
                "startup_id": str(match["startup_id"]),
                "company_name": match["company_name"],
                "industry": match["industry"],
                "technologies": match["technologies"],
                "scores": {
                    "semantic_similarity": match["semantic_similarity"],
                    "technology_fit": match["technology_fit"],
                    "domain_fit": match["domain_fit"],
                    "pilot_readiness": match["pilot_readiness"],
                    "evidence_score": match["evidence_score"],
                    "match_score": match["match_score"],
                },
                "reasons": match["match_reasons"],
                "risks": match["risks"],
            }
        )

    prompt = f"""You are the explanation layer for a government innovation procurement platform.
Explain the ranked startup matches below using ONLY the supplied facts. Do not invent
deployments, certifications, experience, products, costs, or capabilities.

Challenge:
{challenge_embedding_text(challenge)}

Candidates:
{json.dumps(compact, indent=2, ensure_ascii=False)}

Return ONLY valid JSON as an array. For each candidate return:
{{
  "startup_id": "...",
  "explanation": "1-3 concise sentences",
  "strengths": ["..."],
  "concerns": ["..."]
}}
"""

    raw = generate_text(prompt)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama returned invalid JSON for startup explanations.") from exc

    if not isinstance(data, list):
        raise OllamaError("Ollama explanation response must be a JSON array.")
    return data
