from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsGovernmentUser, IsStartupUser

from .models import Startup, StartupEvidence
from .serializers import (
    StartupDetailSerializer,
    StartupEvidenceSerializer,
    StartupEvidenceVerifySerializer,
    StartupListSerializer,
)


class StartupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/startups/          browse Startup Passports
    GET /api/startups/{id}/     view a single passport + its evidence

    Read-only by design: a passport is only ever edited by its own owner
    through /api/startups/passport/. Any authenticated user (government or
    startup) may browse — government users need this to review candidates;
    later phases (Startup Radar) will query this data programmatically
    rather than through this endpoint.
    """

    queryset = Startup.objects.all().prefetch_related("evidence")
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return StartupDetailSerializer
        return StartupListSerializer


class MyPassportView(APIView):
    """
    GET/PATCH /api/startups/passport/
    The authenticated startup's own Startup Passport.
    """

    permission_classes = [permissions.IsAuthenticated, IsStartupUser]

    def get_object(self, user):
        return get_object_or_404(Startup, user=user)

    def get(self, request):
        return Response(StartupDetailSerializer(self.get_object(request.user)).data)

    def patch(self, request):
        startup = self.get_object(request.user)
        serializer = StartupDetailSerializer(startup, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    put = patch


class MyEvidenceListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/startups/passport/evidence/   own evidence
    POST /api/startups/passport/evidence/   add evidence to own passport
    """

    serializer_class = StartupEvidenceSerializer
    permission_classes = [permissions.IsAuthenticated, IsStartupUser]

    def get_queryset(self):
        return StartupEvidence.objects.filter(startup__user=self.request.user)

    def perform_create(self, serializer):
        startup = get_object_or_404(Startup, user=self.request.user)
        serializer.save(startup=startup)


class MyEvidenceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    /api/startups/passport/evidence/{evidence_id}/
    A startup may edit or remove its own evidence, but only while it is
    still unverified — once government has verified a claim, silently
    editing it would break the Claim -> Evidence -> Verification chain.
    """

    serializer_class = StartupEvidenceSerializer
    permission_classes = [permissions.IsAuthenticated, IsStartupUser]
    lookup_url_kwarg = "evidence_id"

    def get_queryset(self):
        return StartupEvidence.objects.filter(startup__user=self.request.user)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), id=self.kwargs["evidence_id"])

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.verified:
            return Response(
                {
                    "detail": "Verified evidence cannot be edited. "
                    "Contact the government reviewer if it needs to change."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.verified:
            return Response(
                {"detail": "Verified evidence cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class StartupEvidenceListView(generics.ListAPIView):
    """
    GET /api/startups/{startup_id}/evidence/
    Read-only view of a given startup's evidence, for government reviewers
    during evaluation — without granting them write access to it.
    """

    serializer_class = StartupEvidenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StartupEvidence.objects.filter(startup_id=self.kwargs["startup_id"])


class VerifyEvidenceView(APIView):
    """
    POST /api/startups/evidence/{evidence_id}/verify/   { "verified": true|false }

    Government-only. Records who verified a claim and when, which is what
    turns a startup's claim into part of the Trust Graph (spec section 26):
    Claim -> Evidence -> Verification.
    """

    permission_classes = [permissions.IsAuthenticated, IsGovernmentUser]

    def post(self, request, evidence_id):
        evidence = get_object_or_404(StartupEvidence, id=evidence_id)
        serializer = StartupEvidenceVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_verified = serializer.validated_data["verified"]
        evidence.verified = is_verified
        evidence.verified_by = request.user if is_verified else None
        evidence.verified_at = timezone.now() if is_verified else None
        evidence.save(update_fields=["verified", "verified_by", "verified_at"])

        return Response(StartupEvidenceSerializer(evidence).data)
