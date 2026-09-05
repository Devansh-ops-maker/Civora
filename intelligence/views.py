from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from accounts.permissions import IsGovernmentUser, IsStartupUser
from challenges.models import Challenge
from challenges.permissions import ChallengePermission
from startups.models import Startup

from .ollama import OllamaError
from .serializers import RadarExplanationSerializer, StartupMatchSerializer
from .services import explain_matches, rank_startups, update_challenge_embedding, update_startup_embedding


class RadarViewSet(viewsets.ViewSet):
    """Startup Radar endpoints. Semantic search is backed by pgvector;
    deterministic scoring is performed in Django; Qwen only explains results."""

    permission_classes = [permissions.IsAuthenticated]

    @action(
        detail=False,
        methods=["post"],
        url_path=r"challenges/(?P<challenge_id>[^/.]+)/refresh-embedding",
        permission_classes=[permissions.IsAuthenticated, IsGovernmentUser],
    )
    def refresh_challenge_embedding(self, request, challenge_id=None):
        challenge = self._get_owned_challenge(request, challenge_id)
        try:
            update_challenge_embedding(challenge)
        except OllamaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"detail": "Challenge embedding generated.", "challenge_id": str(challenge.id)})

    @action(
        detail=False,
        methods=["post"],
        url_path="startups/refresh-embedding",
        permission_classes=[permissions.IsAuthenticated, IsStartupUser],
    )
    def refresh_my_startup_embedding(self, request):
        startup = Startup.objects.filter(user=request.user).first()
        if startup is None:
            return Response({"detail": "Startup Passport not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            update_startup_embedding(startup)
        except OllamaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"detail": "Startup embedding generated.", "startup_id": str(startup.id)})

    @action(
        detail=False,
        methods=["get"],
        url_path=r"challenges/(?P<challenge_id>[^/.]+)/matches",
        permission_classes=[permissions.IsAuthenticated, IsGovernmentUser],
    )
    def matches(self, request, challenge_id=None):
        challenge = self._get_owned_challenge(request, challenge_id)
        try:
            limit = int(request.query_params.get("limit", 10))
        except ValueError:
            return Response({"limit": "Must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        if limit < 1 or limit > 50:
            return Response({"limit": "Must be between 1 and 50."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            results = rank_startups(challenge, limit=limit)
        except OllamaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "challenge_id": str(challenge.id),
            "count": len(results),
            "results": StartupMatchSerializer(results, many=True).data,
        })

    @action(
        detail=False,
        methods=["post"],
        url_path=r"challenges/(?P<challenge_id>[^/.]+)/explain",
        permission_classes=[permissions.IsAuthenticated, IsGovernmentUser],
    )
    def explain(self, request, challenge_id=None):
        challenge = self._get_owned_challenge(request, challenge_id)
        try:
            limit = int(request.data.get("limit", 5))
            if limit < 1 or limit > 10:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"limit": "Must be an integer between 1 and 10."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            matches = rank_startups(challenge, limit=limit)
            if not matches:
                return Response({"challenge_id": str(challenge.id), "results": []})
            explanations = explain_matches(challenge, matches)
            serializer = RadarExplanationSerializer(data=explanations, many=True)
            serializer.is_valid(raise_exception=True)
        except OllamaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            "challenge_id": str(challenge.id),
            "count": len(explanations),
            "results": serializer.data,
        })

    @staticmethod
    def _get_owned_challenge(request, challenge_id):
        return get_object_or_404(
            Challenge, id=challenge_id, created_by=request.user
        )
