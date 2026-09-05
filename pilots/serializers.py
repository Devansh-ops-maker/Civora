from rest_framework import serializers

from evaluations.models import Application, ApplicationStatus

from .models import Milestone, Payment, Pilot, PilotEvidence


class PilotSerializer(serializers.ModelSerializer):
    application = serializers.UUIDField(source="application_id", read_only=True)
    challenge = serializers.UUIDField(source="challenge_id", read_only=True)
    startup = serializers.UUIDField(source="startup_id", read_only=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True)

    class Meta:
        model = Pilot
        fields = [
            "id", "application", "challenge", "startup", "created_by", "title",
            "description", "objectives", "budget", "start_date", "end_date",
            "success_criteria", "data_requirements", "status", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "application", "challenge", "startup", "created_by", "status",
            "created_at", "updated_at",
        ]

    def validate_application(self, value):
        application = Application.objects.filter(pk=value).select_related("challenge", "startup").first()
        if application is None:
            raise serializers.ValidationError("Application not found.")
        if application.status != ApplicationStatus.SELECTED:
            raise serializers.ValidationError("Only selected applications can create pilots.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        application_id = self.initial_data.get("application")
        application = Application.objects.filter(pk=application_id).select_related("challenge", "startup").first()
        if application is None:
            raise serializers.ValidationError({"application": "Selected application not found."})
        if application.status != ApplicationStatus.SELECTED:
            raise serializers.ValidationError({"application": "Only selected applications can create pilots."})
        if application.challenge.created_by_id != request.user.id:
            raise serializers.ValidationError({"application": "Only the challenge owner can create the pilot."})
        if Pilot.objects.filter(application=application).exists():
            raise serializers.ValidationError({"application": "A pilot already exists for this application."})
        return attrs


class PilotActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["activate", "complete", "fail", "cancel"])


class MilestoneSerializer(serializers.ModelSerializer):
    pilot = serializers.UUIDField(source="pilot_id", read_only=True)
    verified_by = serializers.UUIDField(source="verified_by_id", read_only=True)
    payment = serializers.SerializerMethodField()

    class Meta:
        model = Milestone
        fields = [
            "id", "pilot", "title", "description", "amount", "due_date", "status",
            "submitted_at", "verified_at", "verified_by", "payment_approved_at", "paid_at",
            "payment", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "pilot", "status", "submitted_at", "verified_at", "verified_by",
            "payment_approved_at", "paid_at", "payment", "created_at", "updated_at",
        ]

    def get_payment(self, obj):
        try:
            payment = obj.payment
        except Payment.DoesNotExist:
            return None
        return PaymentSerializer(payment).data

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Milestone amount cannot be negative.")
        return value


class PilotEvidenceSerializer(serializers.ModelSerializer):
    pilot = serializers.UUIDField(source="pilot_id", read_only=True)
    milestone = serializers.PrimaryKeyRelatedField(queryset=Milestone.objects.all())
    submitted_by = serializers.UUIDField(source="submitted_by_id", read_only=True)
    verified_by = serializers.UUIDField(source="verified_by_id", read_only=True)

    class Meta:
        model = PilotEvidence
        fields = [
            "id", "pilot", "milestone", "evidence_type", "title", "description", "file",
            "external_url", "submitted_by", "verified", "verified_by", "verified_at", "created_at",
        ]
        read_only_fields = ["id", "pilot", "submitted_by", "verified", "verified_by", "verified_at", "created_at"]

    def validate_milestone(self, value):
        pilot = self.context.get("pilot")
        if pilot and value.pilot_id != pilot.id:
            raise serializers.ValidationError("Milestone does not belong to this pilot.")
        if value.status not in {"SUBMITTED", "UNDER_REVIEW"}:
            raise serializers.ValidationError("Evidence can only be submitted after a milestone is submitted.")
        return value


class EvidenceVerifySerializer(serializers.Serializer):
    verified = serializers.BooleanField()


class PaymentSerializer(serializers.ModelSerializer):
    milestone = serializers.UUIDField(source="milestone_id", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "milestone", "amount", "status", "approved_at", "paid_at", "reference",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class PilotGenerateSerializer(serializers.Serializer):
    application = serializers.PrimaryKeyRelatedField(queryset=Application.objects.all())


from .models import (
    KPI,
    Simulation,
    RiskFlag,
    OutcomeDecision,
    KPIStatus,
    RiskSeverity,
    RiskStatus,
    OutcomeRecommendation,
)


class KPISerializer(serializers.ModelSerializer):
    class Meta:
        model = KPI
        fields = ["id", "pilot", "name", "description", "unit", "baseline", "target", "actual", "direction", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "pilot", "status", "created_at", "updated_at"]

    def validate(self, attrs):
        baseline = attrs.get("baseline")
        target = attrs.get("target")
        actual = attrs.get("actual")
        if target is None and actual is not None:
            raise serializers.ValidationError({"target": "Target is required when actual is provided."})
        return attrs

class SimulationSerializer(serializers.ModelSerializer):
    pilot = serializers.UUIDField(source="pilot_id", read_only=True)

    class Meta:
        model = Simulation
        fields = [
            "id",
            "pilot",
            "assumptions",
            "predicted_results",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "pilot",
            "created_at",
            "updated_at",
        ]

        
class RiskFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskFlag
        fields = ["id", "pilot", "category", "severity", "title", "reason", "mitigation", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "pilot", "created_at", "updated_at"]


class OutcomeDecisionSerializer(serializers.ModelSerializer):
    generated_by = serializers.UUIDField(source="generated_by_id", read_only=True)

    class Meta:
        model = OutcomeDecision
        fields = ["id", "pilot", "recommendation", "rationale", "kpi_summary", "risk_summary", "generated_by", "created_at", "updated_at"]
        read_only_fields = ["id", "pilot", "generated_by", "created_at", "updated_at"]


class SimulationGenerateSerializer(serializers.Serializer):
    assumptions = serializers.JSONField(default=dict)


class OutcomeDecisionGenerateSerializer(serializers.Serializer):
    force = serializers.BooleanField(default=False)
