from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
# from rest_framework.decorators import action
from rest_framework.decorators import action as drf_action
from rest_framework.response import Response

from accounts.models import UserType
from challenges.models import ChallengeStatus
from evaluations.models import Application, ApplicationStatus
from intelligence.ollama import OllamaError

from .models import (
    KPI, Milestone, Payment, PaymentStatus, Pilot, PilotEvidence,
)
from .models import (
    KPI,
    Milestone,
    Payment,
    PaymentStatus,
    Pilot,
    PilotEvidence,
    PilotStatus,
)
from .permissions import MilestonePermission, PilotEvidencePermission, PilotPermission
from .serializers import (
    EvidenceVerifySerializer,
    MilestoneSerializer,
    PaymentSerializer,
    PilotEvidenceSerializer,
    PilotGenerateSerializer,
    PilotSerializer,
    PilotActionSerializer,
    KPISerializer, RiskFlagSerializer, SimulationSerializer, OutcomeDecisionSerializer,
    SimulationGenerateSerializer, OutcomeDecisionGenerateSerializer,
)
from .services import (
    create_pilot_from_plan, generate_pilot_plan, submit_milestone,
    run_pre_pilot_simulation, generate_risk_flags, compute_outcome_decision,
)
from rest_framework.views import APIView
from rest_framework import status as drf_status
from .models import Pilot
from .serializers import PilotSerializer
from .permissions import PilotPermission


