from rest_framework import serializers

from challenges.models import ChallengeStatus

from .models import (
    Application,
    ApplicationStatus,
    AIEvaluation,
    EvaluationRecommendation,
    HumanEvaluation,
)


class ApplicationSerializer(serializers.ModelSerializer):
    challenge = serializers.UUIDField(source="challenge_id", read_only=True)
    startup = serializers.UUIDField(source="startup_id", read_only=True)
    status = serializers.CharField(read_only=True)
    eligibility_status = serializers.BooleanField(read_only=True, allow_null=True)
    eligibility_reason = serializers.CharField(read_only=True)

    class Meta:
        model = Application
        fields = [
            "id", "challenge", "startup", "proposal", "status",
            "eligibility_status", "eligibility_reason", "submitted_at", "updated_at",
        ]
        read_only_fields = [
            "id", "challenge", "startup", "status", "eligibility_status",
            "eligibility_reason", "submitted_at", "updated_at",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        challenge = self.context["challenge"]
        if challenge.status != ChallengeStatus.OPEN:
            raise serializers.ValidationError({"challenge": "Applications are only allowed for open challenges."})
        if Application.objects.filter(challenge=challenge, startup__user=request.user).exists():
            raise serializers.ValidationError({"challenge": "This startup has already applied to this challenge."})
        return attrs


class ApplicationActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["check_eligibility", "start_evaluation", "select", "reject"])


class EligibilityResultSerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    reason = serializers.CharField()
    status = serializers.ChoiceField(choices=ApplicationStatus.choices)


class AIEvaluationSerializer(serializers.ModelSerializer):
    overall_score = serializers.FloatField(read_only=True)

    class Meta:
        model = AIEvaluation
        fields = [
            "id", "application", "technical_score", "innovation_score",
            "feasibility_score", "scalability_score", "evidence_score",
            "overall_score", "strengths", "weaknesses", "missing_evidence",
            "recommendation", "explanation", "model_name", "created_at",
        ]
        read_only_fields = fields


class HumanEvaluationSerializer(serializers.ModelSerializer):
    evaluator = serializers.UUIDField(source="evaluator_id", read_only=True)
    overall_score = serializers.FloatField(read_only=True)

    class Meta:
        model = HumanEvaluation
        fields = [
            "id", "application", "evaluator", "technical_score", "innovation_score",
            "feasibility_score", "scalability_score", "evidence_score",
            "overall_score", "comments", "recommendation", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "application", "evaluator", "overall_score", "created_at", "updated_at"]

    def validate(self, attrs):
        for field in [
            "technical_score", "innovation_score", "feasibility_score",
            "scalability_score", "evidence_score",
        ]:
            value = attrs.get(field)
            if value is not None and not 0 <= value <= 10:
                raise serializers.ValidationError({field: "Score must be between 0 and 10."})
        return attrs


class EvaluationSummarySerializer(serializers.Serializer):
    application_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=ApplicationStatus.choices)
    ai_score = serializers.FloatField(allow_null=True)
    human_evaluation_count = serializers.IntegerField()
    human_average_score = serializers.FloatField(allow_null=True)
    combined_score = serializers.FloatField(allow_null=True)
    human_recommendations = serializers.DictField()
    selection_ready = serializers.BooleanField()
