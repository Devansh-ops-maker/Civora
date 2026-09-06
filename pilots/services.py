import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone

from evaluations.models import Application, ApplicationStatus
from intelligence.ollama import OllamaError, generate_text

from .models import Milestone, Pilot


def _parse_json(raw):
    text = (raw or "").strip()
    # Remove fenced code blocks if present
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        # drop first and last fence lines
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    # Try to extract the first top-level JSON object in the text
    match = re.search(r"({[\s\S]*})", text)
    if match:
        text = match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama returned invalid JSON for the pilot plan.") from exc


def _normalize_plan(data: dict) -> dict:
    """Normalize types in the AI-generated plan and validate basic shapes.

    Ensures numeric fields are converted to Decimal/int and clamps milestone due_days.
    """
    if not isinstance(data, dict):
        raise OllamaError("Pilot plan must be a JSON object.")

    required = [
        "title",
        "description",
        "objectives",
        "success_criteria",
        "data_requirements",
        "milestones",
    ]
    missing = [k for k in required if k not in data]
    if missing:
        raise OllamaError("Pilot plan is missing required fields: " + ", ".join(missing))

    plan = dict(data)

    # Budget: allow null, number, or numeric string
    budget = plan.get("budget")
    if budget in (None, "", "null"):
        plan["budget"] = None
    else:
        try:
            plan["budget"] = Decimal(str(budget))
        except (InvalidOperation, TypeError):
            raise OllamaError("Pilot plan 'budget' must be a number or null.")

    # Duration days
    try:
        plan["duration_days"] = int(plan.get("duration_days", 90) or 90)
    except (TypeError, ValueError):
        raise OllamaError("Pilot plan 'duration_days' must be an integer number of days.")

    duration = plan["duration_days"]

    # Milestones normalization
    normalized_milestones = []
    milestones = plan.get("milestones") or []
    if not isinstance(milestones, list):
        raise OllamaError("Pilot plan 'milestones' must be an array.")
    for item in milestones:
        if not isinstance(item, dict):
            raise OllamaError("Each milestone must be an object.")
        title = str(item.get("title", "Pilot milestone"))[:255]
        description = str(item.get("description", ""))
        # amount default 0
        try:
            amount = Decimal(str(item.get("amount", 0) or 0))
        except (InvalidOperation, TypeError):
            raise OllamaError("Milestone 'amount' must be a numeric value.")
        if amount < 0:
            raise OllamaError("Milestone 'amount' cannot be negative.")
        try:
            due_day = int(item.get("due_day", duration) or duration)
        except (TypeError, ValueError):
            raise OllamaError("Milestone 'due_day' must be an integer.")
        # clamp due_day between 0 and duration
        due_day = max(0, min(due_day, duration))
        normalized_milestones.append({
            "title": title,
            "description": description,
            "amount": amount,
            "due_day": due_day,
        })

    plan["milestones"] = normalized_milestones

    # Ensure lists
    plan["objectives"] = list(plan.get("objectives") or [])
    plan["success_criteria"] = list(plan.get("success_criteria") or [])
    plan["data_requirements"] = list(plan.get("data_requirements") or [])

    return plan


def generate_pilot_plan(application: Application) -> dict:
    if application.status != ApplicationStatus.SELECTED:
        raise ValidationError("A pilot can only be generated for a selected application.")

    challenge = application.challenge
    startup = application.startup
    prompt = f"""You are the pilot-planning assistant for a government innovation procurement platform.
Create a concise pilot plan using ONLY the supplied facts. Do not invent certifications, deployments,
budgets, technologies, or government policies. Return ONLY valid JSON.

Challenge:
Title: {challenge.title}
Problem: {challenge.problem_statement}
Desired outcome: {challenge.desired_outcome}
Requirements: {json.dumps(challenge.requirements, ensure_ascii=False)}
Constraints: {json.dumps(challenge.constraints, ensure_ascii=False)}
Budget: {challenge.budget}
Application deadline: {challenge.application_deadline}

Startup:
Company: {startup.company_name}
Description: {startup.description}
Industry: {startup.industry}
Technologies: {json.dumps(startup.technologies, ensure_ascii=False)}

Return exactly this shape:
{{
  "title": "...",
  "description": "...",
  "objectives": ["..."],
  "budget": null,
  "duration_days": 90,
  "success_criteria": ["..."],
  "data_requirements": ["..."],
  "milestones": [
    {{"title": "...", "description": "...", "amount": 0, "due_day": 30}}
  ]
}}
"""
    raw = generate_text(prompt)
    data = _parse_json(raw)
    # Normalize types and validate plan contents
    plan = _normalize_plan(data)
    return plan


def create_pilot_from_plan(application: Application, plan: dict, created_by) -> Pilot:
    if application.status != ApplicationStatus.SELECTED:
        raise ValidationError("A pilot can only be created for a selected application.")
    if Pilot.objects.filter(application=application).exists():
        raise ValidationError("A pilot already exists for this application.")

    # Expect a normalized plan (numbers as Decimal/int)
    budget = plan.get("budget") if plan.get("budget") is not None else application.challenge.budget
    duration_days = int(plan.get("duration_days", 90))
    # Ensure budget is Decimal or None
    if budget is not None and not isinstance(budget, Decimal):
        try:
            budget = Decimal(str(budget))
        except (InvalidOperation, TypeError):
            raise ValidationError("Pilot budget must be a numeric value or null.")

    pilot = Pilot.objects.create(
        application=application,
        challenge=application.challenge,
        startup=application.startup,
        created_by=created_by,
        title=str(plan["title"])[:255],
        description=str(plan["description"]),
        objectives=plan.get("objectives", []),
        budget=budget,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=duration_days),
        success_criteria=plan.get("success_criteria", []),
        data_requirements=plan.get("data_requirements", []),
    )
    # Validate model constraints
    pilot.full_clean()

    for item in plan.get("milestones", []):
        amount = item.get("amount", Decimal(0))
        due_day = int(item.get("due_day", duration_days))
        Milestone.objects.create(
            pilot=pilot,
            title=str(item.get("title", "Pilot milestone"))[:255],
            description=str(item.get("description", "")),
            amount=amount,
            due_date=date.today() + timedelta(days=min(max(due_day, 0), duration_days)),
        )

    return pilot


