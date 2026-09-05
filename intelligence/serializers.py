from rest_framework import serializers


class StartupMatchSerializer(serializers.Serializer):
    startup_id = serializers.UUIDField()
    company_name = serializers.CharField()
    industry = serializers.CharField()
    technologies = serializers.ListField(child=serializers.CharField())
    semantic_similarity = serializers.FloatField()
    technology_fit = serializers.FloatField()
    domain_fit = serializers.FloatField()
    pilot_readiness = serializers.FloatField()
    evidence_score = serializers.FloatField()
    match_score = serializers.FloatField()
    match_reasons = serializers.ListField(child=serializers.CharField())
    risks = serializers.ListField(child=serializers.CharField())


class RadarExplanationSerializer(serializers.Serializer):
    startup_id = serializers.UUIDField()
    explanation = serializers.CharField()
    strengths = serializers.ListField(child=serializers.CharField())
    concerns = serializers.ListField(child=serializers.CharField())
