import json
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from evaluations.models import Application, ApplicationStatus
from intelligence.ollama import OllamaError, generate_text

from .models import Milestone, Pilot


def _parse_json(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama returned invalid JSON for the pilot plan.") from exc


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
    required = ["title", "description", "objectives", "success_criteria", "data_requirements", "milestones"]
    missing = [key for key in required if key not in data]
    if missing:
        raise OllamaError("Pilot plan is missing required fields: " + ", ".join(missing))
    return data


def create_pilot_from_plan(application: Application, plan: dict, created_by) -> Pilot:
    if application.status != ApplicationStatus.SELECTED:
        raise ValidationError("A pilot can only be created for a selected application.")
    if Pilot.objects.filter(application=application).exists():
        raise ValidationError("A pilot already exists for this application.")

    budget = plan.get("budget", application.challenge.budget)
    duration_days = int(plan.get("duration_days", 90))
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
    pilot.full_clean()

    for item in plan.get("milestones", []):
        amount = item.get("amount", 0)
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
