from rest_framework import serializers

from .models import Challenge, ChallengeStatus


class ChallengeSerializer(serializers.ModelSerializer):
    created_by = serializers.UUIDField(source="created_by_id", read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Challenge
        fields = [
            "id",
            "created_by",
            "title",
            "problem_statement",
            "desired_outcome",
            "requirements",
            "constraints",
            "budget",
            "start_date",
            "application_deadline",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "status", "created_at", "updated_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        deadline = attrs.get(
            "application_deadline",
            getattr(self.instance, "application_deadline", None),
        )
        budget = attrs.get("budget", getattr(self.instance, "budget", None))

        if start_date and deadline and deadline > start_date:
            raise serializers.ValidationError(
                {"application_deadline": "Application deadline cannot be after the challenge start date."}
            )

        if budget is not None and budget < 0:
            raise serializers.ValidationError({"budget": "Budget cannot be negative."})

        return attrs


class ChallengeTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ChallengeStatus.choices)

    def validate_status(self, value):
        challenge = self.context["challenge"]
        if not challenge.can_transition_to(value):
            raise serializers.ValidationError(
                f"Cannot transition challenge from {challenge.status} to {value}."
            )
        return value
