from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import UserType
from pilots.models import Pilot
from startups.models import Startup

from .trust_graph import build_pilot_graph, build_startup_graph


class TrustGraphViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(
        detail=False,
        methods=["get"],
        url_path=r"startups/(?P<startup_id>[^/.]+)",
    )
    def startup(self, request, startup_id=None):
        startup = get_object_or_404(Startup, id=startup_id)

        if request.user.user_type == UserType.STARTUP and startup.user_id != request.user.id:
            return Response({"detail": "You can only view your own trust graph."}, status=status.HTTP_403_FORBIDDEN)

        return Response({
            "root": {"id": str(startup.id), "type": "startup", "label": startup.company_name},
            **build_startup_graph(startup),
        })

    @action(
        detail=False,
        methods=["get"],
        url_path=r"pilots/(?P<pilot_id>[^/.]+)",
    )
    def pilot(self, request, pilot_id=None):
        pilot = get_object_or_404(Pilot.objects.select_related("startup", "created_by"), id=pilot_id)

        if request.user.user_type == UserType.STARTUP and pilot.startup.user_id != request.user.id:
            return Response({"detail": "You can only view pilots involving your startup."}, status=status.HTTP_403_FORBIDDEN)

        if request.user.user_type == UserType.GOVERNMENT and pilot.created_by_id != request.user.id:
            return Response({"detail": "You can only view pilots owned by your department."}, status=status.HTTP_403_FORBIDDEN)

        graph = build_pilot_graph(pilot)
        return Response({
            "root": {"id": str(pilot.id), "type": "pilot", "label": pilot.title},
            **graph,
        })

    @action(
        detail=False,
        methods=["get"],
        url_path=r"challenges/(?P<challenge_id>[^/.]+)",
    )
    def challenge(self, request, challenge_id=None):
        from challenges.models import Challenge

        challenge = get_object_or_404(Challenge, id=challenge_id)
        if request.user.user_type == UserType.GOVERNMENT:
            if challenge.created_by_id != request.user.id:
                return Response({"detail": "You can only view challenges owned by your department."}, status=status.HTTP_403_FORBIDDEN)
        elif request.user.user_type == UserType.STARTUP:
            allowed = challenge.applications.filter(
                startup__user=request.user,
                status="SELECTED",
            ).exists()
            if not allowed:
                return Response({"detail": "You can only view challenges where your startup was selected."}, status=status.HTTP_403_FORBIDDEN)

        startup_ids = list(challenge.applications.filter(status="SELECTED").values_list("startup_id", flat=True))
        nodes = [{
            "id": str(challenge.id),
            "type": "challenge",
            "label": challenge.title,
            "status": challenge.status,
        }]
        edges = []

        for startup_id in startup_ids:
            startup = Startup.objects.get(id=startup_id)
            nodes.append({
                "id": str(startup.id),
                "type": "startup",
                "label": startup.company_name,
            })
            edges.append({
                "source": str(challenge.id),
                "target": str(startup.id),
                "relationship": "SELECTED_STARTUP",
            })

        return Response({
            "root": {"id": str(challenge.id), "type": "challenge", "label": challenge.title},
            "nodes": nodes,
            "edges": edges,
        })
