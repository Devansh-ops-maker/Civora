import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PilotStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


ALLOWED_PILOT_TRANSITIONS = {
    PilotStatus.DRAFT: {PilotStatus.ACTIVE, PilotStatus.CANCELLED},
    PilotStatus.ACTIVE: {
        PilotStatus.COMPLETED,
        PilotStatus.FAILED,
        PilotStatus.CANCELLED,
    },
    PilotStatus.COMPLETED: set(),
    PilotStatus.FAILED: set(),
    PilotStatus.CANCELLED: set(),
}


class MilestoneStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SUBMITTED = "SUBMITTED", "Submitted"
    UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
    VERIFIED = "VERIFIED", "Verified"
    PAYMENT_APPROVED = "PAYMENT_APPROVED", "Payment Approved"
    PAID = "PAID", "Paid"


ALLOWED_MILESTONE_TRANSITIONS = {
    MilestoneStatus.PENDING: {MilestoneStatus.SUBMITTED},
    MilestoneStatus.SUBMITTED: {MilestoneStatus.UNDER_REVIEW},
    MilestoneStatus.UNDER_REVIEW: {MilestoneStatus.VERIFIED},
    MilestoneStatus.VERIFIED: {MilestoneStatus.PAYMENT_APPROVED},
    MilestoneStatus.PAYMENT_APPROVED: {MilestoneStatus.PAID},
    MilestoneStatus.PAID: set(),
}


class EvidenceType(models.TextChoices):
    DEPLOYMENT_REPORT = "DEPLOYMENT_REPORT", "Deployment Report"
    TEST_RESULT = "TEST_RESULT", "Test Result"
    KPI_REPORT = "KPI_REPORT", "KPI Report"
    GOVERNMENT_REPORT = "GOVERNMENT_REPORT", "Government Report"
    SYSTEM_LOG = "SYSTEM_LOG", "System Log"
    PHOTO = "PHOTO", "Photo"
    OTHER = "OTHER", "Other"


