from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import Challenge
from .permissions import ChallengePermission
from .serializers import ChallengeSerializer, ChallengeTransitionSerializer


class ChallengeViewSet(viewsets.ModelViewSet):
    """
    Challenge API.

    GET    /api/challenges/           list challenges
    POST   /api/challenges/           government creates a challenge
    GET    /api/challenges/{id}/      retrieve a challenge
    PATCH  /api/challenges/{id}/      government updates own challenge
    DELETE /api/challenges/{id}/      government deletes own challenge
    POST   /api/challenges/{id}/transition/  move through the lifecycle
    """

    serializer_class = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticated, ChallengePermission]
    queryset = Challenge.objects.select_related("created_by").all()
    filterset_fields = ["status", "created_by"]

    def get_queryset(self):
        queryset = Challenge.objects.select_related("created_by").all()
        if self.request.user.is_government:
            return queryset
        return queryset.filter(status="OPEN")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        challenge = self.get_object()
        serializer = ChallengeTransitionSerializer(
            data=request.data,
            context={"challenge": challenge},
        )
        serializer.is_valid(raise_exception=True)

        challenge.transition_to(serializer.validated_data["status"])
        challenge.save(update_fields=["status", "updated_at"])

        return Response(self.get_serializer(challenge).data, status=status.HTTP_200_OK)
