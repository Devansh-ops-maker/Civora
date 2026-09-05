from rest_framework import serializers

from .models import Startup, StartupEvidence


class StartupEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = StartupEvidence
        fields = [
            "id",
            "startup",
            "evidence_type",
            "title",
            "description",
            "document",
            "external_url",
            "verified",
            "verified_at",
            "created_at",
        ]
        # `startup` is set from the URL/authenticated user, never from the
        # request body. `verified`/`verified_at` are set only through the
        # government-only verify action (spec: Claim -> Evidence -> Verification).
        read_only_fields = ["id", "startup", "verified", "verified_at", "created_at"]


class StartupEvidenceVerifySerializer(serializers.Serializer):
    verified = serializers.BooleanField()


class StartupListSerializer(serializers.ModelSerializer):
    """Slim representation for browsing — this is what Startup Radar (Phase 5) will rank."""

    class Meta:
        model = Startup
        fields = [
            "id",
            "company_name",
            "industry",
            "technologies",
            "location",
            "founded_year",
            "team_size",
        ]


class StartupDetailSerializer(serializers.ModelSerializer):
    evidence = StartupEvidenceSerializer(many=True, read_only=True)
    pilot_count = serializers.IntegerField(read_only=True)
    deployment_count = serializers.IntegerField(read_only=True)
    verified_evidence_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Startup
        fields = [
            "id",
            "user",
            "company_name",
            "description",
            "website",
            "industry",
            "technologies",
            "founded_year",
            "team_size",
            "location",
            "pilot_count",
            "deployment_count",
            "verified_evidence_count",
            "evidence",
            "created_at",
            "updated_at",
        ]
        # `embedding` is deliberately excluded: it's a system-managed vector
        # produced by intelligence.embeddings, never a direct API input, and
        # not useful to API consumers as raw floats.
        read_only_fields = ["id", "user", "created_at", "updated_at"]
