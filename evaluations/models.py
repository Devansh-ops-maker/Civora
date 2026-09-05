import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ApplicationStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    ELIGIBILITY_CHECK = "ELIGIBILITY_CHECK", "Eligibility Check"
    ELIGIBLE = "ELIGIBLE", "Eligible"
    INELIGIBLE = "INELIGIBLE", "Ineligible"
    UNDER_EVALUATION = "UNDER_EVALUATION", "Under Evaluation"
    SELECTED = "SELECTED", "Selected"
    REJECTED = "REJECTED", "Rejected"


ALLOWED_APPLICATION_TRANSITIONS = {
    ApplicationStatus.SUBMITTED: {ApplicationStatus.ELIGIBILITY_CHECK},
    ApplicationStatus.ELIGIBILITY_CHECK: {
        ApplicationStatus.ELIGIBLE,
        ApplicationStatus.INELIGIBLE,
    },
    ApplicationStatus.ELIGIBLE: {ApplicationStatus.UNDER_EVALUATION},
    ApplicationStatus.UNDER_EVALUATION: {
        ApplicationStatus.SELECTED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.INELIGIBLE: set(),
    ApplicationStatus.SELECTED: set(),
    ApplicationStatus.REJECTED: set(),
}


class Application(models.Model):
    """A startup's application to a government challenge."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.ForeignKey(
        "challenges.Challenge",
        on_delete=models.CASCADE,
        related_name="applications",
    )
    startup = models.ForeignKey(
        "startups.Startup",
        on_delete=models.CASCADE,
        related_name="applications",
    )

    proposal = models.TextField(blank=True)

    status = models.CharField(
        max_length=30,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.SUBMITTED,
    )
    eligibility_status = models.BooleanField(null=True, blank=True)
    eligibility_reason = models.TextField(blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "applications"
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["challenge", "startup"],
                name="unique_application_per_challenge_startup",
            )
        ]
        indexes = [
            models.Index(fields=["challenge", "status"]),
            models.Index(fields=["startup", "status"]),
        ]

    def __str__(self):
        return f"{self.startup.company_name} → {self.challenge.title}"

    def can_transition_to(self, new_status):
        return new_status in ALLOWED_APPLICATION_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status):
        if new_status == self.status:
            raise ValidationError({"status": "Application is already in this status."})

        if not self.can_transition_to(new_status):
            raise ValidationError(
                {
                    "status": (
                        f"Cannot transition application from "
                        f"{self.status} to {new_status}."
                    )
                }
            )

        self.status = new_status


class EvaluationRecommendation(models.TextChoices):
    SELECT = "SELECT", "Select"
    REJECT = "REJECT", "Reject"
    REVIEW = "REVIEW", "Further Review"


class AIEvaluation(models.Model):
    """AI-generated evaluation assistance for an application.

    The AI does not make the final selection; this record is advisory and
    remains separate from human evaluator decisions for auditability.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="ai_evaluation",
    )
    technical_score = models.PositiveSmallIntegerField()
    innovation_score = models.PositiveSmallIntegerField()
    feasibility_score = models.PositiveSmallIntegerField()
    scalability_score = models.PositiveSmallIntegerField()
    evidence_score = models.PositiveSmallIntegerField()
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    missing_evidence = models.JSONField(default=list, blank=True)
    recommendation = models.CharField(
        max_length=10,
        choices=EvaluationRecommendation.choices,
        default=EvaluationRecommendation.REVIEW,
    )
    explanation = models.TextField()
    model_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_evaluations"
        ordering = ["-created_at"]

    @property
    def overall_score(self):
        return round(
            (
                self.technical_score
                + self.innovation_score
                + self.feasibility_score
                + self.scalability_score
                + self.evidence_score
            )
            / 5
            * 10,
            2,
        )

    def __str__(self):
        return f"AI evaluation: {self.application}"


class HumanEvaluation(models.Model):
    """A government evaluator's auditable evaluation of an application."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="human_evaluations",
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="human_evaluations",
    )
    technical_score = models.PositiveSmallIntegerField()
    innovation_score = models.PositiveSmallIntegerField()
    feasibility_score = models.PositiveSmallIntegerField()
    scalability_score = models.PositiveSmallIntegerField()
    evidence_score = models.PositiveSmallIntegerField()
    comments = models.TextField(blank=True)
    recommendation = models.CharField(
        max_length=10,
        choices=EvaluationRecommendation.choices,
        default=EvaluationRecommendation.REVIEW,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "human_evaluations"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["application", "evaluator"],
                name="unique_human_evaluation_per_evaluator",
            )
        ]
        indexes = [
            models.Index(fields=["application", "created_at"]),
            models.Index(fields=["evaluator", "created_at"]),
        ]

    @property
    def overall_score(self):
        return round(
            (
                self.technical_score
                + self.innovation_score
                + self.feasibility_score
                + self.scalability_score
                + self.evidence_score
            )
            / 5
            * 10,
            2,
        )

    def __str__(self):
        return f"{self.evaluator.name}: {self.application}"