class PilotViewSet(viewsets.ModelViewSet):
    queryset = Pilot.objects.select_related(
        "application", "challenge", "startup", "created_by"
    ).prefetch_related("milestones", "evidence")
    serializer_class = PilotSerializer
    permission_classes = [permissions.IsAuthenticated, PilotPermission]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == UserType.STARTUP:
            return self.queryset.filter(startup__user=user)
        if user.user_type == UserType.GOVERNMENT:
            return self.queryset.filter(created_by=user)
        return self.queryset.none()

    def create(self, request, *args, **kwargs):
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can create pilots."}, status=status.HTTP_403_FORBIDDEN)
        application_id = request.data.get("application")
        application = get_object_or_404(Application.objects.select_related("challenge", "startup"), id=application_id)
        if application.status != ApplicationStatus.SELECTED:
            return Response({"application": "Only selected applications can create pilots."}, status=status.HTTP_400_BAD_REQUEST)
        if application.challenge.created_by_id != request.user.id:
            return Response({"application": "Only the challenge owner can create the pilot."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pilot = serializer.save(
            application=application,
            challenge=application.challenge,
            startup=application.startup,
            created_by=request.user,
        )
        return Response(self.get_serializer(pilot).data, status=status.HTTP_201_CREATED)

    @drf_action(detail=True, methods=["post"], url_path="action")
    def action(self, request, pk=None):
        pilot = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can manage pilot status."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PilotActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_name = serializer.validated_data["action"]
        target = {
            "activate": "ACTIVE",
            "complete": "COMPLETED",
            "fail": "FAILED",
            "cancel": "CANCELLED",
        }[action_name]
        try:
            pilot.transition_to(target)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        pilot.save(update_fields=["status", "updated_at"])
        if target == PilotStatus.ACTIVE and pilot.challenge.status == ChallengeStatus.EVALUATION:
            pilot.challenge.transition_to(ChallengeStatus.PILOT)
            pilot.challenge.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(pilot).data)

    @drf_action(detail=True, methods=["get", "post"], url_path="milestones")
    def milestones(self, request, pk=None):
        pilot = self.get_object()
        if request.method == "GET":
            return Response(MilestoneSerializer(pilot.milestones.all(), many=True).data)
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can create milestones."}, status=status.HTTP_403_FORBIDDEN)
        serializer = MilestoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        milestone = serializer.save(pilot=pilot)
        return Response(MilestoneSerializer(milestone).data, status=status.HTTP_201_CREATED)

    @drf_action(detail=True, methods=["get", "post"], url_path="evidence")
    def evidence(self, request, pk=None):
        pilot = self.get_object()
        if request.method == "GET":
            return Response(PilotEvidenceSerializer(pilot.evidence.all(), many=True).data)
        if request.user.user_type != UserType.STARTUP:
            return Response({"detail": "Only the participating startup can submit evidence."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PilotEvidenceSerializer(
            data=request.data,
            context={"request": request, "pilot": pilot},
        )
        serializer.is_valid(raise_exception=True)
        evidence = serializer.save(pilot=pilot, submitted_by=request.user)
        return Response(PilotEvidenceSerializer(evidence).data, status=status.HTTP_201_CREATED)

    @drf_action(detail=True, methods=["post"], url_path="generate-plan")
    def generate_plan(self, request, pk=None):
        pilot = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can generate pilot plans."}, status=status.HTTP_403_FORBIDDEN)
        try:
            plan = generate_pilot_plan(pilot.application)
        except (OllamaError, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(plan)

    @drf_action(detail=False, methods=["post"], url_path="generate-from-application")
    def generate_from_application(self, request):
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can generate pilot plans."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PilotGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.validated_data["application"]
        if application.challenge.created_by_id != request.user.id:
            return Response({"detail": "Only the challenge owner can create this pilot."}, status=status.HTTP_403_FORBIDDEN)
        try:
            plan = generate_pilot_plan(application)
            pilot = create_pilot_from_plan(application, plan, request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except OllamaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"pilot": PilotSerializer(pilot).data, "plan": plan}, status=status.HTTP_201_CREATED)


    @drf_action(detail=True, methods=["get", "post"], url_path="kpis")
    def kpis(self, request, pk=None):
        pilot = self.get_object()
        if request.method == "GET":
            return Response(KPISerializer(pilot.kpis.all(), many=True).data)
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can create KPIs."}, status=status.HTTP_403_FORBIDDEN)
        serializer = KPISerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kpi = serializer.save(pilot=pilot)
        return Response(KPISerializer(kpi).data, status=status.HTTP_201_CREATED)

    @drf_action(detail=True, methods=["post"], url_path="simulate")
    def simulate(self, request, pk=None):
        pilot = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can run simulations."}, status=status.HTTP_403_FORBIDDEN)
        serializer = SimulationGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        simulation = run_pre_pilot_simulation(pilot, serializer.validated_data.get("assumptions"))
        return Response(SimulationSerializer(simulation).data)

    @drf_action(detail=True, methods=["post"], url_path="risk-check")
    def risk_check(self, request, pk=None):
        pilot = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can run risk checks."}, status=status.HTTP_403_FORBIDDEN)
        risks = generate_risk_flags(pilot)
        return Response({"count": len(risks), "risks": RiskFlagSerializer(risks, many=True).data})

    @drf_action(detail=True, methods=["get", "post"], url_path="outcome")
    def outcome(self, request, pk=None):
        pilot = self.get_object()
        if request.method == "GET":
            decision = getattr(pilot, "outcome_decision", None)
            if decision is None:
                return Response({"detail": "Outcome decision has not been generated."}, status=status.HTTP_404_NOT_FOUND)
            return Response(OutcomeDecisionSerializer(decision).data)
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can generate outcome decisions."}, status=status.HTTP_403_FORBIDDEN)
        serializer = OutcomeDecisionGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if pilot.status not in {PilotStatus.COMPLETED, PilotStatus.FAILED} and not serializer.validated_data.get("force"):
            return Response({"detail": "Complete or fail the pilot before generating an outcome decision."}, status=status.HTTP_400_BAD_REQUEST)
        decision = compute_outcome_decision(pilot, request.user)
        return Response(OutcomeDecisionSerializer(decision).data)


class MilestoneViewSet(viewsets.ModelViewSet):
    queryset = Milestone.objects.select_related("pilot", "pilot__startup", "pilot__created_by").prefetch_related("evidence")
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticated, MilestonePermission]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == UserType.STARTUP:
            qs = self.queryset.filter(pilot__startup__user=user)
        elif user.user_type == UserType.GOVERNMENT:
            qs = self.queryset.filter(pilot__created_by=user)
        else:
            return self.queryset.none()

        # Optional `pilot` query parameter to narrow milestones to a specific pilot.
        pilot_param = self.request.query_params.get("pilot")
        if pilot_param:
            # tolerate full URLs or paths being passed (frontend bug)
            if isinstance(pilot_param, str) and (pilot_param.startswith("http://") or pilot_param.startswith("https://") or "/" in pilot_param):
                pilot_param = pilot_param.rstrip("/").split("/")[-1]
            try:
                # filter by UUID string; invalid values will simply return empty queryset
                qs = qs.filter(pilot__id=pilot_param)
            except Exception:
                return self.queryset.none()

        return qs

    @drf_action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        milestone = self.get_object()
        if request.user.user_type != UserType.STARTUP:
            return Response({"detail": "Only the participating startup can submit a milestone."}, status=status.HTTP_403_FORBIDDEN)
        try:
            milestone = submit_milestone(milestone)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(milestone).data)

    @drf_action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        milestone = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can review milestones."}, status=status.HTTP_403_FORBIDDEN)
        if milestone.status != "SUBMITTED":
            return Response({"detail": "Only submitted milestones can enter review."}, status=status.HTTP_400_BAD_REQUEST)
        milestone.transition_to("UNDER_REVIEW")
        milestone.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(milestone).data)

    @drf_action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        milestone = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can verify milestones."}, status=status.HTTP_403_FORBIDDEN)
        if milestone.status != "UNDER_REVIEW":
            return Response({"detail": "Milestone must be under review before verification."}, status=status.HTTP_400_BAD_REQUEST)
        evidence_exists = milestone.evidence.filter(verified=True).exists()
        if not evidence_exists:
            return Response({"detail": "At least one verified evidence record is required before verification."}, status=status.HTTP_400_BAD_REQUEST)
        milestone.transition_to("VERIFIED")
        milestone.verified_at = timezone.now()
        milestone.verified_by = request.user
        milestone.save(update_fields=["status", "verified_at", "verified_by", "updated_at"])
        Payment.objects.get_or_create(
            milestone=milestone,
            defaults={
                "amount": milestone.amount,
                "status": PaymentStatus.PENDING,
            },
        )
        return Response(self.get_serializer(milestone).data)

    @drf_action(detail=True, methods=["post"], url_path="approve-payment")
    def approve_payment(self, request, pk=None):
        milestone = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can approve payments."}, status=status.HTTP_403_FORBIDDEN)
        if milestone.status != "VERIFIED":
            return Response({"detail": "Only verified milestones can be payment approved."}, status=status.HTTP_400_BAD_REQUEST)
        milestone.transition_to("PAYMENT_APPROVED")
        milestone.payment_approved_at = timezone.now()
        milestone.save(update_fields=["status", "payment_approved_at", "updated_at"])
        payment = Payment.objects.get_or_create(
            milestone=milestone,
            defaults={"amount": milestone.amount, "status": PaymentStatus.PENDING},
        )[0]
        payment.status = PaymentStatus.APPROVED
        payment.approved_at = timezone.now()
        payment.save(update_fields=["status", "approved_at", "updated_at"])
        return Response(self.get_serializer(milestone).data)

    @drf_action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        milestone = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can mark simulated payments as paid."}, status=status.HTTP_403_FORBIDDEN)
        if milestone.status != "PAYMENT_APPROVED":
            return Response({"detail": "Payment must be approved before it can be marked paid."}, status=status.HTTP_400_BAD_REQUEST)
        milestone.transition_to("PAID")
        milestone.paid_at = timezone.now()
        milestone.save(update_fields=["status", "paid_at", "updated_at"])
        payment = Payment.objects.get(milestone=milestone)
        payment.status = PaymentStatus.PAID
        payment.paid_at = timezone.now()
        payment.reference = f"SIM-{milestone.id.hex[:10].upper()}"
        payment.save(update_fields=["status", "paid_at", "reference", "updated_at"])
        return Response(self.get_serializer(milestone).data)


class PilotEvidenceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PilotEvidence.objects.select_related("pilot", "milestone", "submitted_by", "verified_by")
    serializer_class = PilotEvidenceSerializer
    permission_classes = [permissions.IsAuthenticated, PilotEvidencePermission]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == UserType.STARTUP:
            return self.queryset.filter(pilot__startup__user=user)
        if user.user_type == UserType.GOVERNMENT:
            return self.queryset.filter(pilot__created_by=user)
        return self.queryset.none()

    @drf_action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        evidence = self.get_object()
        if request.user.user_type != UserType.GOVERNMENT:
            return Response({"detail": "Only government users can verify evidence."}, status=status.HTTP_403_FORBIDDEN)
        serializer = EvidenceVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if evidence.verified and not serializer.validated_data["verified"]:
            return Response({"detail": "Verified evidence cannot be unverified in the MVP."}, status=status.HTTP_400_BAD_REQUEST)
        evidence.verified = serializer.validated_data["verified"]
        if evidence.verified:
            evidence.verified_by = request.user
            evidence.verified_at = timezone.now()
        evidence.save(update_fields=["verified", "verified_by", "verified_at"])
        return Response(PilotEvidenceSerializer(evidence).data)



class ManagePilotView(APIView):
    """Convenience endpoint for frontends that request manage page by query param.

    GET /api/pilots/manage/?pilot_id=<uuid>
    """
    permission_classes = [permissions.IsAuthenticated, PilotPermission]

    def get(self, request):
        pilot_id = request.query_params.get("pilot_id")
        if not pilot_id:
            return Response({"detail": "pilot_id query parameter is required."}, status=drf_status.HTTP_400_BAD_REQUEST)

        # Handle frontend bugs where a full URL or path is passed as pilot_id
        # Examples observed in the wild: "http://localhost:5173/startup/pilots/<pilot_uuid>" or
        # "/startup/pilots/<pilot_uuid>" — extract the trailing path segment as the UUID.
        if isinstance(pilot_id, str) and (pilot_id.startswith("http://") or pilot_id.startswith("https://") or "/" in pilot_id):
            # strip trailing slash
            pilot_id_candidate = pilot_id.rstrip("/")
            # take last path segment
            pilot_id = pilot_id_candidate.split("/")[-1]
        pilot = get_object_or_404(Pilot.objects.select_related("application", "challenge", "startup", "created_by"), id=pilot_id)
        # object-level permission check
        perm = PilotPermission()
        if not perm.has_object_permission(request, self, pilot):
            return Response({"detail": "You do not have permission to access this pilot."}, status=drf_status.HTTP_403_FORBIDDEN)
        return Response(PilotSerializer(pilot).data)