class Pilot(models.Model):
    """A controlled pilot between a government department and a selected startup."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        "evaluations.Application",
        on_delete=models.PROTECT,
        related_name="pilot",
    )
    challenge = models.ForeignKey(
        "challenges.Challenge",
        on_delete=models.PROTECT,
        related_name="pilots",
    )
    startup = models.ForeignKey(
        "startups.Startup",
        on_delete=models.PROTECT,
        related_name="pilots",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_pilots",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    objectives = models.JSONField(default=list, blank=True)
    budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    success_criteria = models.JSONField(default=list, blank=True)
    data_requirements = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PilotStatus.choices,
        default=PilotStatus.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pilots"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "status"]),
            models.Index(fields=["startup", "status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.startup.company_name})"

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "Pilot end date cannot be before the start date."
        if self.budget is not None and self.budget < 0:
            errors["budget"] = "Pilot budget cannot be negative."
        if errors:
            raise ValidationError(errors)

    def can_transition_to(self, new_status):
        return new_status in ALLOWED_PILOT_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status):
        if new_status == self.status:
            raise ValidationError({"status": "Pilot is already in this status."})
        if not self.can_transition_to(new_status):
            raise ValidationError(
                {"status": f"Cannot transition pilot from {self.status} to {new_status}."}
            )
        self.status = new_status


class Milestone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=MilestoneStatus.choices,
        default=MilestoneStatus.PENDING,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="verified_pilot_milestones",
    )
    payment_approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pilot_milestones"
        ordering = ["due_date", "created_at"]
        indexes = [
            models.Index(fields=["pilot", "status"]),
            models.Index(fields=["due_date", "status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.pilot.title})"

    def clean(self):
        if self.amount is not None and self.amount < 0:
            raise ValidationError({"amount": "Milestone amount cannot be negative."})

    def can_transition_to(self, new_status):
        return new_status in ALLOWED_MILESTONE_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status):
        if new_status == self.status:
            raise ValidationError({"status": "Milestone is already in this status."})
        if not self.can_transition_to(new_status):
            raise ValidationError(
                {"status": f"Cannot transition milestone from {self.status} to {new_status}."}
            )
        self.status = new_status


class PilotEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name="evidence")
    milestone = models.ForeignKey(
        Milestone,
        on_delete=models.CASCADE,
        related_name="evidence",
    )
    evidence_type = models.CharField(max_length=30, choices=EvidenceType.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="pilot_evidence/", null=True, blank=True)
    external_url = models.URLField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_pilot_evidence",
    )
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="verified_pilot_evidence",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pilot_evidence"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pilot", "milestone"]),
            models.Index(fields=["verified", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.pilot.title})"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    PAID = "PAID", "Paid"


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    milestone = models.OneToOneField(
        Milestone,
        on_delete=models.CASCADE,
        related_name="payment",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pilot_payments"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"Payment for {self.milestone.title}: {self.amount}"


class KPIDirection(models.TextChoices):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER", "Higher is Better"
    LOWER_IS_BETTER = "LOWER_IS_BETTER", "Lower is Better"


class KPIStatus(models.TextChoices):
    NOT_MEASURED = "NOT_MEASURED", "Not Measured"
    ACHIEVED = "ACHIEVED", "Achieved"
    PARTIALLY_ACHIEVED = "PARTIALLY_ACHIEVED", "Partially Achieved"
    FAILED = "FAILED", "Failed"


class KPI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name="kpis")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=100)
    baseline = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    target = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    actual = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    direction = models.CharField(max_length=20, choices=KPIDirection.choices, default=KPIDirection.HIGHER_IS_BETTER)
    status = models.CharField(max_length=25, choices=KPIStatus.choices, default=KPIStatus.NOT_MEASURED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pilot_kpis"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["pilot", "status"])]

    def evaluate(self):
        if self.target is None or self.actual is None:
            return KPIStatus.NOT_MEASURED
        if self.direction == KPIDirection.LOWER_IS_BETTER:
            if self.baseline is not None and self.baseline == self.target:
                return KPIStatus.ACHIEVED if self.actual <= self.target else KPIStatus.FAILED
            if self.baseline is not None:
                expected_delta = self.baseline - self.target
                actual_delta = self.baseline - self.actual
                if expected_delta == 0:
                    return KPIStatus.ACHIEVED if self.actual <= self.target else KPIStatus.FAILED
                progress = actual_delta / expected_delta
                if progress >= 1:
                    return KPIStatus.ACHIEVED
                if progress >= 0.75:
                    return KPIStatus.PARTIALLY_ACHIEVED
                return KPIStatus.FAILED
            return KPIStatus.ACHIEVED if self.actual <= self.target else KPIStatus.FAILED

        if self.target == self.baseline:
            return KPIStatus.ACHIEVED if self.actual >= self.target else KPIStatus.FAILED
        if self.baseline is not None:
            expected_delta = self.target - self.baseline
            actual_delta = self.actual - self.baseline
            if expected_delta == 0:
                return KPIStatus.ACHIEVED if self.actual >= self.target else KPIStatus.FAILED
            progress = actual_delta / expected_delta
            if progress >= 1:
                return KPIStatus.ACHIEVED
            if progress >= 0.75:
                return KPIStatus.PARTIALLY_ACHIEVED
            return KPIStatus.FAILED
        return KPIStatus.ACHIEVED if self.actual >= self.target else KPIStatus.FAILED

    def save(self, *args, **kwargs):
        if self.target is not None and self.actual is not None:
            self.status = self.evaluate()
        super().save(*args, **kwargs)


class Simulation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pilot = models.OneToOneField(Pilot, on_delete=models.CASCADE, related_name="simulation")
    assumptions = models.JSONField(default=dict, blank=True)
    predicted_results = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pilot_simulations"


class RiskSeverity(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class RiskStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    MITIGATED = "MITIGATED", "Mitigated"
    ACCEPTED = "ACCEPTED", "Accepted"


class RiskFlag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name="risk_flags")
    category = models.CharField(max_length=50)
    severity = models.CharField(max_length=20, choices=RiskSeverity.choices)
    title = models.CharField(max_length=255)
    reason = models.TextField()
    mitigation = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=RiskStatus.choices, default=RiskStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pilot_risk_flags"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["pilot", "severity", "status"])]


class OutcomeRecommendation(models.TextChoices):
    SCALE = "SCALE", "Scale"
    EXTEND_PILOT = "EXTEND_PILOT", "Extend Pilot"
    STOP = "STOP", "Stop"


class OutcomeDecision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pilot = models.OneToOneField(Pilot, on_delete=models.CASCADE, related_name="outcome_decision")
    recommendation = models.CharField(max_length=20, choices=OutcomeRecommendation.choices)
    rationale = models.TextField()
    kpi_summary = models.JSONField(default=dict, blank=True)
    risk_summary = models.JSONField(default=dict, blank=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="outcome_decisions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pilot_outcome_decisions"