def submit_milestone(milestone: Milestone):
    if milestone.status != "PENDING":
        raise ValidationError("Only pending milestones can be submitted.")
    milestone.transition_to("SUBMITTED")
    milestone.submitted_at = timezone.now()
    milestone.save(update_fields=["status", "submitted_at", "updated_at"])
    return milestone


from decimal import Decimal

from .models import KPIStatus, OutcomeDecision, OutcomeRecommendation, RiskFlag, RiskSeverity, RiskStatus, Simulation


def run_pre_pilot_simulation(pilot, assumptions=None):
    assumptions = assumptions or {}
    predicted = {}
    for kpi in pilot.kpis.all():
        baseline = kpi.baseline
        target = kpi.target
        if target is None:
            continue
        improvement_factor = Decimal(str(assumptions.get("expected_progress", 0.9)))
        if baseline is None:
            predicted_value = target
        else:
            predicted_value = baseline + ((target - baseline) * improvement_factor)
        predicted[str(kpi.id)] = {
            "kpi": kpi.name,
            "baseline": float(baseline) if baseline is not None else None,
            "target": float(target),
            "predicted": float(predicted_value),
            "unit": kpi.unit,
        }
    simulation, _ = Simulation.objects.update_or_create(
        pilot=pilot,
        defaults={"assumptions": assumptions, "predicted_results": predicted},
    )
    return simulation


def generate_risk_flags(pilot):
    RiskFlag.objects.filter(pilot=pilot, status=RiskStatus.OPEN).delete()
    flags = []
    if pilot.data_requirements:
        text = " ".join(map(str, pilot.data_requirements)).lower()
        if any(term in text for term in ["pii", "personal data", "patient", "citizen"]):
            flags.append(("DATA", RiskSeverity.HIGH, "Potential PII exposure", "Pilot data requirements may involve personal or sensitive information.", "Use anonymization and restrict processing to approved government infrastructure."))
    if pilot.budget is not None:
        milestone_total = sum((m.amount for m in pilot.milestones.all()), Decimal("0"))
        if milestone_total > pilot.budget:
            flags.append(("FINANCIAL", RiskSeverity.HIGH, "Milestones exceed pilot budget", "The sum of milestone amounts exceeds the approved pilot budget.", "Reduce milestone commitments or revise the approved budget before activation."))
    if not pilot.kpis.exists():
        flags.append(("MEASUREMENT", RiskSeverity.HIGH, "No measurable KPIs defined", "The pilot has no KPI records, making outcome validation difficult.", "Define at least one baseline, target, and measurable KPI before completion."))
    created = []
    for category, severity, title, reason, mitigation in flags:
        created.append(RiskFlag.objects.create(pilot=pilot, category=category, severity=severity, title=title, reason=reason, mitigation=mitigation))
    return created


def compute_outcome_decision(pilot, generated_by):
    kpis = list(pilot.kpis.all())
    summary = {"total": len(kpis), "achieved": 0, "partially_achieved": 0, "failed": 0, "not_measured": 0}
    for kpi in kpis:
        status = kpi.evaluate()
        summary[{
            KPIStatus.ACHIEVED: "achieved",
            KPIStatus.PARTIALLY_ACHIEVED: "partially_achieved",
            KPIStatus.FAILED: "failed",
            KPIStatus.NOT_MEASURED: "not_measured",
        }[status]] += 1

    risks = list(pilot.risk_flags.filter(status=RiskStatus.OPEN))
    risk_summary = {"open": len(risks), "high_or_critical": sum(r.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL} for r in risks)}

    if not kpis or summary["not_measured"]:
        recommendation = OutcomeRecommendation.EXTEND_PILOT
        rationale = "Extend the pilot because KPI evidence is incomplete or not yet measurable."
    elif summary["achieved"] == len(kpis) and risk_summary["high_or_critical"] == 0:
        recommendation = OutcomeRecommendation.SCALE
        rationale = "Scale because all measured KPIs achieved their targets and no high or critical risks remain open."
    elif summary["failed"] > len(kpis) / 2 or risk_summary["high_or_critical"] > 0:
        recommendation = OutcomeRecommendation.STOP
        rationale = "Stop because multiple KPIs failed or a high/critical risk remains unresolved."
    else:
        recommendation = OutcomeRecommendation.EXTEND_PILOT
        rationale = "Extend the pilot because the results are promising but not strong enough for immediate scale."

    decision, _ = OutcomeDecision.objects.update_or_create(
        pilot=pilot,
        defaults={
            "recommendation": recommendation,
            "rationale": rationale,
            "kpi_summary": summary,
            "risk_summary": risk_summary,
            "generated_by": generated_by,
        },
    )
    return decision
