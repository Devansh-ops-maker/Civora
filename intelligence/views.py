import json
import requests
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsGovernmentUser, IsStartupUser
from challenges.models import Challenge
from challenges.permissions import ChallengePermission
from startups.models import Startup

from .ollama import OllamaError
from .scrapers import get_startup_schemes
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
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

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

    @action(
        detail=False,
        methods=["get"],
        url_path="schemes",
        permission_classes=[permissions.IsAuthenticated, IsStartupUser],
    )
    def schemes(self, request):
        """Retrieve government schemes from Startup India."""
        payload, error_response = get_filtered_schemes_payload(request.query_params)
        if error_response:
            return error_response
        return Response(payload)

    @staticmethod
    def _get_owned_challenge(request, challenge_id):
        return get_object_or_404(
            Challenge, id=challenge_id, created_by=request.user
        )


SCHEMES_CACHE_KEY = "startup_india_schemes_cache"
SCHEMES_CACHE_TIMEOUT = 3600  # 1 hour


def get_filtered_schemes_payload(query_params):
    """Fetch, cache, and filter Startup India government schemes."""
    timeout_param = query_params.get("timeout", 30)
    try:
        timeout = int(timeout_param)
        if timeout <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, Response(
            {"detail": "timeout must be a positive integer."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    force_refresh = query_params.get("refresh", "").lower() in {"1", "true", "yes"}

    cached_data = cache.get(SCHEMES_CACHE_KEY)
    if cached_data and not force_refresh:
        data = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
        is_cached = True
    else:
        try:
            data = get_startup_schemes(timeout=timeout)
            cache.set(SCHEMES_CACHE_KEY, data, SCHEMES_CACHE_TIMEOUT)
            is_cached = False
        except requests.RequestException as exc:
            if cached_data:
                data = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                is_cached = True
            else:
                return None, Response(
                    {"detail": f"Failed to fetch schemes from Startup India: {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
        except Exception as exc:
            return None, Response(
                {"detail": f"Unexpected error while fetching schemes: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    ministry = query_params.get("ministry")
    sector = query_params.get("sector")
    search = query_params.get("search")

    schemes = list(data.get("schemes", []))

    if ministry:
        min_lower = ministry.lower()
        schemes = [
            s for s in schemes
            if min_lower in (s.get("ministry") or "").lower()
        ]

    if sector:
        sec_lower = sector.lower()
        schemes = [
            s for s in schemes
            if any(sec_lower in str(sec).lower() for sec in s.get("sectors", []))
        ]

    if search:
        search_lower = search.lower()
        schemes = [
            s for s in schemes
            if search_lower in (s.get("scheme_name") or "").lower()
            or search_lower in (s.get("brief") or "").lower()
            or any(search_lower in str(t).lower() for t in s.get("benefit_tags", []))
            or any(search_lower in str(b).lower() for b in s.get("benefits", []))
        ]

    if query_params.get("output") == "array" or query_params.get("shape") == "array":
        return schemes, None

    response_payload = {
        "status": "success",
        "count": len(schemes),
        "schemes": schemes,
        "results": schemes,
        "metadata": {
            **(data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}),
            "scheme_count": len(schemes),
            "cached": is_cached,
        },
    }
    return response_payload, None


class GovernmentSchemesView(APIView):
    """Direct endpoint returning Startup India government schemes in JSON format (Startup users only)."""

    permission_classes = [permissions.IsAuthenticated, IsStartupUser]

    def get(self, request):
        payload, error_response = get_filtered_schemes_payload(request.query_params)
        if error_response:
            return error_response
        return Response(payload)
